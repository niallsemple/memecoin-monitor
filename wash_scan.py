#!/usr/bin/env python3
"""wash_scan.py — auto-forensics for hot tape pools.

Reads the latest txflow.jsonl row per pool; for any pool in the top-5 by
swaps_5m with NO verdict in pool_wash_cache.json, runs swap_forensics-style
sampling (15 txs). Wash verdict -> appended to paper_denylist.json.
Runs cheap: only uncached hot pools, ~15 getTransaction calls each.

Usage: python3 wash_scan.py
"""
import json, os, time, urllib.request, collections

MON = os.path.dirname(os.path.abspath(__file__))
KEY = open(os.path.join(MON, "helius_key.txt")).read().strip()
URL = f"https://mainnet.helius-rpc.com/?api-key={KEY}"
CACHE = os.path.join(MON, "pool_wash_cache.json")
DENY = os.path.join(MON, "paper_denylist.json")

def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params}).encode()
    req = urllib.request.Request(URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()).get("result")

def forensic(pool, n=15):
    sigs = rpc("getSignaturesForAddress", [pool, {"limit": 100}]) or []
    ok = [s["signature"] for s in sigs if s.get("err") is None][:n]
    payers = collections.Counter()
    deltas = []
    for sig in ok:
        try:
            tx = rpc("getTransaction", [sig, {"encoding": "json",
                                              "maxSupportedTransactionVersion": 0}])
        except Exception:
            continue
        if not tx:
            continue
        payer = tx["transaction"]["message"]["accountKeys"][0]
        if isinstance(payer, dict):
            payer = payer.get("pubkey", str(payer))
        payers[payer] += 1
        meta = tx.get("meta") or {}
        pre, post = meta.get("preBalances", []), meta.get("postBalances", [])
        if pre and post:
            deltas.append(abs(post[0] - pre[0]) / 1e9)
    total = sum(payers.values())
    if total < 5:
        return "unknown", total
    top = payers.most_common(1)[0][1] / total
    if len(payers) <= 3 or top > 0.5:
        return "wash", total
    # dust-cycling check: diverse payer COUNT but no real size on the tape.
    # Calibrated 2026-09-13: 9Ndi (confirmed organic payer) median 5.8e-4,
    # max 7.1 SOL; confirmed wash pools median ~6e-6, max <0.01.
    if deltas:
        import statistics
        if statistics.median(deltas) < 0.0001 and max(deltas) < 0.01:
            return "wash", total
    return "organic", total

def main():
    # latest tape row per pool
    latest = {}
    for line in open(os.path.join(MON, "txflow.jsonl")):
        try:
            r = json.loads(line)
        except Exception:
            continue
        latest[r["pool"]] = r
    hot = sorted(latest.values(), key=lambda r: -r["swaps_5m"])[:5]
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    deny = json.load(open(DENY))
    for r in hot:
        p = r["pool"]
        if p in cache:
            continue
        verdict, n = forensic(p)
        cache[p] = {"verdict": verdict, "t": time.time(), "n": n,
                    "swaps_5m_at_scan": r["swaps_5m"]}
        print(f"scan {p[:8]}: {verdict} (n={n}, tape={r['swaps_5m']})")
        if verdict == "wash" and p not in deny["pools"]:
            deny["pools"].append(p)
            print(f"  -> denylisted {p[:8]}")
        time.sleep(0.5)
    json.dump(cache, open(CACHE, "w"), indent=1)
    json.dump(deny, open(DENY, "w"), indent=1)
    if not any(r["pool"] not in cache for r in hot):
        pass

if __name__ == "__main__":
    main()
