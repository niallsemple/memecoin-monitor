#!/usr/bin/env python3
"""Latency decay + capital capacity for the surviving signal (H02/H03).

Latency: our data is 2-4 min mcap samples — we cannot resolve ms. What we CAN
measure honestly is decay in the band we actually operate in: entering 1 or 2
samples (~2-8 min) after the 1.5x crossing vs entering at the crossing print.

Capacity: constant-product impact model. Pool depth proxy = detected liquidity
(USD). A buy of $X into a pool with $L quote-side depth moves price by
X/(L+X). We find the size where round-trip impact eats the simulated edge.
"""
import json
from pathlib import Path
from datetime import datetime
from statistics import mean, median

ROOT = Path(__file__).parent
state = json.loads((ROOT / "state.json").read_text())["seen"]
FEE = 0.015
SOL_USD = 200  # approx; used only to convert SOL sizes to USD impact

def ts(s): return datetime.fromisoformat(s).timestamp()

cands = []
for key, v in state.items():
    if not key.startswith("solana:"): continue
    if v.get("verdict") != "PASS": continue
    det = v.get("detect") or {}
    hist = v.get("history") or []
    if not hist or not det.get("mcap") or not (det.get("liq_usd") or 0) >= 20000: continue
    t0 = ts(hist[0]["t"])
    pts = [(ts(h["t"]) - t0, (h.get("mcap") or 0) / det["mcap"]) for h in hist if h.get("mcap")]
    if len(pts) < 3: continue
    cands.append({"key": key, "pts": pts, "liq": det["liq_usd"], "d_mcap": det["mcap"]})

print(f"PASS + liq>=$20k cohort: {len(cands)}")

# ---- signal events: first sample >=1.5x at/after 5min, else at/after 15min ----
def signals(c):
    out = []
    for i, (dt, r) in enumerate(c["pts"]):
        if dt >= 300 and r >= 1.5:
            out.append(("r5", i)); break
    if not out:
        for i, (dt, r) in enumerate(c["pts"]):
            if dt >= 900 and r >= 1.5:
                out.append(("r15", i)); break
    return out

events = []
for c in cands:
    sig = signals(c)
    if sig:
        events.append((c, sig[0][0], sig[0][1]))
print(f"signal events: {len(events)}")

def roi_with_entry(c, entry_idx):
    """100%@2x, trail 0.6-of-peak, fees, entering at pts[entry_idx]."""
    pts = c["pts"]
    e = pts[entry_idx][1]
    after = pts[entry_idx:]
    peak = max(r for _, r in after) / e
    final = after[-1][1] / e
    if peak >= 2.0:
        return (2.0 * (1 - FEE)) / (1 + FEE) - 1.0
    exit_mult = min(max(0.6 * peak, final), peak)
    return (exit_mult * (1 - FEE)) / (1 + FEE) - 1.0

print("\n== LATENCY DECAY (entry delayed by N samples after the 1.5x print) ==")
print(f"{'delay':>16s} {'n':>3s} {'mean ROI':>9s} {'median':>8s} {'win%':>5s} {'entry price vs signal':>22s}")
for delay in (0, 1, 2, 3):
    rois, slips = [], []
    for c, kind, idx in events:
        j = idx + delay
        if j >= len(c["pts"]): continue
        rois.append(roi_with_entry(c, j))
        slips.append(c["pts"][j][1] / c["pts"][idx][1])
    if rois:
        wins = sum(1 for x in rois if x > 0)
        print(f"{'+'+str(delay)+' samples':>16s} {len(rois):3d} {mean(rois)*100:+8.1f}% {median(rois)*100:+7.1f}% {wins/len(rois)*100:4.0f}% {median(slips):21.2f}x")

# inter-sample gap context
gaps = []
for c, kind, idx in events:
    pts = c["pts"]
    for a, b in zip(pts[idx:idx+3], pts[idx+1:idx+4]):
        gaps.append((b[0]-a[0])/60)
if gaps: print(f"\n(median sample spacing after signal: {median(gaps):.1f} min — '1 sample' ≈ this delay)")

# ---- CAPACITY ----
print("\n== CAPITAL CAPACITY (constant-product impact on detected liquidity) ==")
liqs = sorted(c["liq"] for c, _, _ in events)
med_liq = median(liqs)
print(f"signal-cohort detection liquidity: median ${med_liq:,.0f}, p25 ${liqs[len(liqs)//4]:,.0f}, p75 ${liqs[3*len(liqs)//4]:,.0f}")
edge = mean([roi_with_entry(c, idx) for c, _, idx in events])
print(f"simulated mean edge/trade: {edge*100:+.1f}%")
print(f"\n{'size':>8s} {'1-way impact @med liq':>22s} {'round-trip':>11s} {'edge survives?':>15s}")
for sol in (0.1, 0.25, 0.5, 1, 2.5, 5, 10):
    usd = sol * SOL_USD
    imp = usd / (med_liq / 2 + usd)  # quote side ≈ half of 'liquidity' (dexscreener liq = both sides)
    rt = 2 * imp
    print(f"{sol:6.1f} SOL (£{usd:5,.0f}) {imp*100:19.1f}% {rt*100:10.1f}% {'YES' if rt < edge else 'NO':>15s}")

# per-token capacity limit: size where RT impact = half the edge
print(f"\nper-trade size cap (RT impact = 50% of edge) at median liq: "
      f"${edge/2 * med_liq/2 / (1 - edge/2):,.0f} ≈ {edge/2 * med_liq/2 / (1 - edge/2) / SOL_USD:.2f} SOL")
