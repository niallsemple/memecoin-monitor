#!/usr/bin/env python3
"""Memecoin new-listing monitor + audit scorer.

Each run:
 1. Polls dexscreener token-profiles/latest for new listings.
 2. Dedups against state.json (seen tokens persist across runs).
 3. Audits NEW tokens: GoPlus (contract security) + RugCheck (Solana behaviour).
 4. Snapshots price/MC/liquidity at detection.
 5. Re-fetches prices for previously seen tokens to track outcomes over time.
 6. Appends results to watchlist.md and updates state.json.

Designed to be invoked repeatedly (each goal turn = one or more cycles).
"""
import json, time, sys, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).parent
STATE_FILE = ROOT / "state.json"
WATCHLIST = ROOT / "watchlist.md"

DEX_PROFILES = "https://api.dexscreener.com/token-profiles/latest/v1"
DEX_BOOSTS = "https://api.dexscreener.com/token-boosts/latest/v1"
DEX_TOKENS = "https://api.dexscreener.com/latest/dex/tokens/{}"
GOPLUS_SOL = "https://api.gopluslabs.io/api/v1/solana/token_security?contract_addresses={}"
GOPLUS_EVM = "https://api.gopluslabs.io/api/v1/token_security/{}?contract_addresses={}"
RUGCHECK = "https://api.rugcheck.xyz/v1/tokens/{}/report/summary"
RUGCHECK_FULL = "https://api.rugcheck.xyz/v1/tokens/{}/report"

EVM_CHAIN_IDS = {"ethereum": "1", "bsc": "56", "base": "8453", "arbitrum": "42171", "polygon": "137"}

UA = {"User-Agent": "memecoin-monitor/1.0 (research)"}

def get(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"_error": str(e)}

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"seen": {}, "runs": 0}

def save_state(s):
    STATE_FILE.write_text(json.dumps(s, indent=1))

def audit_solana(addr):
    """Return (flags, notes). flags<0 danger, 0 neutral, >0 good."""
    flags, notes = [], []
    gp = get(GOPLUS_SOL.format(addr))
    time.sleep(1.5)
    if "_error" not in gp and gp.get("code") == 1:
        d = gp["result"].get(addr, {})
        def bad(key):
            v = d.get(key, {})
            if isinstance(v, dict):
                return v.get("status") == "1"
            return False
        if bad("mintable"): flags.append("MINTABLE")
        if bad("freezable"): flags.append("FREEZABLE")
        if bad("closable"): flags.append("CLOSABLE")
        if bad("metadata_mutable"): flags.append("METADATA_MUTABLE")
        if bad("balance_mutable_authority"): flags.append("BALANCE_MUTABLE")
        if d.get("non_transferable") == "1": flags.append("NON_TRANSFERABLE")
        if d.get("default_account_state") == "1" and d.get("default_account_state_upgradable", {}).get("status") == "1":
            flags.append("DEFAULT_ACCT_STATE_UPGRADABLE")
        meta = d.get("metadata", {})
        notes.append(f"name={meta.get('name','?')} symbol={meta.get('symbol','?')}")
        if not flags:
            notes.append("contract:clean")
    else:
        notes.append("goplus:unavailable")
    rc = get(RUGCHECK.format(addr))
    time.sleep(1.5)
    rc_data = {}
    if "_error" not in rc and isinstance(rc, dict) and "score_normalised" in rc:
        rc_data = rc
        notes.append(f"rugcheck_score={rc.get('score_normalised')} lpLocked={rc.get('lpLockedPct')}%")
        for r in rc.get("risks", []):
            lvl = r.get("level")
            if lvl in ("danger", "warn"):
                flags.append(f"RC_{lvl.upper()}:{r.get('name','?')[:50]}")
    else:
        notes.append("rugcheck:unavailable")
    # top-10 holder concentration via RugCheck full report (empty for very fresh tokens)
    top10 = rc_top10_pct(addr)
    if top10 is not None:
        notes.append(f"top10_hold={top10:.1f}%")
        if top10 > 50:
            flags.append(f"TOP10_HEAVY:{top10:.0f}%")
        elif top10 > 30:
            flags.append(f"TOP10_CONCENTRATED:{top10:.0f}%")
    else:
        notes.append("top10:pending")
    return flags, notes, rc_data

def rc_top10_pct(mint):
    """Top-10 holder % excluding lockers/burns, from RugCheck full report. None if not indexed yet."""
    full = get(RUGCHECK_FULL.format(mint))
    time.sleep(1.5)
    if "_error" in full or not isinstance(full, dict):
        return None
    holders = full.get("topHolders") or []
    if not holders:
        return None
    top10, counted = 0.0, 0
    for h in holders:
        if counted >= 10:
            break
        if h.get("isLocker") or h.get("isBurned"):
            continue
        top10 += float(h.get("pct") or 0)
        counted += 1
    return top10

def audit_evm(chain_id, addr):
    flags, notes = [], []
    gp = get(GOPLUS_EVM.format(chain_id, addr))
    time.sleep(1.5)
    if "_error" not in gp and gp.get("code") == 1:
        d = gp["result"].get(addr.lower()) or gp["result"].get(addr) or {}
        truthy = lambda k: str(d.get(k, "0")) == "1"
        if truthy("is_honeypot"): flags.append("HONEYPOT")
        if truthy("is_mintable"): flags.append("MINTABLE")
        if truthy("can_take_back_ownership"): flags.append("TAKE_BACK_OWNERSHIP")
        if truthy("hidden_owner"): flags.append("HIDDEN_OWNER")
        if truthy("is_blacklisted"): flags.append("BLACKLIST_FUNC")
        if truthy("is_whitelisted"): flags.append("WHITELIST_FUNC")
        if truthy("cannot_sell_all"): flags.append("CANNOT_SELL_ALL")
        if truthy("cannot_buy"): flags.append("CANNOT_BUY")
        if truthy("selfdestruct"): flags.append("SELFDESTRUCT")
        if truthy("is_proxy"): flags.append("PROXY")
        if truthy("transfer_pausable"): flags.append("PAUSABLE")
        buy_tax = d.get("buy_tax"); sell_tax = d.get("sell_tax")
        try:
            if sell_tax is not None and float(sell_tax) > 0.10: flags.append(f"HIGH_SELL_TAX:{sell_tax}")
            if buy_tax is not None and float(buy_tax) > 0.10: flags.append(f"HIGH_BUY_TAX:{buy_tax}")
        except (TypeError, ValueError): pass
        try:
            hp = float(d.get("holder_count") or 0)
            notes.append(f"holders={int(hp)}")
        except (TypeError, ValueError): pass
        lp = d.get("lp_holder_count")
        notes.append(f"buy_tax={buy_tax} sell_tax={sell_tax}")
        if not flags: notes.append("contract:clean")
    else:
        notes.append("goplus:unavailable")
    return flags, notes, {}

def dex_snapshot(addr):
    """Best-pair liquidity/MC/price snapshot."""
    d = get(DEX_TOKENS.format(addr))
    time.sleep(1.0)
    if "_error" in d or not isinstance(d, dict):
        return {}
    pairs = d.get("pairs") or []
    if not pairs:
        return {}
    p = max(pairs, key=lambda x: (x.get("liquidity") or {}).get("usd") or 0)
    return {
        "price_usd": p.get("priceUsd"),
        "mcap": p.get("marketCap") or p.get("fdv"),
        "liq_usd": (p.get("liquidity") or {}).get("usd"),
        "pair": p.get("pairAddress"),
        "dex": p.get("dexId"),
        "txns_h1_buys": ((p.get("txns") or {}).get("h1") or {}).get("buys"),
        "txns_h1_sells": ((p.get("txns") or {}).get("h1") or {}).get("sells"),
        "vol_h1": (p.get("volume") or {}).get("h1"),
        "pair_created": p.get("pairCreatedAt"),
    }

def verdict(flags, rc_data):
    hard_danger = [f for f in flags if any(k in f for k in
        ("HONEYPOT", "MINTABLE", "FREEZABLE", "CLOSABLE", "NON_TRANSFERABLE",
         "CANNOT_SELL_ALL", "CANNOT_BUY", "RC_DANGER", "SELFDESTRUCT",
         "TAKE_BACK_OWNERSHIP", "HIDDEN_OWNER", "BALANCE_MUTABLE", "TOP10_HEAVY"))]
    warns = [f for f in flags if f not in hard_danger]
    if hard_danger:
        return "FAIL", hard_danger + warns
    if rc_data and (rc_data.get("score_normalised") or 0) >= 50:
        return "FAIL", [f"RC_SCORE:{rc_data.get('score_normalised')}"] + warns
    if warns:
        return "CAUTION", warns
    return "PASS", []

def run_cycle(state, max_audit=12):
    now = datetime.now(timezone.utc)
    profiles = get(DEX_PROFILES)
    if "_error" in profiles or not isinstance(profiles, list):
        print(f"[{now.isoformat()}] dexscreener poll failed: {profiles.get('_error')}")
        return 0
    boosts = get(DEX_BOOSTS)
    time.sleep(1.0)
    if isinstance(boosts, list):
        seen_addrs = {t.get("tokenAddress") for t in profiles}
        for b in boosts:
            if b.get("tokenAddress") not in seen_addrs:
                profiles.append(b)  # merge boosted tokens as supplementary source
    new_tokens = []
    for t in profiles:
        key = f"{t.get('chainId')}:{t.get('tokenAddress')}"
        if key not in state["seen"]:
            state["seen"][key] = {"first_seen": now.isoformat(), "audited": False}
            new_tokens.append(t)
    print(f"[{now.strftime('%H:%M:%S')}Z] poll: {len(profiles)} profiles+boosts, {len(new_tokens)} new")

    audited = 0
    lines = []
    for t in new_tokens:
        if audited >= max_audit:
            break
        chain, addr = t.get("chainId"), t.get("tokenAddress")
        key = f"{chain}:{addr}"
        snap = dex_snapshot(addr)
        if chain == "solana":
            flags, notes, rc = audit_solana(addr)
        elif chain in EVM_CHAIN_IDS:
            flags, notes, rc = audit_evm(EVM_CHAIN_IDS[chain], addr)
        else:
            flags, notes, rc = ["NO_AUDIT_ADAPTER"], [f"chain:{chain} no-audit-adapter"], {}
        if "NO_AUDIT_ADAPTER" in flags:
            v, vflags = "NO_AUDIT", flags
        elif "goplus:unavailable" in notes and ("rugcheck:unavailable" in notes or chain != "solana"):
            v, vflags = "UNKNOWN", ["AUDIT_UNAVAILABLE"]
        else:
            v, vflags = verdict(flags, rc)
        state["seen"][key].update({
            "audited": True, "verdict": v, "flags": vflags,
            "detect": snap, "chain": chain, "addr": addr,
            "history": [{"t": now.isoformat(), "price": snap.get("price_usd"), "mcap": snap.get("mcap")}],
        })
        # stage 3: behavioural audit (wallet layer) for Solana PASS candidates
        if v == "PASS" and chain == "solana":
            try:
                import behaviour
                b = behaviour.assess(addr)
                state["seen"][key]["behaviour"] = b
                notes.append(f"behaviour:{b.get('verdict')}({b.get('mode')})")
            except Exception as e:
                state["seen"][key]["behaviour"] = {"verdict": "SKIP", "mode": "error", "reason": str(e)[:80]}
        # stage 4: cluster tag (H09/H10) for all Solana tokens — are known
        # cluster wallets among the first buyers? Independent of audit verdict.
        if chain == "solana":
            try:
                import cluster_tag
                pc = (snap.get("pair_created") or 0) / 1000 or None
                ct = cluster_tag.tag(addr, pc, max_pages=4)
                state["seen"][key]["cluster"] = ct
                if ct.get("hit"):
                    notes.append(f"CLUSTER_HIT:{len(ct['hit'])}")
            except Exception as e:
                state["seen"][key]["cluster"] = {"error": str(e)[:80]}
        audited += 1
        desc = (t.get("description") or "").replace("\n", " ")[:80]
        lines.append(
            f"| {now.strftime('%H:%M')} | {chain} | `{addr[:8]}…` | {v} | "
            f"{'; '.join(vflags) if vflags else '—'} | "
            f"liq=${(snap.get('liq_usd') or 0):,.0f} mc=${(snap.get('mcap') or 0):,.0f} | "
            f"{'; '.join(notes)[:90]} | {desc} |"
        )
    if lines:
        header_needed = not WATCHLIST.exists()
        with WATCHLIST.open("a") as f:
            if header_needed:
                f.write("# Memecoin New-Listing Watchlist (audited)\n\n")
                f.write("| time(UTC) | chain | token | verdict | flags | liq/mcap | audit notes | desc |\n")
                f.write("|---|---|---|---|---|---|---|---|\n")
            f.write("\n".join(lines) + "\n")
    # update outcome tracking for previously audited tokens (batch, same chain only)
    # prioritize most recently detected so new tokens always get history
    sol_items = [(v.get("first_seen", ""), v["addr"]) for k, v in state["seen"].items()
                 if v.get("audited") and v.get("chain") == "solana" and v.get("detect")]
    sol_items.sort(reverse=True)
    sol_addrs = [a for _, a in sol_items[:60]]
    for i in range(0, min(len(sol_addrs), 60), 30):
        batch = sol_addrs[i:i+30]
        d = get(DEX_TOKENS.format(",".join(batch)))
        time.sleep(1.0)
        pairs_by_token = {}
        for p in (d.get("pairs") or []):
            ta = (p.get("baseToken") or {}).get("address")
            cur = pairs_by_token.get(ta)
            if not cur or ((p.get("liquidity") or {}).get("usd") or 0) > ((cur.get("liquidity") or {}).get("usd") or 0):
                pairs_by_token[ta] = p
        for k, v in state["seen"].items():
            if v.get("chain") == "solana" and v.get("addr") in pairs_by_token:
                p = pairs_by_token[v["addr"]]
                v.setdefault("history", []).append({
                    "t": now.isoformat(), "price": p.get("priceUsd"),
                    "mcap": p.get("marketCap") or p.get("fdv")})
    # backfill top-10 holder concentration for tokens that were too fresh at detection
    backfilled = 0
    for k, v in state["seen"].items():
        if backfilled >= 3:
            break
        if (v.get("chain") == "solana" and v.get("audited") and "top10" not in v
                and v.get("verdict") in ("PASS", "CAUTION")):
            t10 = rc_top10_pct(v["addr"])
            if t10 is not None:
                v["top10"] = round(t10, 1)
                if t10 > 50:
                    v["verdict"] = "FAIL"
                    v.setdefault("flags", []).append(f"TOP10_HEAVY:{t10:.0f}%(late)")
                elif t10 > 30:
                    if v["verdict"] == "PASS":
                        v["verdict"] = "CAUTION"
                    v.setdefault("flags", []).append(f"TOP10_CONCENTRATED:{t10:.0f}%(late)")
                backfilled += 1
    # cluster re-tag (§21 coverage fix): tokens tagged with thin/partial
    # first-buyer data at detection get ONE re-tag once >=15 min old
    retagged = 0
    for k, v in state["seen"].items():
        if retagged >= 1:
            break
        cl = v.get("cluster") or {}
        if (v.get("chain") == "solana" and v.get("audited") and cl
                and not cl.get("error") and not cl.get("retagged")
                and (not cl.get("reached_birth") or (cl.get("first_buyers") or 0) < 5)
                and not cl.get("hit")
                and v.get("history")):
            try:
                age_min = (now - datetime.fromisoformat(v["history"][0]["t"])).total_seconds() / 60
            except Exception:
                continue
            if age_min >= 15:
                try:
                    import cluster_tag
                    pc = ((v.get("detect") or {}).get("pair_created") or 0) / 1000 or None
                    ct = cluster_tag.tag(v["addr"], pc)
                    ct["retagged"] = True
                    v["cluster"] = ct
                    retagged += 1
                except Exception:
                    pass
    return audited

def main():
    cycles = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    interval = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    max_audit = int(sys.argv[3]) if len(sys.argv) > 3 else 12
    state = load_state()
    for c in range(cycles):
        state["runs"] += 1
        n = run_cycle(state, max_audit=max_audit)
        save_state(state)
        print(f"  cycle done, {n} audited, total tracked={len(state['seen'])}")
        if c < cycles - 1:
            time.sleep(interval)

if __name__ == "__main__":
    main()
