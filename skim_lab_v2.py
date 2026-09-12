#!/usr/bin/env python3
"""skim_lab v2 — burst-triggered LP crowding from dense bin snapshots.

Question: when liquidity floods into a pool's active range (fee-chasing LPs),
how fast does it arrive, how much does it dilute an incumbent's fee share,
and does it persist?

Data: bin_snapshots.jsonl (t, pool, active_bin, bin_step, liq_active, liq_pm10, bins)
"""
import json, math, statistics
from collections import defaultdict

SNAP = "bin_snapshots.jsonl"
INFLOW_TH = 0.25      # +25% liq_pm10 vs 5min ago = inflow event
LOOKBACK_S = 300
MIN_INTERVAL_S = 20   # min spacing between distinct events per pool

def load():
    series = defaultdict(list)
    for line in open(SNAP):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("liq_pm10") and d.get("t"):
            series[d["pool"]].append((d["t"], d["liq_active"], d["liq_pm10"], d["active_bin"]))
    for p in series:
        series[p].sort()
    return series

def analyze(pool, pts):
    events = []
    for i, (t, la, lp, ab) in enumerate(pts):
        # find point ~5min ago
        prev = None
        for j in range(i - 1, -1, -1):
            if t - pts[j][0] >= LOOKBACK_S:
                prev = pts[j]
                break
        if not prev or prev[2] <= 0:
            continue
        growth = lp / prev[2] - 1
        if growth >= INFLOW_TH:
            if events and t - events[-1]["t"] < MIN_INTERVAL_S:
                continue
            # dilution of an incumbent share = 1/(1+growth)
            # persistence: does liq_pm10 stay elevated 30/60min later?
            def liq_at(dt):
                cand = [p for p in pts if p[0] >= t + dt]
                return cand[0][2] if cand else None
            l30, l60 = liq_at(1800), liq_at(3600)
            # concentration: active-bin liquidity growth vs pm10 growth
            act_growth = (la / prev[1] - 1) if prev[1] > 0 else None
            events.append({
                "t": t, "growth": growth, "dilution": 1 / (1 + growth),
                "act_growth": act_growth,
                "persist30": (l30 / lp) if l30 else None,
                "persist60": (l60 / lp) if l60 else None,
            })
    return events

def main():
    series = load()
    all_events = []
    print(f"pools: {len(series)}")
    for pool, pts in series.items():
        ev = analyze(pool, pts)
        span_h = (pts[-1][0] - pts[0][0]) / 3600
        if ev:
            print(f"  {pool[:8]}: {len(ev)} inflow events over {span_h:.1f}h")
        all_events.extend((pool, e) for e in ev)
    if not all_events:
        print("\nNO inflow events yet — series too young or threshold too high.")
        return
    n = len(all_events)
    growths = [e["growth"] for _, e in all_events]
    dils = [e["dilution"] for _, e in all_events]
    p30 = [e["persist30"] for _, e in all_events if e["persist30"] is not None]
    p60 = [e["persist60"] for _, e in all_events if e["persist60"] is not None]
    conc = [e["act_growth"] for _, e in all_events if e["act_growth"] is not None]
    print(f"\n=== inflow events: {n} ===")
    print(f"size:       median +{statistics.median(growths)*100:.0f}%  p90 +{sorted(growths)[int(n*0.9)]*100:.0f}%")
    print(f"dilution:   median incumbent keeps {statistics.median(dils)*100:.0f}% of fee share")
    if p30:
        print(f"persist30:  median {statistics.median(p30)*100:.0f}% of inflow still there 30min later (n={len(p30)})")
    if p60:
        print(f"persist60:  median {statistics.median(p60)*100:.0f}% still there 60min later (n={len(p60)})")
    if conc:
        print(f"active-bin concentration: median act-liq growth {statistics.median(conc)*100:+.0f}% (fee-chasing if >> pm10 growth)")

if __name__ == "__main__":
    main()
