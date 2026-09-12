#!/usr/bin/env python3
"""False-positive analysis: what separates a 2-bin dip that recovers (win)
from a 2-bin dip that is a strike?

For every trade whose active-bin path dips >=2 bins from entry, compare:
- dip velocity (bins/sec to first 2-bin touch)
- max depth beyond 2 bins within window
- recovery: did active bin return to entry level within the trade?
- liquidity behavior: liq_active trajectory during the dip (refill vs drain)
- time of first dip relative to entry
- outcome (recorded net)

Goal: find a secondary filter so the d=2 early-exit keeps winners.
"""
import json, datetime
from collections import defaultdict

FIX_EPOCH = datetime.datetime(2026, 9, 12, 20, 3, 3,
                              tzinfo=datetime.timezone(datetime.timedelta(hours=1))).timestamp()

def load_snaps():
    snaps = defaultdict(list)
    for line in open('bin_snapshots.jsonl'):
        try:
            r = json.loads(line)
        except Exception:
            continue
        snaps[r['pool']].append(r)
    for p in snaps:
        snaps[p].sort(key=lambda r: r['t'])
    return snaps

def load_trades():
    trades = []
    rows = [json.loads(l) for l in open('hfna_live.jsonl') if l.strip()]
    rows.sort(key=lambda r: r['t'])
    corrected = [(r['t'], r['pool']) for r in rows if r.get('kind') == 'real_pnl_corrected']
    for i, r in enumerate(rows):
        if r.get('kind') != 'live_enter':
            continue
        for r2 in rows[i+1:]:
            if r2.get('kind') == 'real_pnl' and r2['pool'] == r['pool']:
                if not any(r2['pool'] == p and 0 < ct - r2['t'] < 900 for ct, p in corrected):
                    trades.append({'src': 'live', 'pool': r['pool'],
                                   'entry_t': r['t'], 'exit_t': r2['t'],
                                   'net': r2['real_pnl']})
                break
    for line in open('hfna_paper.jsonl'):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if 'net' not in r or r['t'] < FIX_EPOCH:
            continue
        trades.append({'src': 'paper', 'pool': r['pool'],
                       'entry_t': r.get('entry_t', r['t'] - 180), 'exit_t': r['t'],
                       'net': r['net']})
    return trades

def main():
    snaps = load_snaps()
    trades = load_trades()
    rows_out = []
    for tr in trades:
        path = [r for r in snaps.get(tr['pool'], [])
                if tr['entry_t'] - 120 <= r['t'] <= tr['exit_t'] + 30]
        if len(path) < 3:
            continue
        entry_ab = next((r['active_bin'] for r in path if r['t'] <= tr['entry_t'] + 5),
                        path[0]['active_bin'])
        # dip analysis
        dip2_t = None
        max_depth = 0
        recovered = False
        liq_at_entry = next((r['liq_active'] for r in path if r['t'] <= tr['entry_t'] + 5),
                            path[0]['liq_active'])
        liq_min_ratio = 1.0
        for r in path:
            if r['t'] <= tr['entry_t'] + 5:
                continue
            depth = entry_ab - r['active_bin']
            max_depth = max(max_depth, depth)
            if liq_at_entry:
                liq_min_ratio = min(liq_min_ratio, r['liq_active'] / liq_at_entry)
            if depth >= 2 and dip2_t is None:
                dip2_t = r['t']
            if dip2_t and r['active_bin'] >= entry_ab:
                recovered = True
        if dip2_t is None:
            continue  # never dipped 2 bins
        vel = 2.0 / max(dip2_t - tr['entry_t'], 1)
        rows_out.append({
            'src': tr['src'], 'pool': tr['pool'][:8], 'net': tr['net'],
            'win': tr['net'] > 0,
            't_dip2': dip2_t - tr['entry_t'], 'vel': vel,
            'max_depth': max_depth, 'recovered': recovered,
            'liq_min_ratio': liq_min_ratio,
        })

    wins = [r for r in rows_out if r['win']]
    losses = [r for r in rows_out if not r['win']]
    print(f"trades with a >=2-bin dip: {len(rows_out)}  "
          f"(recovered-and-won: {len(wins)}, strikes: {len(losses)})\n")
    hdr = f"{'src':6s}{'pool':10s}{'net':>9s} {'t_dip2':>7s} {'vel':>7s} {'maxd':>5s} {'recov':>6s} {'liqmin':>7s}"
    print(hdr)
    for r in sorted(rows_out, key=lambda x: -x['net']):
        print(f"{r['src']:6s}{r['pool']:10s}{r['net']:+9.4f} {r['t_dip2']:6.0f}s "
              f"{r['vel']:7.4f} {r['max_depth']:5d} {str(r['recovered']):>6s} {r['liq_min_ratio']:7.3f}")

    if wins and losses:
        print("\nmeans (recovered-winners vs strikes):")
        for k in ['t_dip2', 'vel', 'max_depth', 'liq_min_ratio']:
            mw = sum(r[k] for r in wins) / len(wins)
            ml = sum(r[k] for r in losses) / len(losses)
            print(f"  {k:14s} winners {mw:8.3f}   strikes {ml:8.3f}")
        print(f"  recovery rate  winners {sum(r['recovered'] for r in wins)}/{len(wins)}"
              f"   strikes {sum(r['recovered'] for r in losses)}/{len(losses)}")

if __name__ == '__main__':
    main()
