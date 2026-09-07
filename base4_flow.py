#!/usr/bin/env python3
"""
base4_flow.py — Uniswap V4 swap-flow tracker on Base.

Scans PoolManager Swap events (checkpointed, chunked), buckets by poolId,
and appends per-pool net quote deltas + price (from sqrtPriceX96) to
base4_flow.jsonl. Only pools discovered by base4_scout.py are tracked.

V4 Swap event: Swap(bytes32 id, address sender, int128 amount0,
                    int128 amount1, uint160 sqrtPriceX96, uint128 liquidity,
                    int24 tick, uint24 fee)
  topics[1]=poolId, topics[2]=sender
  data = amount0|amount1|sqrtPriceX96|liquidity|tick|fee  (6 words)
  amountN = change in POOL balance of currencyN (positive = pool gained).
  Pool gaining quote currency = buy pressure on the base token.

Usage:
  python3 base4_flow.py           # one-shot catch-up
  python3 base4_flow.py <minutes> # loop (cron pattern)
"""
import json, os, sys, time, urllib.request

MON = os.path.dirname(os.path.abspath(__file__))
PM = "0x498581fF718922c3f8e6A244956aF099B2652b2b"
SWAP = "0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f"
RPCS = ["https://mainnet.base.org",
        "https://base-mainnet.public.blastapi.io",
        "https://base.drpc.org"]
UA = {"Content-Type": "application/json",
      "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
CHUNK = 200
CONFIRM = 3
MAX_AGE_H = 26          # only track pools younger than this
POOLS = os.path.join(MON, "base4_pools.jsonl")
OUT = os.path.join(MON, "base4_flow.jsonl")
STATE = os.path.join(MON, "base4_flow_state.json")
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
            time.sleep(min(2 ** a, 15))
    raise RuntimeError(f"rpc {method} failed: {err}")


def i128(word_hex):
    # ABI int128 is sign-extended into a 256-bit word; take low 128 bits
    v = int(word_hex, 16) & ((1 << 128) - 1)
    return v - (1 << 128) if v >= (1 << 127) else v


def load_pools():
    """pool_id -> {quote_is0, base, quote, quote_sym, birth_t, base_sym}"""
    pools = {}
    if not os.path.exists(POOLS):
        return pools
    for l in open(POOLS):
        try:
            d = json.loads(l)
        except Exception:
            continue
        pid = d.get("pool_id")
        if not pid or pid in pools:
            continue
        # determine which side is the quote from the scout record
        q = (d.get("quote") or "").lower()
        b = (d.get("base") or "").lower()
        pools[pid] = {
            "base": b, "quote": q, "quote_sym": d.get("quote_sym"),
            "base_sym": d.get("base_sym"), "birth_t": d.get("t"),
            "fee": d.get("fee"),
        }
    return pools


def scan_once():
    st = {"last_block": 0}
    if os.path.exists(STATE):
        try:
            st = json.load(open(STATE))
        except Exception:
            pass
    latest = int(rpc("eth_blockNumber", []), 16) - CONFIRM
    start = st["last_block"] + 1 if st["last_block"] else latest - CHUNK
    if start > latest:
        return 0
    pools = load_pools()
    now = time.time()
    # per-pool aggregation for this scan
    agg = {}
    n_logs = 0
    while start <= latest:
        end = min(start + CHUNK - 1, latest)
        try:
            logs = rpc("eth_getLogs", [{
                "address": PM, "fromBlock": hex(start),
                "toBlock": hex(end), "topics": [SWAP]}]) or []
        except Exception as e:
            print(f"getLogs {start}-{end} failed: {e}")
            break
        for e in logs:
            pid = e["topics"][1]
            p = pools.get(pid)
            if not p:
                continue
            n_logs += 1
            d = e["data"][2:]
            a0 = i128(d[0:64])
            a1 = i128(d[64:128])
            sqrt_price = int(d[128:192], 16)
            # V4 orders currencies by address: currency0 < currency1.
            # EMPIRICAL: event amounts are SWAPPER-perspective deltas
            # (a buy shows swapper losing quote), so negate to get
            # pool-side net quote inflow.
            quote_is0 = p["quote"] < p["base"]
            net_quote = -(a0 if quote_is0 else a1)
            g = agg.setdefault(pid, {"n": 0, "net_q": 0, "sqrt": sqrt_price,
                                     "p": p})
            g["n"] += 1
            g["net_q"] += net_quote
            g["sqrt"] = sqrt_price
        start = end + 1
        st["last_block"] = end
    with open(OUT, "a") as out:
        for pid, g in agg.items():
            p = g["p"]
            age_h = (now - (p.get("birth_t") or now)) / 3600
            if age_h > MAX_AGE_H:
                continue
            out.write(json.dumps({
                "t": now, "pool_id": pid, "n_swaps": g["n"],
                "net_quote_raw": g["net_q"],
                "sqrt_price_x96": g["sqrt"],
                "base": p["base"], "quote": p["quote"],
                "quote_sym": p.get("quote_sym"), "base_sym": p.get("base_sym"),
                "age_h": round(age_h, 2),
            }) + "\n")
    json.dump(st, open(STATE, "w"))
    return n_logs


def main():
    mins = float(sys.argv[1]) if len(sys.argv) > 1 else 0
    t0 = time.time()
    total = 0
    while True:
        n = scan_once()
        total += n
        print(f"flow scan: {n} swaps in tracked pools")
        if mins <= 0 or time.time() - t0 > mins * 60:
            break
        time.sleep(20)
    print(f"flow done: {total} tracked swaps, {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
