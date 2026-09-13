#!/usr/bin/env python3
"""pool_txflow.py — claim-immune burst meter via Helius enhanced transactions.

prot_fee counters get zeroed by fee claims (see DEADFILL_ANALYSIS.md addendum
2), so gates built on them undercount bursts. This polls Helius for recent
transactions per tracked pool, counts SWAP-type txs in trailing windows, and
appends to txflow.jsonl:
  {t, pool, swaps_1m, swaps_5m, swaps_10m, new_sigs}
Universe: same hot set as bin_collector (top-8 fee velocity + watchlist +
open positions). One Helius call per pool per run (~15 calls/run).
"""
import json, os, time, urllib.request, collections

MON = os.path.dirname(os.path.abspath(__file__))
KEY = open(os.path.join(MON, "helius_key.txt")).read().strip()
OUT = os.path.join(MON, "txflow.jsonl")
SEEN = os.path.join(MON, "txflow_seen.json")
SNAP = os.path.join(MON, "meteora_fee_snapshots.jsonl")
TOP_N = 8

def hot_pools(now):
    last2 = collections.defaultdict(list)
    with open(SNAP) as f:
        for l in f:
            try:
                r = json.loads(l)
            except Exception:
                continue
            if r.get("pool") and r.get("cum_fees") is not None and r.get("t"):
                last2[r["pool"]].append((r["t"], r["cum_fees"]))
    vel = {}
    for p, rows in last2.items():
        rows.sort()
        for (t1, c1), (t2, c2) in zip(rows[-2:-1], rows[-1:]):
            if t2 > t1 and c2 >= c1 and t2 > now - 6 * 3600:
                vel[p] = (c2 - c1) / ((t2 - t1) / 60)
    return [p for p, _ in sorted(vel.items(), key=lambda kv: -kv[1])[:TOP_N]]

def fetch_swaps(pool):
    """RPC getSignaturesForAddress: [{signature, blockTime, err}], newest first.
    Pool accounts see almost exclusively swap txs; failed txs excluded."""
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "getSignaturesForAddress",
        "params": [pool, {"limit": 1000}],
    }).encode()
    url = f"https://mainnet.helius-rpc.com/?api-key={KEY}"
    try:
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            res = json.loads(r.read()).get("result", [])
        return [{"signature": x["signature"], "timestamp": x.get("blockTime") or 0}
                for x in res if x.get("err") is None]
    except Exception as e:
        print(f"  txflow fail {pool[:8]}: {str(e)[:60]}")
        return None

def main():
    now = time.time()
    pools = hot_pools(now)
    try:
        for wp in json.load(open(os.path.join(MON, "hfna_watchlist.json")))["pools"]:
            if wp not in pools:
                pools.append(wp)
    except Exception:
        pass
    seen = {}
    if os.path.exists(SEEN):
        seen = json.load(open(SEEN))
    rows = []
    for p in pools:
        txs = fetch_swaps(p)
        if txs is None:
            continue
        known = set(seen.get(p, []))
        new = [tx for tx in txs if tx.get("signature") not in known]
        ts = [tx.get("timestamp", 0) for tx in txs]
        rows.append({
            "t": now, "pool": p,
            "swaps_1m": sum(1 for x in ts if x > now - 60),
            "swaps_5m": sum(1 for x in ts if x > now - 300),
            "swaps_10m": sum(1 for x in ts if x > now - 600),
            "new_sigs": len(new),
        })
        # keep recent sigs bounded
        sigs = [tx.get("signature") for tx in txs if tx.get("timestamp", 0) > now - 1200]
        seen[p] = list(dict.fromkeys(sigs + list(known)))[:300]
    with open(OUT, "a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    json.dump(seen, open(SEEN, "w"))
    hot = sorted(rows, key=lambda r: -r["swaps_5m"])[:4]
    print(f"txflow: {len(rows)} pools | top 5m swaps: "
          + ", ".join(f"{r['pool'][:8]}={r['swaps_5m']}" for r in hot))

if __name__ == "__main__":
    main()
