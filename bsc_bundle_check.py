#!/usr/bin/env python3
"""
bsc_bundle_check.py — token-holder concentration ("bundle check") for a
PancakeSwap-V2-style pair at a given entry time, via archive eth_call +
chunked eth_getLogs on drpc (public, browser-UA, backoff).

Reports top-1/5/10 holder share of the base (non-quote) token at entry.
Hypothesis: supply-dump rugs have extreme top-holder concentration even when
LP is locked (LP locks don't stop insiders dumping the token itself).

Usage: python3 bsc_bundle_check.py <pair> <entry_unix_t>
"""
import json, sys, time, urllib.request

RPC = "https://bsc.drpc.org"                       # logs + archive (429-prone)
RPC_CALLS = "https://bsc-dataseed.binance.org"     # plain eth_call (reliable)
UA = {"Content-Type": "application/json",
      "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
WBNB = "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c"
USDT = "0x55d398326f99059ff775485246999027b3197955"
CHUNK = 2000
MAX_BACK = 240         # ~240*2k = 480k blocks lookback (~4 days at 0.75s)
_id = 0


def rpc(method, params, tries=10, url=RPC):
    global _id
    _id += 1
    p = json.dumps({"jsonrpc": "2.0", "id": _id,
                    "method": method, "params": params}).encode()
    for a in range(tries):
        try:
            req = urllib.request.Request(url, data=p, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                q = json.load(r)
            if "error" in q:
                raise RuntimeError(str(q["error"])[:100])
            return q.get("result")
        except urllib.error.HTTPError as e:
            if e.code in (408, 429, 500, 502, 503) and a < tries - 1:
                time.sleep(min(45, 5 * (a + 1)))
                continue
            raise
        except Exception:
            if a < tries - 1:
                time.sleep(2 * (a + 1))
                continue
            raise


def uint_call(to, data, block="latest"):
    h = rpc("eth_call", [{"to": to, "data": data}, block], url=RPC_CALLS)
    return int(h, 16) if h and h != "0x" else 0


def block_at(ts):
    latest = int(rpc("eth_blockNumber", [], url=RPC_CALLS), 16)
    lo, hi = 0, latest
    while lo < hi:
        mid = (lo + hi + 1) // 2
        b = rpc("eth_getBlockByNumber", [hex(mid), False], url=RPC_CALLS)
        if b is None:
            hi = mid - 1
            continue
        if int(b["timestamp"], 16) <= ts:
            lo = mid
        else:
            hi = mid - 1
    return lo


def logs(addr, frm, to):
    time.sleep(0.4)
    return rpc("eth_getLogs", [{"address": addr, "topics": [TRANSFER],
                                "fromBlock": hex(frm), "toBlock": hex(to)}]) or []


def main():
    pair, entry_t = sys.argv[1].lower(), int(float(sys.argv[2]))
    t0 = uint_call(pair, "0x0dfe1681")   # token0()
    t1 = uint_call(pair, "0xd21220a7")   # token1()
    a0 = "0x" + f"{t0:040x}" if t0 else None
    a1 = "0x" + f"{t1:040x}" if t1 else None
    base = a1 if a0 and a0.lower() in (WBNB, USDT) else a0
    eb = block_at(entry_t)
    print(f"pair={pair} base_token={base} entry_block={eb}", file=sys.stderr)

    # find creation: scan backwards until a chunk with logs whose earliest
    # log is a mint-from-zero; stop when an earlier chunk has none
    all_logs = []
    to = eb
    found_start = None
    for _ in range(MAX_BACK):
        frm = max(0, to - CHUNK)
        lg = logs(base, frm, to)
        if lg:
            all_logs = lg + all_logs
            to = frm - 1
            # creation = first-ever transfer; if earliest log in the FIRST
            # chunk we saw is from 0x0 we may already have it, keep scanning
            # until an empty chunk to be sure
            found_start = int(lg[0]["blockNumber"], 16)
            continue
        else:
            if all_logs:
                break          # empty chunk after data -> creation reached
            to = frm - 1       # no logs yet at all; keep scanning back
        if frm == 0:
            break
    if not all_logs:
        print(json.dumps({"pair": pair, "error": "no transfer logs found"}))
        return
    creation_blk = int(all_logs[0]["blockNumber"], 16)

    bal = {}
    total = 0
    zero = "0x" + "0" * 40
    for e in all_logs:
        f = "0x" + e["topics"][1][-40:]
        t = "0x" + e["topics"][2][-40:]
        v = int(e["data"], 16)
        if f == zero:
            total += v
        if t == zero or t.lower() == "0x" + "0" * 38 + "dead":
            total -= v
        bal[f] = bal.get(f, 0) - v
        bal[t] = bal.get(t, 0) + v
    bal.pop(zero, None)
    bal.pop("0x" + "0" * 38 + "dead", None)
    bal.pop(pair, None)          # pool inventory isn't a "holder"
    if total <= 0:
        print(json.dumps({"pair": pair, "error": "zero supply"}))
        return
    top = sorted(bal.items(), key=lambda kv: -kv[1])
    def share(n):
        return round(sum(v for _, v in top[:n]) / total, 4)
    print(json.dumps({
        "pair": pair, "base": base, "entry_block": eb,
        "creation_block": creation_blk,
        "n_logs": len(all_logs), "n_holders": len(bal),
        "top1": share(1), "top5": share(5), "top10": share(10),
        "top5_addrs": [(a, round(v / total, 4)) for a, v in top[:5]],
    }))


if __name__ == "__main__":
    main()
