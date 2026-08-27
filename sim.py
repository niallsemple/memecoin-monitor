#!/usr/bin/env python3
"""Simulate trader variants over the full tracked cohort (analysis_rows.json).

Rules mirrored from live traders: 2% of cash sizing, 1.5% fee per side,
ladder 25% at 2x/5x/10x entry, trailing stop at 50% of position peak ratio.
Entry variants: r5 floor (1.0/1.25/1.5), r15 fallback checkpoint, age filter.
Price path = observed mcap-ratio snapshots (coarse: poll interval ~2min).
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent
rows = json.loads((ROOT / "analysis_rows.json").read_text())

FEE = 0.015
LADDER = [(2.0, 0.25), (5.0, 0.25), (10.0, 0.25)]  # (multiple, fraction of original)
STOP = 0.5  # trailing stop at 50% of peak ratio

def simulate(entries):
    """entries: list of (row, entry_ratio). Returns final bank on £1000, 2% sizing."""
    bank = cash = 1000.0
    n = wins = 0
    for r, entry in entries:
        stake = cash * 0.02
        if stake < 1:
            continue
        cash -= stake
        n += 1
        # walk the price path after entry time: approximate using r5/r15/peak/final shape
        # We reconstruct from row stats: assume linear path entry->peak->final is too crude;
        # instead use ladder hits from peak and stop from peak.
        peak = r["peak"] / entry  # position peak multiple relative to entry
        final = r["final"] / entry
        remaining = 1.0
        proceeds = 0.0
        stopped = False
        for mult, frac in LADDER:
            if peak >= mult and remaining > 0:
                sell = min(frac, remaining)
                proceeds += stake * sell * mult * (1 - FEE)
                remaining -= sell
        if remaining > 0:
            # trailing stop: exit at max(STOP*peak, final) — if final below stop level, stopped there
            stop_lvl = STOP * peak
            exit_mult = stop_lvl if final < stop_lvl else final
            exit_mult = min(exit_mult, peak)
            proceeds += stake * remaining * exit_mult * (1 - FEE)
            stopped = True
        pnl = proceeds - stake
        cash += proceeds
        if pnl > 0:
            wins += 1
        bank = cash
    return bank, n, wins

pass_rows = [r for r in rows if r["verdict"] == "PASS" and r["liq"] and r["liq"] >= 20000]
print(f"tradable PASS cohort (liq>=$20k): {len(pass_rows)}")

def report(label, sel):
    ent = [(r, r["r5"]) for r in pass_rows if sel(r) and r.get("r5")]
    bank, n, w = simulate(ent)
    if n:
        print(f"{label:44s} trades={n:3d} wins={w:3d} ({w/n*100:3.0f}%) | bank=£{bank:,.2f} ROI={(bank/1000-1)*100:+6.1f}%")
    else:
        print(f"{label:44s} trades=  0")

print("\n== single checkpoint r5 floors ==")
report("floor>=1.0 (v2 live)", lambda r: r["r5"] >= 1.0)
report("floor>=1.25 (v3 live)", lambda r: r["r5"] >= 1.25)
report("floor>=1.5", lambda r: r["r5"] >= 1.5)
report("floor>=2.0", lambda r: r["r5"] >= 2.0)

print("\n== with age>=15min pre-filter ==")
report("floor>=1.0 + age>=15", lambda r: r["r5"] >= 1.0 and (r["age_min"] or 0) >= 15)
report("floor>=1.25 + age>=15", lambda r: r["r5"] >= 1.25 and (r["age_min"] or 0) >= 15)
report("floor>=1.5 + age>=15", lambda r: r["r5"] >= 1.5 and (r["age_min"] or 0) >= 15)

print("\n== two-checkpoint variants (enter at r5 if passes, else at r15 if passes) ==")
def two_chk(r, f5, f15):
    if r.get("r5") and r["r5"] >= f5:
        return r["r5"]
    if r.get("r15") and r["r15"] >= f15:
        return r["r15"]
    return None
for f5, f15 in [(1.25, 1.5), (1.0, 1.5), (1.5, 1.5), (1.25, 2.0)]:
    ent = []
    for r in pass_rows:
        e = two_chk(r, f5, f15)
        if e:
            ent.append((r, e))
    bank, n, w = simulate(ent)
    if n:
        print(f"r5>={f5} else r15>={f15}: trades={n:3d} wins={w:3d} ({w/n*100:3.0f}%) | bank=£{bank:,.2f} ROI={(bank/1000-1)*100:+6.1f}%")

print("\n== high-liquidity defensive variant (liq>=$50k) ==")
hi = [r for r in rows if r["verdict"] == "PASS" and r["liq"] and r["liq"] >= 50000]
report("liq>=50k, floor>=1.0", lambda r: r["r5"] and r["r5"] >= 1.0 and r in hi or False)
