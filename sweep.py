#!/usr/bin/env python3
"""Sweep exit parameters (ladder + trailing stop) for the best entry variant."""
import json
from pathlib import Path

ROOT = Path(__file__).parent
rows = json.loads((ROOT / "analysis_rows.json").read_text())
FEE = 0.015

pass_rows = [r for r in rows if r["verdict"] == "PASS" and r["liq"] and r["liq"] >= 20000]

def entry(r):
    if r.get("r5") and r["r5"] >= 1.5:
        return r["r5"]
    if r.get("r15") and r["r15"] >= 1.5:
        return r["r15"]
    return None

cands = [(r, entry(r)) for r in pass_rows if entry(r)]
print(f"entries (r5>=1.5 else r15>=1.5): {len(cands)}")

def simulate(ladder, stop):
    bank = 1000.0
    n = wins = 0
    for r, e in cands:
        stake = bank * 0.02
        n += 1
        peak = r["peak"] / e
        final = r["final"] / e
        remaining = 1.0
        proceeds = 0.0
        for mult, frac in ladder:
            if peak >= mult and remaining > 0:
                sell = min(frac, remaining)
                proceeds += stake * sell * mult * (1 - FEE)
                remaining -= sell
        if remaining > 0:
            exit_mult = min(max(stop * peak, final), peak)
            proceeds += stake * remaining * exit_mult * (1 - FEE)
        if proceeds > stake:
            wins += 1
        bank = bank - stake + proceeds
    return bank, wins

print("\n== trailing stop sweep (ladder 25% at 2/5/10x) ==")
for s in (0.3, 0.4, 0.5, 0.6, 0.7):
    b, w = simulate([(2, .25), (5, .25), (10, .25)], s)
    print(f"stop={s:.1f} of peak: bank=£{b:,.2f} ROI={(b/1000-1)*100:+6.1f}% wins={w}/{len(cands)}")

print("\n== ladder sweep (stop=0.5) ==")
for lad, lbl in [
    ([(2, .25), (5, .25), (10, .25)], "25% @2/5/10x"),
    ([(1.5, .33), (3, .33), (6, .34)], "33% @1.5/3/6x"),
    ([(2, .50), (5, .25)], "50% @2x, 25% @5x"),
    ([(2, 1.0)], "100% @2x"),
    ([(1.5, .50), (3, .50)], "50% @1.5x, 50% @3x"),
    ([(3, .50), (10, .50)], "50% @3x, 50% @10x"),
]:
    b, w = simulate(lad, 0.5)
    print(f"{lbl:22s}: bank=£{b:,.2f} ROI={(b/1000-1)*100:+6.1f}% wins={w}/{len(cands)}")

print("\n== combined best-guess grid ==")
best = None
for s in (0.4, 0.5, 0.6):
    for lad, lbl in [([(2, .5), (5, .25)], "50@2/25@5"), ([(1.5, .5), (3, .5)], "50@1.5/50@3"), ([(2, 1)], "100@2")]:
        b, w = simulate(lad, s)
        tag = f"stop={s} {lbl}"
        if best is None or b > best[0]:
            best = (b, tag, w)
        print(f"{tag:22s}: bank=£{b:,.2f} ROI={(b/1000-1)*100:+6.1f}% wins={w}/{len(cands)}")
print(f"\nBEST: {best[1]} -> £{best[0]:,.2f}")
