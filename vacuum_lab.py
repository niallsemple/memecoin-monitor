#!/usr/bin/env python3
"""vacuum_lab — post-sweep liquidity-vacuum detector (memo #37, idea 7).

Signal: L_active collapses (big swap knocks LPs out of range / LPs pull).
  ratio = liq_active_now / liq_active_5min_ago << 1
Then measure: refill half-life (seconds until liq_active doubles from trough),
and whether the vacuum coincides with price stability (active_bin settles).

Data: bin_snapshots.jsonl (14s cadence, per pool).
"""
import json, statistics
from collections import defaultdict

SNAP = "bin_snapshots.jsonl"
DROP_TH = 0.60        # liq_active falls to <=60% of 5min ago = vacuum
LOOKBACK_S = 300
MIN_INTERVAL_S = 120

def load():
    series = defaultdict(list)
    for line in open(SNAP):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("liq_active") is not None and d.get("t"):
            series[d["pool"]].append((d["t"], d["liq_active"], d["active_bin"]))
    for p in series:
        series[p].sort()
    return series

def analyze(pts):
    events = []
    for i, (t, la, ab) in enumerate(pts):
        prev = None
        for j in range(i - 1, -1, -1):
            if t - pts[j][0] >= LOOKBACK_S:
                prev = pts[j]
                break
        if not prev or prev[1] <= 0:
            continue
        ratio = la / prev[1]
        if ratio <= DROP_TH:
            if events and t - events[-1]["t"] < MIN_INTERVAL_S:
                continue
            # refill half-life: first time liq_active >= 2x trough value
            def time_to(mult):
                for t2, la2, _ in pts[i:]:
                    if la2 >= la * mult:
                        return t2 - t
                return None
            # bin stability after vacuum: does active_bin stop moving?
            bins_after = [b for _, _, b in pts[i:] if _ is not None][:20]
            bin_drift = (max(bins_after) - min(bins_after)) if len(bins_after) > 5 else None
            events.append({
                "t": t, "ratio": ratio,
                "t_double": time_to(2.0), "t_recover": time_to(prev[1] / la if la > 0 else 99),
                "bin_drift_5min": bin_drift,
            })
    return events

def main():
    series = load()
    all_events = []
    for pool, pts in series.items():
        ev = analyze(pts)
        if ev:
            print(f"  {pool[:8]}: {len(ev)} vacuums")
        all_events.extend((pool, e) for e in ev)
    if not all_events:
        print("NO vacuum events yet — either quiet tape or series too young.")
        return
    n = len(all_events)
    ratios = [e["ratio"] for _, e in all_events]
    td = [e["t_double"] for _, e in all_events if e["t_double"] is not None]
    drifts = [e["bin_drift_5min"] for _, e in all_events if e["bin_drift_5min"] is not None]
    print(f"\n=== vacuum events: {n} ===")
    print(f"depth:      median drop to {statistics.median(ratios)*100:.0f}% of prior active liq")
    if td:
        print(f"refill:     median {statistics.median(td):.0f}s to double from trough (n={len(td)})")
        unfilled = sum(1 for _, e in all_events if e["t_double"] is None)
        print(f"            {unfilled}/{n} never doubled within the observation window")
    if drifts:
        print(f"bin drift after vacuum: median {statistics.median(drifts):.0f} bins over next ~5min")

if __name__ == "__main__":
    main()
