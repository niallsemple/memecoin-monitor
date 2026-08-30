#!/usr/bin/env python3
"""Falsification pass for the best surviving config (entry r5/r15>=1.5, 100%@2x, trail 0.6).

Master-prompt Part 10 battery:
  - remove best trade / best 3 / best 5 / best 10% winners
  - iid bootstrap CI on mean per-trade return
  - chronological halves (regime split)
  - parameter-plateau check (is the best config an island?)
"""
import json, random
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).parent
rows = json.loads((ROOT / "analysis_rows.json").read_text())
FEE = 0.015

cands = [r for r in rows if r["verdict"] == "PASS" and r["liq"] and r["liq"] >= 20000]

def entry(r):
    if r.get("r5") and r["r5"] >= 1.5: return r["r5"]
    if r.get("r15") and r["r15"] >= 1.5: return r["r15"]
    return None

def trade_roi(r, stop, ladder):
    e = entry(r)
    peak, final = r["peak"] / e, r["final"] / e
    remaining, proceeds = 1.0, 0.0
    for mult, frac in ladder:
        if peak >= mult and remaining > 0:
            sell = min(frac, remaining)
            proceeds += sell * mult * (1 - FEE)
            remaining -= sell
    if remaining > 0:
        proceeds += remaining * min(max(stop * peak, final), peak) * (1 - FEE)
    return proceeds - 1.0  # net ROI on stake

cands = [(r, entry(r)) for r in cands if entry(r)]
print(f"entry cohort n={len(cands)}")

def report(rois, label):
    if not rois:
        print(f"{label:40s} n=0"); return
    wins = sum(1 for x in rois if x > 0)
    print(f"{label:40s} n={len(rois):2d} mean={mean(rois)*100:+6.1f}% med={median(rois)*100:+6.1f}% win={wins}/{len(rois)}")

cfg = dict(stop=0.6, ladder=[(2, 1.0)])
rois = sorted((trade_roi(r, **cfg) for r, _ in cands), reverse=True)
print("\n== best config: 100%@2x, trail 0.6 — per-trade ROI ==")
report(rois, "full")
for k, lbl in [(1, "remove best 1"), (3, "remove best 3"), (5, "remove best 5"),
               (max(1, len(rois)//10), "remove best 10%")]:
    report(rois[k:], lbl)
print("per-trade ROIs:", ", ".join(f"{x*100:+.0f}%" for x in rois))

random.seed(42)
boot = sorted(mean(random.choices(rois, k=len(rois))) for _ in range(10000))
print(f"\nbootstrap mean ROI 95% CI: [{boot[250]*100:+.1f}%, {boot[9750]*100:+.1f}%]  P(mean<0)={sum(1 for b in boot if b<0)/len(boot)*100:.0f}%")

half = len(cands) // 2
first = [trade_roi(r, **cfg) for r, _ in cands[:half]]
second = [trade_roi(r, **cfg) for r, _ in cands[half:]]
print("\n== chronological split (detection order) ==")
report(first, "first half")
report(second, "second half")

print("\n== parameter plateau (neighbourhood of best config) ==")
for stop in (0.5, 0.6, 0.7):
    for lad, lbl in [([(2, 1.0)], "100@2"), ([(2, .5), (5, .25)], "50@2/25@5"), ([(1.5, .5), (3, .5)], "50@1.5/50@3")]:
        rr = [trade_roi(r, stop, lad) for r, _ in cands]
        report(rr, f"stop={stop} {lbl}")
