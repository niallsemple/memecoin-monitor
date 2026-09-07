#!/usr/bin/env python3
"""
base4_scout.py — persistent Uniswap V4 launch scout on Base.

Scans PoolManager Initialize events block-range by block-range
(checkpointed), resolves token symbols via eth_call, classifies
quote currency (WETH/USDC/other), and appends to base4_pools.jsonl.

Usage:
  python3 base4_scout.py            # one-shot catch-up scan
  python3 base4_scout.py <minutes>  # loop for N minutes (cron pattern)

Data layout (Initialize):
  topic1 = poolId (bytes32), topic2 = currency0, topic3 = currency1
  data   = fee(32) | tickSpacing(32) | hooks(32) | sqrtPriceX96(32) | tick(32)
"""
import json, os, sys, time, urllib.request

MON = os.path.dirname(os.path.abspath(__file__))
PM = "0x498581fF718922c3f8e6A244956aF099B2652b2b"
INIT = "0xdd466e674ea557f56295e2d0218a125ea4b4f0f6f3307b95f85e6110838d6438"
WETH = "0x4200000000000000000000000000000000000006"
USDC = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
ETH0 = "0x0000000000000000000000000000000000000000"   # V4 native ETH
QUOTES = {WETH: "WETH", USDC: "USDC", ETH0: "ETH"}
RPCS = ["https://mainnet.base.org",
        "https://base-mainnet.public.blastapi.io",
        "https://base.drpc.org"]
UA = {"Content-Type": "application/json",
      "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
CHUNK = 500
CONFIRM = 5
OUT = os.path.join(MON, "base4_pools.jsonl")
STATE = os.path.join(MON, "base4_scout_state.json")
TOKS = os.path.join(MON, "base4_tokens.json")
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


def load_tokens():
    try:
        return json.load(open(TOKS))
    except Exception:
        return {}


def symbol_of(token, cache):
    if token in cache:
        return cache[token]
    if token.lower() == ETH0:
        cache[token] = "ETH"
        return "ETH"
    sym = None
    try:
        r = rpc("eth_call", [{"to": token, "data": "0x95d89b41"}, "latest"])
        raw = bytes.fromhex(r[2:]) if r else b""
        if len(raw) >= 64:
            n = int.from_bytes(raw[32:64], "big")
            if 0 < n <= 64 and len(raw) >= 64 + n:
                sym = raw[64:64 + n].decode("utf-8", "replace")
            else:
                # bytes32-encoded symbol (older tokens)
                sym = raw[:32].rstrip(b"\x00").decode("utf-8", "replace") or None
        elif len(raw) == 32:
            sym = raw.rstrip(b"\x00").decode("utf-8", "replace") or None
    except Exception:
        pass
    cache[token] = sym
    return sym


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
        return 0, latest
    cache = load_tokens()
    n_new = 0
    with open(OUT, "a") as out:
        while start <= latest:
            end = min(start + CHUNK - 1, latest)
            try:
                blk = rpc("eth_getBlockByNumber", [hex(end), False])
                chunk_t = int(blk["timestamp"], 16) if blk else time.time()
            except Exception:
                chunk_t = time.time()
            try:
                logs = rpc("eth_getLogs", [{
                    "address": PM, "fromBlock": hex(start),
                    "toBlock": hex(end), "topics": [INIT]}]) or []
            except Exception as e:
                print(f"getLogs {start}-{end} failed: {e}")
                break
            for e in logs:
                d = e["data"][2:]
                c0 = "0x" + e["topics"][2][26:]
                c1 = "0x" + e["topics"][3][26:]
                hooks = "0x" + d[152:192]
                fee = int(d[0:64], 16)
                tick_spacing = int(d[64:128], 16)
                sqrt_price = int(d[192:256], 16)
                if c1.lower() in QUOTES:
                    base, quote = c0, c1
                elif c0.lower() in QUOTES:
                    base, quote = c1, c0
                else:
                    base, quote = c0, c1   # unknown quote; log raw
                rec = {
                    "t": chunk_t,
                    "block": int(e["blockNumber"], 16),
                    "tx": e["transactionHash"],
                    "pool_id": e["topics"][1],
                    "base": base, "quote": quote,
                    "quote_sym": QUOTES.get(quote.lower()),
                    "base_sym": symbol_of(base, cache),
                    "fee": fee, "tick_spacing": tick_spacing,
                    "hooks": hooks, "sqrt_price_x96": sqrt_price,
                }
                out.write(json.dumps(rec) + "\n")
                n_new += 1
            start = end + 1
            st["last_block"] = end
            json.dump(st, open(STATE, "w"))   # checkpoint per chunk
        json.dump(cache, open(TOKS, "w"))
    json.dump(st, open(STATE, "w"))
    return n_new, latest


def main():
    mins = float(sys.argv[1]) if len(sys.argv) > 1 else 0
    t0 = time.time()
    total = 0
    while True:
        n, latest = scan_once()
        total += n
        print(f"scan: +{n} pools (block {latest})")
        if mins <= 0 or time.time() - t0 > mins * 60:
            break
        time.sleep(15)
    print(f"scout done: {total} new pools, {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
