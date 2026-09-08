#!/usr/bin/env python3
"""
meteora_verdict_diff.py — compare the last two runs in meteora_verdict_log.jsonl.

Each log entry: {"t": epoch, "rows": [{"age","ftr","tvl","summary","n"}, ...]}
Prints per-row deltas (n, mean_narrow_worst, pos count) between the two most
recent runs so drift in the verdict is visible at a glance.
"""
import json, os, re, sys, datetime

MON = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(MON, "meteora_verdict_log.jsonl")

NUM = re.compile(r"n=(\d+) mean_narrow_worst=([+-]?[\d.]+) .*?pos_narrow_worst=(\d+)/(\d+)")


def parse(summary):
    m = NUM.search(summary)
    if not m:
        return None
    return {"n": int(m.group(1)), "mean": float(m.group(2)),
            "pos": int(m.group(3)), "tot": int(m.group(4))}


def key(row):
    return (row.get("age"), row.get("ftr"), row.get("tvl"), row.get("max_hold_h"))


def main():
    if not os.path.exists(LOG):
        sys.exit("no verdict log yet")
    runs = [json.loads(l) for l in open(LOG) if l.strip()]
    if len(runs) < 2:
        sys.exit("need >=2 logged runs to diff")
    a, b = runs[-2], runs[-1]
    ta = datetime.datetime.fromtimestamp(a["t"], datetime.UTC).strftime("%m-%d %H:%M")
    tb = datetime.datetime.fromtimestamp(b["t"], datetime.UTC).strftime("%m-%d %H:%M")
    print(f"verdict drift: {ta} UTC -> {tb} UTC")
    print(f"{'row':<22} {'n':>9} {'mean_narrow_worst':>22} {'pos':>9}")
    amap = {key(r): parse(r["summary"]) for r in a["rows"]}
    for r in b["rows"]:
        k = key(r)
        pb = parse(r["summary"])
        pa = amap.get(k)
        age_s = f"{k[0]:g}" if k[0] is not None else "any"
        label = f"age<={age_s} ftr>={k[1]:g} tvl>={k[2]/1000:g}k"
        if k[3] is not None:
            label += f" hold<={k[3]:g}h"
        if not pb:
            continue
        n_s = f"{pa['n']}->{pb['n']}" if pa else f"->{pb['n']}"
        if pa:
            dm = pb["mean"] - pa["mean"]
            m_s = f"{pa['mean']:+.1f}->{pb['mean']:+.1f} ({dm:+.1f})"
            p_s = f"{pa['pos']}/{pa['tot']}->{pb['pos']}/{pb['tot']}"
        else:
            m_s = f"->{pb['mean']:+.1f}"
            p_s = f"->{pb['pos']}/{pb['tot']}"
        print(f"{label:<22} {n_s:>9} {m_s:>22} {p_s:>9}")


if __name__ == "__main__":
    main()
