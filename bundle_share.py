#!/usr/bin/env python3
"""bundle_share.py — how much supply did non-deployer wallets grab at birth?

For a mint: find creation time, pull all mint txs within the first WINDOW_S
seconds, sum token deltas for wallets other than the deployer, express as
% of 1e9 supply. High first-window outsider share = bundled launch.
"""
import json, time, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from deployer_score import rpc

SUPPLY = 1_000_000_000
WINDOW_S = 30  # first 30 seconds of life
CACHE_V = 2    # bump when accumulation logic changes; stale entries recompute


def _amt(b):
    ta = b["uiTokenAmount"]
    dec = ta.get("decimals", 6)
    return float(ta.get("amount", "0")) / (10 ** dec)


def bundle_share(mint, deployer=None, window_s=WINDOW_S):
    # cache: birth-window share never changes — reuse across paths/runs
    cache_p = Path(__file__).parent / "bundle_cache.json"
    try:
        cache = json.load(open(cache_p)) if cache_p.exists() else {}
    except Exception:
        cache = {}
    if mint in cache and cache[mint].get("v") == CACHE_V:
        return cache[mint]
    # §265: paginate BACKWARD to the true birth. limit-100 newest-only
    # silently measured the wrong window on any mint with >100 txs,
    # passing bundled launches (7vEVYhk5: 61.6% at birth, 0.0% at +70min).
    sigs, before = [], None
    for _attempt in range(3):  # entry-time races RPC indexing; retry empty
        for _ in range(30):  # up to 3000 sigs, newest-first
            params = [mint, {"limit": 100}]
            if before:
                params[1]["before"] = before
            page = rpc("getSignaturesForAddress", params) or []
            if not page:
                break
            sigs += page
            before = page[-1]["signature"]
            if len(page) < 100:
                break
        if sigs:
            break
        time.sleep(3)
    if not sigs:
        return None
    if len(sigs) >= 3000:
        # birth still not reached — ambiguous, caller sees None share
        return {"outsider_pct": None, "error": "birth beyond 3000-sig window"}
    birth = min(s["blockTime"] for s in sigs if s.get("blockTime"))
    early = [s for s in sigs if s.get("blockTime") and
             s["blockTime"] - birth <= window_s]
    early.sort(key=lambda s: s["blockTime"])  # chronological: create first
    acquired = {}      # owner -> tokens bought FROM THE CURVE in window
    curve_owner = None
    create_found = False
    for s in early:
        tx = rpc("getTransaction", [s["signature"], {
                 "encoding": "jsonParsed",
                 "maxSupportedTransactionVersion": 0}])
        if not tx or not tx.get("meta"):
            continue
        pre = {b["owner"]: _amt(b)
               for b in tx["meta"].get("preTokenBalances", [])
               if b.get("mint") == mint and b.get("owner")}
        post = {b["owner"]: _amt(b)
                for b in tx["meta"].get("postTokenBalances", [])
                if b.get("mint") == mint and b.get("owner")}
        deltas = {o: a - pre.get(o, 0) for o, a in post.items()}
        # §334: create-tx detection by FULL-SUPPLY distribution (>900M
        # positive deltas), not by deployer delta — the curve's 793.1M
        # inventory is credited to the curve vault owner, not the creator
        # (the old >700M deployer heuristic silently never fired, leaving
        # the constant ~100pp create allocation + reserve re-distribution
        # inside outsider_pct, which is how it printed 202-209%).
        pos_sum = sum(d for d in deltas.values() if d > 0)
        if pos_sum > 900_000_000:
            create_found = True
            curve_owner = max(deltas, key=lambda o: deltas[o])
            continue  # supply distribution, not demand
        # §334: count only acquisitions FROM THE CURVE (curve balance
        # decreased this tx). Wallet-to-wallet shuffles after the create
        # (platform reserve -> MM accounts) otherwise double-count supply.
        if curve_owner is not None and deltas.get(curve_owner, 0) >= 0:
            continue
        for owner, delta in deltas.items():
            if delta > 0 and owner != curve_owner:
                acquired[owner] = acquired.get(owner, 0) + delta
        time.sleep(0.05)
    outsider = sum(v for k, v in acquired.items() if k != deployer)
    deployer_amt = acquired.get(deployer, 0) if deployer else 0
    res = {
        "v": CACHE_V,
        "birth": birth, "txs_in_window": len(early),
        "outsider_pct": round(100 * outsider / SUPPLY, 2),
        "deployer_pct": round(100 * deployer_amt / SUPPLY, 2),
        "n_buyers": len(acquired),
        "buyers": sorted(acquired),  # §289: winner-wallet registry cross-ref
        "curve_owner": curve_owner,
        "create_found": create_found,
        # kept for edge_screen compatibility — identical to outsider_pct
        # now that curve-only accounting IS the net measure
        "outsider_pct_net": round(100 * outsider / SUPPLY, 2),
        "n_buyers_net": len(acquired),
    }
    try:
        cache[mint] = res
        json.dump(cache, open(cache_p, "w"), indent=1)
    except Exception:
        pass
    return res


if __name__ == "__main__":
    mint = sys.argv[1]
    dep = sys.argv[2] if len(sys.argv) > 2 else None
    print(json.dumps(bundle_share(mint, dep), indent=1))
