#!/usr/bin/env python3
"""Replay: would early bin-migration exits beat the 15s tripwire?

For every trade (live + post-fix paper) with snapshot coverage, reconstruct the
active-bin path from bin_snapshots.jsonl and simulate exit at the first snapshot
where active_bin has dropped >= d bins from entry, for d in 1..5.

Economics model (Y-only SOL-side LP):
- strike (actual): recorded net from logs
- early exit at d bins down, still above our range: cost = friction only
  (~0.0008 SOL tx+rent) — position not yet converted, no IL
- false positive cost: trades that dipped d bins but recovered get exited early,
  forfeiting their recorded win; we count recorded net -> -friction instead.

Cadence caveat: snapshots are ~64s median; strikes hit ~2min post-entry, so we
typically get 1-2 snapshots in-window. Results are an upper bound on what
early detection at this cadence could save.
"""
import json, datetime
from collections import defaultdict

FIX_EPOCH = datetime.datetime(2026, 9, 12, 20, 3, 3,
                              tzinfo=datetime.timezone(datetime.timedelta(hours=1))).timestamp()
FRICTION = 0.0008

def load_snaps():
    snaps = defaultdict(list)
    for line in open('bin_snapshots.jsonl'):
        try:
            r = json.loads(line)
        except Exception:
            continue
        snaps[r['pool']].append((r['t'], r['active_bin']))
    for p in snaps:
        snaps[p].sort()
    return snaps

def load_trades():
    trades = []
    # live: join enter -> real_pnl, excluding reconciled artifacts
    rows = [json.loads(l) for l in open('hfna_live.jsonl') if l.strip()]
    rows.sort(key=lambda r: r['t'])
    corrected = [(r['t'], r['pool']) for r in rows if r.get('kind') == 'real_pnl_corrected']
    exits = {}
    for r in rows:
        if r.get('kind') == 'live_exit':
            exits[(r['pool'], round(r['t']))] = r.get('reason', '')
    for i, r in enumerate(rows):
        if r.get('kind') != 'live_enter':
            continue
        for r2 in rows[i+1:]:
            if r2.get('kind') == 'real_pnl' and r2['pool'] == r['pool']:
                if not any(r2['pool'] == p and 0 < ct - r2['t'] < 900 for ct, p in corrected):
                    trades.append({'src': 'live', 'pool': r['pool'],
                                   'entry_t': r['t'], 'exit_t': r2['t'],
                                   'net': r2['real_pnl'],
                                   'bins': r.get('bins')})
                break
    # paper post-fix
    for line in open('hfna_paper.jsonl'):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if 'net' not in r or r['t'] < FIX_EPOCH:
            continue
        trades.append({'src': 'paper', 'pool': r['pool'],
                       'entry_t': r.get('entry_t', r['t'] - 180), 'exit_t': r['t'],
                       'net': r['net'], 'reason': r.get('reason', '')})
    return trades

def path_during(snaps, pool, t0, t1):
    return [(t, ab) for t, ab in snaps.get(pool, []) if t0 - 120 <= t <= t1 + 30]

def main():
    snaps = load_snaps()
    trades = load_trades()
    print(f"trades: {len(trades)}, pools with snapshots: {len(snaps)}")

    usable = []
    for tr in trades:
        path = path_during(snaps, tr['pool'], tr['entry_t'], tr['exit_t'])
        if len(path) >= 2:
            tr['path'] = path
            usable.append(tr)
    print(f"trades with >=2 in-window snapshots: {len(usable)}\n")

    actual = sum(t['net'] for t in usable)
    print(f"ACTUAL recorded net over usable trades: {actual:+.4f} SOL\n")

    print(f"{'d bins':>6s} {'sim net':>9s} {'vs actual':>10s} {'early exits':>11s} {'false+':>7s}")
    for d in [1, 2, 3, 5, 8]:
        sim = 0.0
        early = 0
        false_pos = 0
        for tr in usable:
            p0 = tr['path']
            entry_ab = None
            for t, ab in p0:
                if t <= tr['entry_t'] + 5:
                    entry_ab = ab
            if entry_ab is None:
                entry_ab = p0[0][1]
            triggered = False
            for t, ab in p0:
                if t > tr['entry_t'] + 5 and entry_ab - ab >= d:
                    triggered = True
                    break
            if triggered:
                early += 1
                if tr['net'] > 0:
                    false_pos += 1
                sim += -FRICTION  # exit before conversion: friction only
            else:
                sim += tr['net']
        print(f"{d:6d} {sim:+9.4f} {sim - actual:+10.4f} {early:11d} {false_pos:7d}")

    # timing: on strikes, when does the first 1-bin and 3-bin drop occur vs exit?
    print("\nstrike timing (live+paper losses > friction):")
    for tr in usable:
        if tr['net'] < -0.002:
            entry_ab = tr['path'][0][1]
            first1 = next((t - tr['entry_t'] for t, ab in tr['path']
                           if t > tr['entry_t'] + 5 and entry_ab - ab >= 1), None)
            first3 = next((t - tr['entry_t'] for t, ab in tr['path']
                           if t > tr['entry_t'] + 5 and entry_ab - ab >= 3), None)
            dur = tr['exit_t'] - tr['entry_t']
            print(f"  {tr['src']:5s} {tr['pool'][:8]} net={tr['net']:+.4f} "
                  f"life={dur:.0f}s first-1bin={'%4.0fs' % first1 if first1 else '  n/a'} "
                  f"first-3bin={'%4.0fs' % first3 if first3 else '  n/a'}")

if __name__ == '__main__':
    main()
