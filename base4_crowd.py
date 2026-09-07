#!/usr/bin/env python3
"""
base4_crowd.py — holder-proxy study for entered Base V4 pools.

GoPlus chain-8453 coverage of fresh meme tokens is too thin (9/68 on the
first backfill), so measure the crowd directly: unique Transfer recipients
of the base token from pool birth to chain tip. Correlates with trade
outcomes from base4_paper_trades.jsonl.

Output: base4_crowd.jsonl  {pool_id, base, name, ret, holders, birth_block}
"""
import json, os, time, urllib.request

MON = os.path.dirname(os.path.abspath(__file__))
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
PM = "0x498581ff718922c3f8e6a244956af099b2652b2b"
RPCS = ["https://mainnet.base.org",
        "https://base-mainnet.public.blastapi.io",
        "https://base.drpc.org"]
UA = {"Content-Type": "application/json",
      "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
EXCLUDE = {"0x0000000000000000000000000000000000000000",
           "0x000000000000000000000000000000000000dead", PM}
OUT = os.path.join(MON, "base4_crowd.jsonl")
_id = 0


def rpc(method, params, tries=6):
    global _id
    _id += 1
    p = json.dumps({"jsonrpc": "2.0", "id": _id,
                    "method": method, "params": params}).encode()
    err = None
    for a in range(tries):
        url = RPCS[a % len(RPCS)]
        try:
            req = urllib.request.Request(url, data=p, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                q = json.load(r)
            if "error" in q:
                raise RuntimeError(str(q["error"])[:100])
            return q.get("result")
        except Exception as e:
            err = e
            time.sleep(min(2 ** a, 10))
    raise RuntimeError(f"rpc {method} failed: {err}")


def holders_of(token, from_block, tip):
    recips = set()
    start = from_block
    chunk = 2000
    while start <= tip:
        end = min(start + chunk - 1, tip)
        try:
            logs = rpc("eth_getLogs", [{
                "address": token, "fromBlock": hex(start), "toBlock": hex(end),
                "topics": [TRANSFER]}], tries=3) or []
        except Exception:
            if chunk > 250:          # hot token: 413 payload — halve and retry
                chunk //= 2
                continue
            raise
        for e in logs:
            if len(e.get("topics", [])) >= 3:
                to = "0x" + e["topics"][2][-40:]
                if to not in EXCLUDE:
                    recips.add(to)
        start = end + 1
    return len(recips)


def main():
    pools = {}
    for l in open(os.path.join(MON, "base4_pools.jsonl")):
        try:
            d = json.loads(l)
        except Exception:
            continue
        if d.get("pool_id"):
            pools[d["pool_id"]] = d

    entries = {}   # pool_id -> {name, ret, base}
    for l in open(os.path.join(MON, "base4_paper_trades.jsonl")):
        t = json.loads(l)
        entries[t["pool_id"]] = {"name": t["name"], "ret": t["ret"]}
    st = json.load(open(os.path.join(MON, "base4_paper_state.json")))
    for pid, p in st.get("open", {}).items():
        entries.setdefault(pid, {"name": p["name"], "ret": None})

    done = set()
    if os.path.exists(OUT):
        for l in open(OUT):
            try:
                done.add(json.loads(l)["pool_id"])
            except Exception:
                pass

    tip = int(rpc("eth_blockNumber", []), 16)
    out = open(OUT, "a")
    n = 0
    for pid, e in entries.items():
        if pid in done:
            continue
        d = pools.get(pid)
        if not d or not d.get("base"):
            continue
        try:
            h = holders_of(d["base"], d["block"], tip)
        except Exception as ex:
            print(f"fail {e['name']}: {ex}")
            continue
        rec = {"pool_id": pid, "base": d["base"], "name": e["name"],
               "ret": e["ret"], "holders": h, "birth_block": d["block"]}
        out.write(json.dumps(rec) + "\n")
        out.flush()
        n += 1
        print(f"{e['name']:<26} ret={e['ret']}  holders={h}")
    out.close()
    print(f"crowd scan: {n} pools measured")


if __name__ == "__main__":
    main()
