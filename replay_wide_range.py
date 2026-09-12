#!/usr/bin/env python3
"""Wide-range replay: would 5/7/10-bin Y-only ranges beat the 3-bin standard?

Model per trade:
- time-in-range (TIR): seconds the active bin spent inside [entry_ab - w,
  entry_ab - 1], from snapshots (>=64s cadence, linear between snapshots)
- fees scale as fees_3 * (TIR_w / TIR_3) * (3 / w)   [same SOL spread over w
  bins -> 1/w density, but survives longer]
- strikes: a range is "struck" if active bin falls below (entry_ab - w);
  then net = -FR and conversion avoided only if we exit at boundary
  (conservatively: struck ranges take recorded strike loss scaled by w/3
  price distance? No — conservative: full recorded strike loss)
- friction per trade unchanged (one position account regardless of width,
  approximately; extra bin-array rent ~0.0002 for >~70 bins, not hit here)

Anchor: recorded fees for the actual 3-bin trades (paper rows carry fees;
live trades don't record fees separately — use paper post-fix only for the
fee anchor, live trades contribute TIR/survival stats).
"""
import json, datetime
from collections import defaultdict

FIX = datetime.datetime(2026, 9, 12, 20, 3, 3,
                        tzinfo=datetime.timezone(datetime.timedelta(hours=1))).timestamp()
FR = 0.0008
WIDTHS = [3, 5, 7, 10, 15]

snaps = defaultdict(list)
for line in open('bin_snapshots.jsonl'):
    try:
        r = json.loads(line)
    except Exception:
        continue
    snaps[r['pool']].append(r)
for p in snaps:
    snaps[p].sort(key=lambda r: r['t'])

trades = []
rows = [json.loads(l) for l in open('hfna_live.jsonl') if l.strip()]
rows.sort(key=lambda r: r['t'])
corr = [(r['t'], r['pool']) for r in rows if r.get('kind') == 'real_pnl_corrected']
for i, r in enumerate(rows):
    if r.get('kind') != 'live_enter':
        continue
    for r2 in rows[i+1:]:
        if r2.get('kind') == 'real_pnl' and r2['pool'] == r['pool']:
            if not any(r2['pool'] == p and 0 < ct - r2['t'] < 900 for ct, p in corr):
                trades.append({'src': 'live', 'pool': r['pool'], 'entry_t': r['t'],
                               'exit_t': r2['t'], 'net': r2['real_pnl'], 'fees': None})
            break
for line in open('hfna_paper.jsonl'):
    try:
        r = json.loads(line)
    except Exception:
        continue
    if 'net' not in r or r['t'] < FIX:
        continue
    trades.append({'src': 'paper', 'pool': r['pool'],
                   'entry_t': r.get('entry_t', r['t'] - 180), 'exit_t': r['t'],
                   'net': r['net'], 'fees': r.get('fees')})

def tir_and_strike(tr, w):
    path = [r for r in snaps.get(tr['pool'], [])
            if tr['entry_t'] - 120 <= r['t'] <= tr['exit_t'] + 30]
    if len(path) < 2:
        return None
    eab = next((r['active_bin'] for r in path if r['t'] <= tr['entry_t'] + 5),
               path[0]['active_bin'])
    lo, hi = eab - w, eab - 1
    tir = 0.0
    struck = False
    prev = None
    for r in path:
        if r['t'] <= tr['entry_t']:
            prev = r
            continue
        if prev is not None:
            dt = r['t'] - prev['t']
            mid = (prev['active_bin'] + r['active_bin']) / 2
            if lo <= mid <= hi:
                tir += dt
        if r['active_bin'] < lo:
            struck = True
            break
        prev = r
    return tir, struck, tr['exit_t'] - tr['entry_t']

results = {w: {'net': 0.0, 'n': 0, 'struck': 0} for w in WIDTHS}
per_trade_rows = []
for tr in trades:
    base = tir_and_strike(tr, 3)
    if base is None:
        continue
    tir3, struck3, life = base
    for w in WIDTHS:
        tir_w, struck_w, _ = tir_and_strike(tr, w)
        if struck_w:
            net_w = tr['net'] if tr['net'] < -0.002 else -FR  # strike: recorded loss
        else:
            if tr['fees'] is not None and tir3 > 0 and tr['net'] > -0.002:
                fees_w = tr['fees'] * (tir_w / tir3) * (3 / w)
            elif tr['net'] > -0.002 and tr['fees'] is None:
                # live rows: infer fees ~ net + friction for non-strikes
                fees3 = tr['net'] + FR
                fees_w = fees3 * (tir_w / tir3) * (3 / w) if tir3 > 0 else 0
            else:
                fees_w = 0
            net_w = fees_w - FR
        results[w]['net'] += net_w
        results[w]['n'] += 1
        results[w]['struck'] += struck_w

print(f"{'width':>6s} {'sim net':>9s} {'vs 3-bin':>9s} {'struck':>7s} {'exp/trade':>10s}")
base_net = results[3]['net']
for w in WIDTHS:
    r = results[w]
    print(f"{w:6d} {r['net']:+9.4f} {r['net'] - base_net:+9.4f} "
          f"{r['struck']:4d}/{r['n']:<3d} {r['net']/max(r['n'],1):+10.5f}")
