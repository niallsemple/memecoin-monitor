#!/usr/bin/env python3
"""
bsc_sink_at_entry.py — for each historical paper trade, compute the FULL LP
sink decomposition (burned dead/zero + PinkLock V1/V2 + UNCX x2) AT THE ENTRY
BLOCK using archive-capable endpoints. Decisive re-test of the lock gate:
in-sample claim was 'rugs 0% locked' but burn sinks were never checked at
entry time.

Usage: python3 bsc_sink_at_entry.py [start_idx] [end_idx]
Writes: bsc_sink_at_entry.jsonl (appends)
"""
import json, sys, time, urllib.request

UA = {"Content-Type": "application/json",
      "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
DS = "https://bsc-dataseed.binance.org"          # block search (reliable)
ARCH = ["https://bsc-mainnet.public.blastapi.io", "https://bsc.drpc.org"]
SINKS = {"burn_dead": "000000000000000000000000000000000000dead",
         "burn_zero": "0000000000000000000000000000000000000000",
         "pinklock": "407993575c91ce7643a4d4ccacc9a98c36ee1bbe",
         "pinklock_v1": "7ee058420e5937496f5a2096f04caa7721cf70cc",
         "uncx": "c765bddb93b0d1c1a88282ba0fa6b2d00e3e0c83",
         "uncx_alt": "7229247bd5cf29fa9b0764aa1568732be024084b"}
_id = 0


def rpc(url, method, params, ua=None, tries=8):
    global _id
    _id += 1
    p = json.dumps({"jsonrpc": "2.0", "id": _id,
                    "method": method, "params": params}).encode()
    for a in range(tries):
        try:
            req = urllib.request.Request(url, data=p, headers=ua or
                                         {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as r:
                q = json.load(r)
            if "error" in q:
                raise RuntimeError(str(q["error"])[:90])
            return q.get("result")
        except urllib.error.HTTPError as e:
            if e.code in (408, 429, 500, 502, 503) and a < tries - 1:
                time.sleep(min(30, 4 * (a + 1)))
                continue
            raise
        except Exception:
            if a < tries - 1:
                time.sleep(2 * (a + 1))
                continue
            raise


def block_at(ts):
    latest = int(rpc(DS, "eth_blockNumber", []), 16)
    lo, hi = 0, latest
    while lo < hi:
        mid = (lo + hi + 1) // 2
        b = rpc(DS, "eth_getBlockByNumber", [hex(mid), False])
        if b is None:
            hi = mid - 1
            continue
        if int(b["timestamp"], 16) <= ts:
            lo = mid
        else:
            hi = mid - 1
    return lo


def arch_call(to, data, block):
    errs = []
    for url in ARCH:
        try:
            h = rpc(url, "eth_call", [{"to": to, "data": data}, hex(block)], UA)
            return int(h, 16) if h and h != "0x" else 0
        except Exception as e:
            errs.append(str(e)[:60])
    raise RuntimeError("; ".join(errs))


def main():
    lo = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 999
    trades = [json.loads(l) for l in open("bsc_paper_trades.jsonl")]
    done = set()
    try:
        for l in open("bsc_sink_at_entry.jsonl"):
            done.add(json.loads(l)["pair"])
    except FileNotFoundError:
        pass
    out = open("bsc_sink_at_entry.jsonl", "a")
    for i, r in enumerate(trades):
        if not (lo <= i < hi) or r["pair"] in done:
            continue
        pair, et = r["pair"], int(r["entry_t"])
        try:
            eb = block_at(et)
            ts = arch_call(pair, "0x18160ddd", eb)
            fr = {}
            for nm, s in SINKS.items():
                fr[nm] = round(arch_call(pair, "0x70a08231" + "0" * 24 + s, eb)
                               / ts, 4) if ts else None
                time.sleep(0.3)
            sunk = round(sum(v for v in fr.values() if v), 4)
            rec = {"name": r["name"], "pair": pair, "exit": r["exit"],
                   "ret": r["ret"], "entry_block": eb, "sinks": fr,
                   "sunk_at_entry": sunk}
        except Exception as e:
            rec = {"name": r["name"], "pair": pair, "exit": r["exit"],
                   "ret": r["ret"], "error": str(e)[:120]}
        out.write(json.dumps(rec) + "\n")
        out.flush()
        print(json.dumps(rec), flush=True)


if __name__ == "__main__":
    main()
