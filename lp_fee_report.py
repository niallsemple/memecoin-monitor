#!/usr/bin/env python3
"""Realized fee-yield report for the open Meteora LP position.

Reads lp_fee_samples.jsonl (written each watch turn) and reports:
- elapsed time, in-range fraction
- fee accrual on both sides (X token units, Y lamports -> SOL)
- realized SOL/hr pace and extrapolated daily yield on sol_in
Run: python3 lp_fee_report.py
"""
import json, sys

def sol_in():
    try:
        st = json.load(open('lp_positions.json'))
        for p in st['positions']:
            if p.get('status') == 'open':
                return p.get('sol_in', 0.783)
    except Exception:
        pass
    return 0.783

SOL_IN = sol_in()

rows = [json.loads(l) for l in open('lp_fee_samples.jsonl')]
if len(rows) < 2:
    print('need >=2 samples; have', len(rows)); sys.exit(0)

# Segment on fee-counter resets (re-center creates a new position whose
# counters start at zero). Cumulative = sum of positive deltas across all
# segments; pace = current segment only.
segs = [[rows[0]]]
for r in rows[1:]:
    prev = segs[-1][-1]
    if r['fee_y_lamports'] < prev['fee_y_lamports'] or r['fee_x'] < prev['fee_x']:
        segs.append([r])  # counter reset -> new position segment
    else:
        segs[-1].append(r)

tot_y = sum(s[-1]['fee_y_lamports'] - s[0]['fee_y_lamports'] for s in segs) / 1e9
tot_x = sum(s[-1]['fee_x'] - s[0]['fee_x'] for s in segs)
t0, t1 = rows[0]['ts'], rows[-1]['ts']
dt_hr = (t1 - t0) / 3600
in_range = sum(1 for r in rows if r['in_range']) / len(rows)

cur = segs[-1]
seg_dt = (cur[-1]['ts'] - cur[0]['ts']) / 3600
seg_dy = (cur[-1]['fee_y_lamports'] - cur[0]['fee_y_lamports']) / 1e9
seg_dx = cur[-1]['fee_x'] - cur[0]['fee_x']

print(f"samples        : {len(rows)} over {dt_hr*60:.1f} min, {len(segs)} position segment(s)")
print(f"in-range share : {in_range*100:.0f}%")
print(f"fee Y total    : +{tot_y:.6f} SOL  (all segments)")
print(f"fee X total    : +{tot_x} raw (all segments)")
if len(cur) >= 2 and seg_dt > 0:
    daily = seg_dy / seg_dt * 24
    print(f"current segment: {len(cur)} samples over {seg_dt*60:.1f} min, +{seg_dy:.6f} SOL, +{seg_dx} X")
    print(f"daily pace     : {daily:.6f} SOL/day = {daily/SOL_IN*100:.2f}%/day on {SOL_IN} SOL")
else:
    print(f"current segment: {len(cur)} sample(s) since re-center — pace forms next sample")
print(f"breakeven note : needs to outrun IL + entry/exit costs (~0.02 SOL round trip)")
