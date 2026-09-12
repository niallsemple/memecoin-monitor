#!/usr/bin/env python3
"""hfna_scan — full HFNA state measurement (memo #37): vacuum + price settled.

HFNA window = liquidity vacuum (liq_active <= 60% of 5min ago)
              AND price settles afterwards (active bin drift <= N bins over 60s
              starting S seconds after the vacuum).

For each vacuum, scan post-event snapshots for the first moment where the
60s-forward bin drift is <= FLAT_TH. That's the tradeable window open.
Measure: how often it opens, how long after the vacuum, how long it stays open.
"""
import json, statistics
from collections import defaultdict

SNAP = "bin_snapshots.jsonl"
DROP_TH = 0.60
LOOKBACK_S = 300
MIN_INTERVAL_S = 120
FLAT_TH = 5        # bins — active bin must stay within +-5 over the settle window
SETTLE_WIN_S = None  # adaptive: 3x per-pool median sampling interval (min 180s)
MAX_WAIT_S = 900   # give up waiting for settlement after 15min

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

def scan(pts):
    """Return list of vacuum events with settlement info."""
    # adaptive settle window: 3x median sampling interval, min 180s
    intervals = [pts[i+1][0]-pts[i][0] for i in range(len(pts)-1)]
    win = max(180.0, 3*statistics.median(intervals)) if intervals else 300.0
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
        if ratio > DROP_TH:
            continue
        if events and t - events[-1]["t_vac"] < MIN_INTERVAL_S:
            continue
        # find first settled moment after vacuum
        settled_at = None
        open_until = None
        for k in range(i, len(pts)):
            tk, _, _ = pts[k]
            if tk - t > MAX_WAIT_S:
                break
            fwd = [b for t2, _, b in pts[k:] if t2 <= tk + win]
            if len(fwd) >= 2 and max(fwd) - min(fwd) <= FLAT_TH:
                settled_at = tk
                # how long does settlement hold? (drift stays <= FLAT_TH)
                for m in range(k, len(pts)):
                    tm = pts[m][0]
                    fwd2 = [b for t2, _, b in pts[m:] if t2 <= tm + win]
                    if len(fwd2) >= 2 and max(fwd2) - min(fwd2) > FLAT_TH:
                        open_until = tm
                        break
                break
        events.append({
            "t_vac": t, "ratio": ratio,
            "settle_lag": (settled_at - t) if settled_at else None,
            "open_dur": (open_until - settled_at) if (settled_at and open_until) else None,
        })
    return events

def main():
    series = load()
    all_ev = []
    for pool, pts in series.items():
        ev = scan(pts)
        all_ev.extend(ev)
    n = len(all_ev)
    if not n:
        print("no vacuums yet")
        return
    settled = [e for e in all_ev if e["settle_lag"] is not None]
    print(f"vacuums: {n}   settled (HFNA window opened): {len(settled)} ({len(settled)/n*100:.0f}%)")
    if settled:
        lags = [e["settle_lag"] for e in settled]
        durs = [e["open_dur"] for e in settled if e["open_dur"] is not None]
        print(f"settle lag:   median {statistics.median(lags):.0f}s  p25 {sorted(lags)[len(lags)//4]:.0f}s  p90 {sorted(lags)[int(len(lags)*0.9)]:.0f}s")
        if durs:
            print(f"window open:  median {statistics.median(durs):.0f}s  max {max(durs):.0f}s (n={len(durs)})")
        span_h = 2.6  # current series span; refine as it grows
        print(f"HFNA frequency: ~{len(settled)/span_h:.1f} windows/hour across {len(series)} pools")

if __name__ == "__main__":
    main()
