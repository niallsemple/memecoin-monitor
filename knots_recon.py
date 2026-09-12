#!/usr/bin/env python3
"""KNOTS swap-truth reconstruction — phase 1: authoritative transaction set.

Window: wide_arm_v3 LP-active period (2026-09-11 22:30:22 -> 2026-09-12 07:02:00).
Source of truth: raw signatures via RPC getSignaturesForAddress (paginated),
then raw jsonParsed transactions. Nothing interpreted yet — ground truth only.

Outputs:
  knots_sigs.jsonl  — {sig, slot, blockTime} for every tx touching the pool
  knots_txs.jsonl   — raw transaction payloads (jsonParsed)
"""
import json, os, time, urllib.request

MON = os.path.dirname(os.path.abspath(__file__))
POOL = "nBXytBBfKLhj6teXarAv8rk6WNgUFBMyybUFRkuK7ad"
T0 = 1789156222.0   # deploy 22:30:22
T1 = 1789186920.0   # exit 07:02:00
KEY = open(os.path.join(MON, "helius_key.txt")).read().strip()
RPC = f"https://mainnet.helius-rpc.com/?api-key={KEY}"

def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(RPC, data=body, headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

def main():
    # phase 1: signatures
    sigs, before = [], None
    while True:
        params = [POOL, {"limit": 1000}]
        if before:
            params[1]["before"] = before
        r = rpc("getSignaturesForAddress", params)
        batch = r.get("result") or []
        if not batch:
            break
        sigs.extend(batch)
        oldest = batch[-1]
        print(f"  sigs so far {len(sigs)}, oldest blockTime {time.strftime('%H:%M:%S', time.localtime(oldest['blockTime']))}")
        if oldest["blockTime"] < T0 - 3600:
            break
        before = oldest["signature"]
        time.sleep(0.15)
    # filter to window with 1h margin on each side for context
    keep = [s for s in sigs if T0 - 3600 <= s["blockTime"] <= T1 + 600]
    with open(os.path.join(MON, "knots_sigs.jsonl"), "w") as f:
        for s in keep:
            f.write(json.dumps({"sig": s["signature"], "slot": s["slot"],
                                "blockTime": s["blockTime"]}) + "\n")
    print(f"phase 1 done: {len(sigs)} total, {len(keep)} in window+context -> knots_sigs.jsonl")

if __name__ == "__main__":
    main()

def fetch_txs(batch=100):
    """Phase 2: resumable raw-tx fetch via batched JSON-RPC."""
    out_f = os.path.join(MON, "knots_txs.jsonl")
    done = set()
    if os.path.exists(out_f):
        for ln in open(out_f):
            try: done.add(json.loads(ln)["sig"])
            except Exception: pass
    sigs = [json.loads(l) for l in open(os.path.join(MON, "knots_sigs.jsonl"))]
    todo = [s for s in sigs if s["sig"] not in done]
    print(f"phase 2: {len(done)} already fetched, {len(todo)} to go")
    f = open(out_f, "a")
    n = 0
    for i in range(0, len(todo), batch):
        chunk = todo[i:i+batch]
        reqs = [{"jsonrpc":"2.0","id":j,"method":"getTransaction",
                 "params":[c["sig"], {"encoding":"jsonParsed","maxSupportedTransactionVersion":0}]}
                for j, c in enumerate(chunk)]
        res = None
        for attempt in range(4):
            try:
                req = urllib.request.Request(RPC, data=json.dumps(reqs).encode(),
                                             headers={"Content-Type":"application/json"})
                res = json.loads(urllib.request.urlopen(req, timeout=60).read())
                break
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(3 + attempt * 3); continue
                raise
            except Exception:
                time.sleep(2); continue
        if res is None:
            print(f"  batch {i} exhausted retries — resume next run"); break
        if True:
            for c, r in zip(chunk, res if isinstance(res, list) else []):
                if r.get("result"):
                    f.write(json.dumps({"sig": c["sig"], "slot": c["slot"],
                                        "blockTime": c["blockTime"],
                                        "tx": r["result"]}) + "\n")
                    n += 1
        f.flush()
        if (i // batch) % 20 == 0:
            print(f"  fetched {i+n if False else i}/{len(todo)}")
        time.sleep(0.5)
    f.close()
    print(f"phase 2 done: +{n} txs -> knots_txs.jsonl (rerun to resume)")
