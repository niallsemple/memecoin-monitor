#!/usr/bin/env python3
"""
bsc_standings.py — one-glance standings across all BSC paper books.
Splits each book into historical (pre-gate era) and forward (post-deploy)
trades so in-sample vs out-of-sample performance is never mixed.

Forward boundary: 2026-09-07 17:30 UTC (lockgate deployment).
"""
import json, os, statistics, time

FWD_T = 1788801600.0   # ~2026-09-07 17:20 UTC
BOOKS = [("", "control (ungated)"),
         ("_lockgate", "lockgate (>=95% LP locked)"),
         ("_lockgate_usdt", "lockgate+USDT")]


def stats(rets):
    if not rets:
        return "n=0"
    g = sum(1 for x in rets if x > 0)
    return (f"n={len(rets):2d} green={g:2d} ({g/len(rets):4.0%}) "
            f"mean={statistics.mean(rets):6.3f}x med={statistics.median(rets):6.3f}x "
            f"sum={sum(rets)-len(rets):+7.2f}x")


def main():
    print(f"{'book':<26} {'historical':<44} forward")
    for suf, lab in BOOKS:
        fn = f"bsc_paper_trades{suf}.jsonl"
        if not os.path.exists(fn):
            continue
        rows = [json.loads(l) for l in open(fn)]
        hist = [r["ret"] for r in rows if r["entry_t"] < FWD_T]
        fwd = [r["ret"] for r in rows if r["entry_t"] >= FWD_T]
        print(f"{lab:<26} {stats(hist):<44} {stats(fwd)}")
        fwd_rows = [r for r in rows if r["entry_t"] >= FWD_T]
        for r in fwd_rows:
            print(f"{'':28}FWD {r['name'][:20]:<22} ret={r['ret']:.3f} ({r['exit']})")
    # open positions
    for suf, lab in BOOKS:
        fn = f"bsc_paper_state{suf}.json"
        if os.path.exists(fn):
            st = json.load(open(fn))
            for v in st.get("open", {}).values():
                age = (time.time() - v["entry_t"]) / 60
                print(f"OPEN [{lab}] {v['name']} age={age:.0f}m peak={v.get('peak'):.2f}x")


if __name__ == "__main__":
    main()
