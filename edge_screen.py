#!/usr/bin/env python3
"""edge_screen.py — the research checklist as one pre-entry score.

Implements the "60-second drill" + 7-signal screen from
memecoin-research/05-synthesis.md by unifying the existing forensic
components into a single PASS / WATCH / AVOID verdict with reasons.

Checks (research source in brackets):
  1. creator blacklist cross-ref        [P3: serial deployers]
  2. birth-window bundle share           [P3: >20-30% = engineered]
  3. insider overhang (v2 classifier)    [P3: >30% cluster = avoid]
  4. mintable / freezable authority      [P2: mandatory contract check]
  5. top-1 / top-5 holder concentration  [P3: >30% = avoid]
  6. holder-count floor                  [P1: >=7 holders cheat sheet]
  7. age / mcap floors                   [P1: 40-60min, >=15K MC]

Hard fail on any AVOID check => AVOID. Any watch => WATCH. Else PASS.

Usage:
  python3 edge_screen.py <mint> [--deployer <addr>] [--mcap-sol N]
                         [--age-min N] [--json]
Appends every verdict to edge_screen_log.jsonl.
"""
import argparse
import base64
import json
import sys
import time
from pathlib import Path

MON = Path(__file__).resolve().parent
sys.path.insert(0, str(MON))

from bundle_share import bundle_share            # noqa: E402
from insider_screen_v2 import screen_v2, rpc     # noqa: E402

BLACKLIST = MON / "mfg_creator_blacklist.jsonl"
DENYLISTS = [MON / "creator_denylist.json", MON / "farm_denylist.json",
             MON / "drainer_blocklist.json", MON / "paper_denylist.json"]
BIRTHS = MON / "mfg_armed_births.jsonl"
TOKENS = MON / "mfg_tokens.jsonl"
LOG = MON / "edge_screen_log.jsonl"
SUPPLY = 1_000_000_000


def autofill(mint):
    """Fill deployer / mcap_sol / age_min from the local data plane.
    Returns (deployer, mcap_sol, age_min, source_note)."""
    deployer, mcap_sol, age_min = None, None, None
    if BIRTHS.exists():  # small file, full scan fine
        for line in BIRTHS.open():
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("mint") == mint:
                deployer = r.get("creator")
                break
    if TOKENS.exists():  # 44MB stream; keep latest record for the mint
        latest = None
        for line in TOKENS.open():
            if mint not in line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("mint") == mint:
                latest = r
        if latest:
            deployer = deployer or latest.get("creator")
            mcap_sol = latest.get("mcap_sol")
            if latest.get("age_s"):
                age_min = round(latest["age_s"] / 60, 1)
    src = "local data plane" if (deployer or mcap_sol) else "not tracked locally"
    return deployer, mcap_sol, age_min, src

# research thresholds (05-synthesis.md)
BUNDLE_OK, BUNDLE_AVOID = 5.0, 20.0
OVERHANG_OK, OVERHANG_AVOID = 15.0, 30.0
TOP1_OK, TOP1_AVOID = 15.0, 30.0
TOP5_AVOID = 50.0
MIN_HOLDERS = 7

# screen profiles — forensic checks (bundle/overhang/authorities/
# concentration/blacklist) are IDENTICAL in all profiles; only the
# age/mcap floor lane checks differ.
PROFILES = {
    "default": {"age_floor_min": 40.0, "mcap_floor_sol": 150.0},
    # sub-30m PumpSwap lane (exec_dry entry lane): the 40min age floor
    # would WATCH every candidate by definition — waived; mcap floor
    # softened to 40 SOL.
    "early_pumpswap": {"age_floor_min": None, "mcap_floor_sol": 40.0},
}

SCREEN_CACHE = MON / "screen_cache.json"

# program-owned vaults must be excluded from concentration reads —
# otherwise every live bonding curve false-positives at ~79%
VAULT_PROGS = {"6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",   # pump.fun curve
               "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA",   # PumpSwap AMM
               }


def _b58(b):
    alpha = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = int.from_bytes(b, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = alpha[r] + out
    pad = 0
    for c in b:
        if c == 0:
            pad += 1
        else:
            break
    return "1" * pad + (out or "")


def _load_denylists():
    bad = set()
    for p in DENYLISTS:
        if not p.exists():
            continue
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        if isinstance(d, list):
            bad.update(x if isinstance(x, str) else x.get("creator", "")
                       for x in d)
        elif isinstance(d, dict):
            bad.update(d.keys())
    return {x for x in bad if x}


def _blacklisted_creators():
    out = set()
    if BLACKLIST.exists():
        for line in BLACKLIST.open():
            try:
                out.add(json.loads(line)["creator"])
            except Exception:
                continue
    return out


def mint_authorities(mint):
    """(mintable, freezable) via parsed mint account."""
    r = rpc("getAccountInfo", [mint, {"encoding": "jsonParsed"}]).get("result")
    info = (((r or {}).get("value") or {}).get("data") or {}).get("parsed", {}) \
        .get("info", {})
    return info.get("mintAuthority") is not None, \
        info.get("freezeAuthority") is not None


def holder_concentration(mint):
    """(top1_pct, top5_pct, n_accounts, vault_pct) — vault accounts
    (bonding curve / AMM pools) excluded from concentration."""
    la = rpc("getTokenLargestAccounts", [mint]).get("result", {}).get("value", [])
    if not la:
        return None, None, 0, None
    s = rpc("getTokenSupply", [mint]).get("result", {}).get("value", {})
    supply = float(s.get("amount", 0))
    if not supply:
        return None, None, len(la), None
    addrs = [a["address"] for a in la]
    owners_r = rpc("getMultipleAccounts", [addrs, {"encoding": "base64"}])
    owner_of = {}
    for addr, acc in zip(addrs, (owners_r.get("result") or {}).get("value", [])):
        if acc and acc.get("data"):
            raw = base64.b64decode(acc["data"][0])
            owner_of[addr] = _b58(raw[32:64])
    uniq = sorted(set(owner_of.values()))
    prog_of = {}
    if uniq:
        o_r = rpc("getMultipleAccounts", [uniq])
        for ow, acc in zip(uniq, (o_r.get("result") or {}).get("value", [])):
            prog_of[ow] = (acc or {}).get("owner")
    rows = []
    vault_pct = 0.0
    for a in la:
        share = float(a["amount"]) / supply * 100
        ow = owner_of.get(a["address"])
        if prog_of.get(ow) in VAULT_PROGS:
            vault_pct += share
            continue
        rows.append((share, ow))
    rows.sort(reverse=True)
    shares = [s for s, _ in rows]
    top1 = round(shares[0], 2) if shares else 0.0
    top5 = round(sum(shares[:5]), 2)
    return top1, top5, len(rows), round(vault_pct, 2)


def _cache_get(mint, profile, ttl):
    if ttl <= 0 or not SCREEN_CACHE.exists():
        return None
    try:
        c = json.loads(SCREEN_CACHE.read_text())
    except Exception:
        return None
    rec = c.get(f"{mint}:{profile}")
    if rec and time.time() - rec.get("t", 0) < ttl:
        r = dict(rec)
        r["cached"] = True
        return r
    return None


def _cache_put(mint, profile, rec):
    try:
        c = json.loads(SCREEN_CACHE.read_text()) if SCREEN_CACHE.exists() else {}
    except Exception:
        c = {}
    c[f"{mint}:{profile}"] = rec
    # bound the file: drop entries older than 24h
    cut = time.time() - 86400
    c = {k: v for k, v in c.items() if v.get("t", 0) > cut}
    try:
        SCREEN_CACHE.write_text(json.dumps(c))
    except Exception:
        pass


def screen(mint, deployer=None, mcap_sol=None, age_min=None,
           profile="default", ttl=300):
    """Full pre-entry screen. Results cached per mint+profile for `ttl`
    seconds (default 300) so polling loops (exec_dry every ~1min) don't
    re-hit Helius on the same mint. Cached returns are NOT re-logged.
    Pass ttl=0 when inputs (deployer/mcap/age) change meaningfully."""
    cached = _cache_get(mint, profile, ttl)
    if cached is not None:
        return cached
    prof = PROFILES.get(profile, PROFILES["default"])
    t0 = time.time()
    checks, verdicts = [], []

    def add(name, value, verdict, note=""):
        checks.append({"check": name, "value": value,
                       "verdict": verdict, "note": note})
        verdicts.append(verdict)

    # 1. creator history
    if deployer:
        bl = _blacklisted_creators() | _load_denylists()
        add("creator_blacklist", deployer[:12] + "…",
            "AVOID" if deployer in bl else "PASS",
            "creator has prior losing/rug launches" if deployer in bl else "")
    else:
        add("creator_blacklist", None, "WATCH", "no deployer supplied")

    # 2. bundle share at birth (network). Prefer the NET share (§333:
    # create-tx platform allocations stripped); raw outsider_pct can
    # exceed 100% from the constant 20.69pp platform-reserve offset.
    b = bundle_share(mint, deployer)
    bpct = (b or {}).get("outsider_pct_net")
    if bpct is None:
        bpct = (b or {}).get("outsider_pct")
    if bpct is None:
        add("bundle_share", (b or {}).get("error"), "WATCH", "bundle unknown")
    else:
        v = "PASS" if bpct < BUNDLE_OK else ("AVOID" if bpct >= BUNDLE_AVOID
                                             else "WATCH")
        add("bundle_share", bpct, v,
            f"{(b or {}).get('n_buyers')} birth-window buyers")

    # 3. insider overhang (creation-transfer classifier)
    try:
        ov = screen_v2(mint)
        opct = ov.get("overhang_v2_pct")
        if opct is None and "error" in ov:
            add("insider_overhang", ov["error"], "WATCH", "classifier: no data")
    except Exception as e:
        ov, opct = {}, None
        add("insider_overhang", str(e)[:60], "WATCH", "classifier error")
    if opct is not None:
        v = "PASS" if opct < OVERHANG_OK else ("AVOID" if opct >= OVERHANG_AVOID
                                               else "WATCH")
        add("insider_overhang", opct, v, f"classified {ov.get('classified')}")

    # 4. authorities
    try:
        mintable, freezable = mint_authorities(mint)
        add("authorities", {"mintable": mintable, "freezable": freezable},
            "AVOID" if (mintable or freezable) else "PASS")
    except Exception as e:
        add("authorities", str(e)[:60], "WATCH", "rpc error")

    # 5/6. holder concentration + count
    try:
        top1, top5, n, vault_pct = holder_concentration(mint)
        if top1 is None:
            add("holder_concentration", None, "WATCH", "no supply data")
        else:
            v1 = "PASS" if top1 < TOP1_OK else ("AVOID" if top1 >= TOP1_AVOID
                                                else "WATCH")
            v = v1 if top5 < TOP5_AVOID else "AVOID"
            add("holder_concentration",
                {"top1_pct": top1, "top5_pct": top5, "vault_pct": vault_pct}, v,
                "curve/AMM vault excluded")
        add("holder_count", n, "PASS" if n >= MIN_HOLDERS else "WATCH",
            "non-vault largest accounts")
    except Exception as e:
        add("holder_concentration", str(e)[:60], "WATCH", "rpc error")

    # 7. age / mcap floors (profile-scoped lane checks; forensic checks above
    # are identical across profiles)
    if age_min is not None:
        floor = prof["age_floor_min"]
        if floor is None:
            add("age_min", age_min, "PASS",
                f"{profile} lane: age floor waived (info only)")
        else:
            add("age_min", age_min, "PASS" if age_min >= floor else "WATCH",
                f"<{floor:.0f}min = fresh-scam window")
    if mcap_sol is not None:
        floor = prof["mcap_floor_sol"]
        add("mcap_sol", mcap_sol, "PASS" if mcap_sol >= floor else "WATCH",
            f"below ~{floor:.0f} SOL MC most coins fail"
            if profile == "default" else f"{profile} soft floor")

    final = "AVOID" if "AVOID" in verdicts else \
            ("WATCH" if "WATCH" in verdicts else "PASS")
    rec = {"t": time.time(), "mint": mint, "verdict": final,
           "profile": profile, "checks": checks,
           "elapsed_s": round(time.time() - t0, 1)}
    with LOG.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    _cache_put(mint, profile, rec)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mint")
    ap.add_argument("--deployer")
    ap.add_argument("--mcap-sol", type=float)
    ap.add_argument("--age-min", type=float)
    ap.add_argument("--no-auto", action="store_true",
                    help="skip autofill from local data plane")
    ap.add_argument("--profile", choices=sorted(PROFILES), default="default",
                    help="early_pumpswap waives the 40min age floor and "
                         "softens the mcap floor for the sub-30m lane")
    ap.add_argument("--ttl", type=float, default=300,
                    help="screen result cache seconds (0 = always fresh)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    note = None
    if not a.no_auto and not (a.deployer and a.mcap_sol and a.age_min):
        dep, mc, ag, note = autofill(a.mint)
        a.deployer = a.deployer or dep
        a.mcap_sol = a.mcap_sol if a.mcap_sol is not None else mc
        a.age_min = a.age_min if a.age_min is not None else ag
    r = screen(a.mint, a.deployer, a.mcap_sol, a.age_min,
               profile=a.profile, ttl=a.ttl)
    if a.json:
        print(json.dumps(r, indent=1))
        return
    if note:
        print(f"autofill: {note} (deployer={'yes' if a.deployer else 'no'}, "
              f"mcap={a.mcap_sol}, age_min={a.age_min})")
    tag = "  [cached]" if r.get("cached") else ""
    print(f"\n{r['mint'][:16]}…  VERDICT: {r['verdict']}  "
          f"({r['elapsed_s']}s){tag}  profile={r.get('profile', 'default')}")
    for c in r["checks"]:
        mark = {"PASS": "✓", "WATCH": "~", "AVOID": "✗"}[c["verdict"]]
        print(f"  {mark} {c['check']:<22} {str(c['value']):<38} {c['note']}")


if __name__ == "__main__":
    main()
