#!/usr/bin/env python3
"""Fetch KNOTS pool txs for the hour BEFORE the current knots_txs.jsonl window
to locate the protocol-fee claim preceding our deploy. Writes knots_txs_pre.jsonl."""
import json, os, time, urllib.request

MON = os.path.dirname(os.path.abspath(__file__))
KEY = open(os.path.join(MON, "helius_key.txt")).read().strip()
RPC = f"https://mainnet.helius-rpc.com/?api-key={KEY}"
POOL = "nBXytBBfKLhj6teXarAv8rk6WNgUFBMyybUFRkuK7ad"
STOP_T = 1789149000           # ~1h before current data start
CUR_START = 1789152629        # oldest blockTime in knots_txs.jsonl


def post(payload, timeout=60):
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    for attempt in range(8):
        try:
            req = urllib.request.Request(RPC, data=body, headers={"Content-Type": "application/json"})
            return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = min(2 ** attempt, 30)
                print(f"  429, backing off {wait}s")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("rate limited out")

def rpc(method, params):
    return post({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})


def main():
    # page signatures backward from oldest known
    oldest_sig = None
    with open(os.path.join(MON, "knots_sigs.jsonl")) as f:
        rows = [json.loads(l) for l in f]
    oldest = min(rows, key=lambda r: r["blockTime"])
    before = oldest["sig"]
    sigs = []
    while True:
        r = rpc("getSignaturesForAddress", [POOL, {"limit": 1000, "before": before}])
        batch = r.get("result") or []
        if not batch:
            break
        sigs.extend(batch)
        before = batch[-1]["signature"]
        print(f"sigs {len(sigs)}, oldest {batch[-1]['blockTime']}")
        if batch[-1]["blockTime"] < STOP_T:
            break
        time.sleep(0.15)
    keep = [s for s in sigs if STOP_T <= s["blockTime"] < CUR_START]
    print(f"keep {len(keep)} sigs in pre-window")
    # batch fetch
    out = open(os.path.join(MON, "knots_txs_pre.jsonl"), "w")
    for i in range(0, len(keep), 50):
        reqs = [{"jsonrpc": "2.0", "id": j,
                 "method": "getTransaction",
                 "params": [s["signature"], {"encoding": "jsonParsed",
                            "maxSupportedTransactionVersion": 0,
                            "commitment": "confirmed"}]}
                for j, s in enumerate(keep[i:i+50])]
        resp = post(reqs, timeout=120)
        for j, s in enumerate(keep[i:i+50]):
            r = resp[j].get("result")
            if r:
                out.write(json.dumps({"sig": s["signature"], "slot": r.get("slot"),
                                      "blockTime": r.get("blockTime"), "tx": r}) + "\n")
        print(f"fetched {min(i+50, len(keep))}/{len(keep)}")
        time.sleep(0.5)
    out.close()
    print("done -> knots_txs_pre.jsonl")


if __name__ == "__main__":
    main()
