#!/usr/bin/env python3
"""§446c: birth-window concentration over h16e2 entry-stream candidates.

Usage: python3 birth_concentration_h16.py <offset> <count>
Appends to birth_concentration_h16.jsonl (skips mints already done).
Outcome labels: win (touched 1.2x), loss (touched 0.92x), timeout (1h).
"""
import json
import sys
import importlib.util
from pathlib import Path

MON = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "bcb", str(MON / "birth_concentration_batch.py"))
bcb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bcb)

OUT = MON / "birth_concentration_h16.jsonl"


def main():
    offset, count = int(sys.argv[1]), int(sys.argv[2])
    opens, closes = {}, {}
    for l in (MON / "h16_early2.jsonl").open():
        try:
            r = json.loads(l)
        except Exception:
            continue
        if r.get("action") == "h16e2_open":
            opens[r["mint"]] = r
        elif r.get("action") == "h16e2_close":
            closes[r["mint"]] = r
    cmap = {}
    for l in (MON / "curves.jsonl").open():
        try:
            r = json.loads(l)
        except Exception:
            continue
        if r.get("mint") and r.get("bondingCurveKey"):
            cmap[r["mint"]] = r["bondingCurveKey"]
    done = set()
    if OUT.exists():
        for l in OUT.open():
            try:
                done.add(json.loads(l)["mint"])
            except Exception:
                pass
    mints = [m for m in opens if m in closes and m in cmap and m not in done]
    batch = mints[offset:offset + count]
    print(f"eligible={len(mints)} doing {len(batch)}")
    with OUT.open("a") as f:
        for m in batch:
            r = bcb.analyze(m, cmap[m])
            if r:
                r["outcome"] = closes[m].get("outcome")
                r["mult"] = closes[m].get("mult")
                r["seed"] = opens[m].get("seed")
                r["mom"] = opens[m].get("mom")
                f.write(json.dumps(r) + "\n")
                f.flush()
                print(f"{m[:8]} {r['outcome']:>7} seed={r['seed']!s:>7} top1={r['top1_share']:>6} cb={r['creator_buy_share']!s:>6} buyers={r['n_buyers']:>3} vol={r['tot_buy_sol']:>7} t1=c:{r['top1_eq_creator']}")
            else:
                print(f"{m[:8]} NO DATA")


if __name__ == "__main__":
    main()
