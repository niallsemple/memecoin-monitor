#!/usr/bin/env python3
"""
deployer_safety.py — on-chain pre-entry safety gate for newborn PumpSwap
tokens. The atomic-rug study (REPORT.md 2026-09-08) showed our rugs are
deployer DUMPS (supply concentration), not LP pulls — PumpSwap LP is
program-held. So the gate measures:

  mintable     — mintAuthority not revoked (deployer can print infinite supply)
  freezable    — freezeAuthority not revoked (deployer can freeze holder accts)
  top1_share   — largest non-vault holder's share of supply (the dump risk)
  top5_share   — top-5 non-vault concentration
  vault_share  — pool vault share (healthy pool share reference)

Method: getAccountInfo(mint, jsonParsed) for authorities;
getTokenLargestAccounts(mint) for concentration; the pool vault is identified
as the largest account (per pool_reserve_poller's validated assumption) and
EXCLUDED from holder-concentration numbers.

Usage:
  python3 deployer_safety.py MINT [MINT...]   # one-shot check
  python3 deployer_safety.py --hot            # check current hot watchlist

Appends to deployer_safety.jsonl: {t, mint, name, mintable, freezable,
top1_share, top5_share, vault_share, n_accounts}
"""
import json, os, sys, time, urllib.request

MON = os.path.dirname(os.path.abspath(__file__))
KEYF = os.path.join(MON, "helius_key.txt")
PAIRS = os.path.join(MON, "pumpswap_pairs.json")
SNAP = os.path.join(MON, "pumpswap_snapshots.jsonl")
OUT = os.path.join(MON, "deployer_safety.jsonl")
RPC_TIMEOUT = 15


def rpc(key, method, params):
    url = f"https://mainnet.helius-rpc.com/?api-key={key}"
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params}).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=RPC_TIMEOUT) as r:
        return json.loads(r.read()).get("result")


def check_mint(key, mint):
    info = rpc(key, "getAccountInfo", [mint, {"encoding": "jsonParsed"}])
    parsed = (((info or {}).get("value") or {}).get("data") or {}).get("parsed") or {}
    mi = parsed.get("info") or {}
    supply = float(mi.get("supply") or 0)
    decimals = mi.get("decimals") or 0
    mintable = mi.get("mintAuthority") is not None
    freezable = mi.get("freezeAuthority") is not None
    lacct = rpc(key, "getTokenLargestAccounts", [mint]) or {}
    vals = lacct.get("value") or []
    if not vals or supply <= 0:
        return None
    # largest account = pool vault (validated assumption for newborn pumpswap)
    vault = vals[0]
    vault_share = float(vault.get("amount") or 0) / supply
    holders = [v for v in vals[1:]]
    top1 = float(holders[0].get("amount") or 0) / supply if holders else 0.0
    top5 = sum(float(v.get("amount") or 0) for v in holders[:5]) / supply
    return {"mintable": mintable, "freezable": freezable,
            "supply_ui": supply / (10 ** decimals),
            "vault_share": round(vault_share, 4),
            "top1_share": round(top1, 4), "top5_share": round(top5, 4),
            "n_accounts": len(vals)}


def hot_mints(now, max_age_h=6.0, min_liq=25000.0, cap=15):
    try:
        pairs = json.load(open(PAIRS))
    except Exception:
        return {}
    latest = {}
    if os.path.exists(SNAP):
        for l in open(SNAP):
            try:
                r = json.loads(l)
            except Exception:
                continue
            if r.get("mint"):
                latest[r["mint"]] = r
    out = {}
    for mint, p in pairs.items():
        if p.get("dex") != "pumpswap":
            continue
        if (now - p.get("born_t", now)) / 3600 > max_age_h:
            continue
        s = latest.get(mint)
        if not s or (s.get("liq") or 0) < min_liq:
            continue
        out[mint] = {"name": p.get("name"), "liq": s.get("liq") or 0}
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["liq"])[:cap])


def main():
    key = open(KEYF).read().strip()
    now = time.time()
    if "--hot" in sys.argv:
        targets = hot_mints(now)
    else:
        targets = {m: {"name": None} for m in sys.argv[1:] if not m.startswith("-")}
    if not targets:
        print("no targets")
        return
    with open(OUT, "a") as f:
        for mint, meta in targets.items():
            try:
                r = check_mint(key, mint)
            except Exception as e:
                print(f"{mint[:12]}… rpc fail: {e}", file=sys.stderr)
                continue
            if not r:
                print(f"{(meta['name'] or mint[:12])}: no data")
                continue
            row = {"t": now, "mint": mint, "name": meta.get("name"), **r}
            f.write(json.dumps(row) + "\n")
            danger = []
            if r["mintable"]: danger.append("MINTABLE")
            if r["freezable"]: danger.append("FREEZABLE")
            if r["top1_share"] > 0.20: danger.append(f"top1={r['top1_share']*100:.0f}%")
            tag = ("  <-- " + ",".join(danger)) if danger else ""
            print(f"{(meta['name'] or '?')[:16]:<18} vault={r['vault_share']*100:5.1f}% "
                  f"top1={r['top1_share']*100:5.1f}% top5={r['top5_share']*100:5.1f}% "
                  f"mint={'Y' if r['mintable'] else 'n'} freeze={'Y' if r['freezable'] else 'n'}{tag}")


if __name__ == "__main__":
    main()
