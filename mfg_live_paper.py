#!/usr/bin/env python3
"""
mfg_live_paper.py — live paper-trader for the free-roll strategy.

Strategy (best config from §56e backtest, +12%/trade on n=9):
  ENTRY : E25 early trigger — cumulative net pool flow >= 25 SOL, >= 10 buys,
          buys/sells >= 2 (reconstructed from pool trades)
  EXIT 1: free-roll — when price >= 1.5x entry, sell 75% (recovers 1.125x stake)
  EXIT 2: trailing stop — exit everything if price < 50% of post-entry peak
  EXIT 3: time-stop — if 1.5x not hit within 120 min, exit at market

Run any time: rebuilds all positions trade-by-trade from mfg_trades.jsonl,
writes mfg_paper_trades.jsonl (one line per closed/open position, idempotent
by mint) and prints a scoreboard. Paper only — no real orders.
"""
import json, collections, time, os

TRADES = 'mfg_trades.jsonl'
OUT = 'mfg_paper_trades.jsonl'

T_TARGET, F_SELL = 1.5, 0.75
TRAIL = 0.5
TIMESTOP_MIN = 120
NET_MIN, NB_MIN, FLOW_MIN = 25, 10, 2


def load_paths():
    tr = collections.defaultdict(list)
    for line in open(TRADES):
        try:
            x = json.loads(line)
        except Exception:
            continue
        if x.get('venue') != 'pool' or not x.get('t') or not x.get('mcap_sol'):
            continue
        tr[x['mint']].append(x)
    for m in tr:
        tr[m].sort(key=lambda x: x['t'])
    return tr


def trade_position(xs):
    """Simulate the strategy over the full path. Returns position record or None."""
    nb = ns = 0
    bs = ss = 0.0
    ti = None
    for i, x in enumerate(xs):
        if x.get('side') == 'buy':
            nb += 1; bs += x.get('sol') or 0
        else:
            ns += 1; ss += x.get('sol') or 0
        if (bs - ss) >= NET_MIN and nb >= NB_MIN and nb / max(ns, 1) >= FLOW_MIN:
            ti = i
            break
    if ti is None:
        return None
    emc = xs[ti]['mcap_sol']
    t0 = xs[ti]['t']
    if emc <= 0:
        return None
    proceeds = 0.0
    pos = 1.0
    peak = 1.0
    freerolled = False
    exit_reason = None
    exit_t = None
    for x in xs[ti + 1:]:
        r = x['mcap_sol'] / emc
        peak = max(peak, r)
        if not freerolled and r >= T_TARGET:
            proceeds += F_SELL * T_TARGET
            pos -= F_SELL
            freerolled = True
        if r <= TRAIL * peak and pos > 0:
            proceeds += pos * r
            pos = 0
            exit_reason = 'trail'
            exit_t = x['t']
            break
        if not freerolled and (x['t'] - t0) / 60 >= TIMESTOP_MIN:
            proceeds += pos * r
            pos = 0
            exit_reason = 'timestop'
            exit_t = x['t']
            break
    last = xs[-1]
    if pos > 0:
        mark = last['mcap_sol'] / emc
        status = 'open'
        total = proceeds + pos * mark
    else:
        mark = None
        status = 'closed'
        total = proceeds
    return dict(
        mint=xs[0]['mint'], entry_t=t0, entry_mcap=emc,
        freerolled=freerolled, peak=round(peak, 3),
        status=status, exit_reason=exit_reason, exit_t=exit_t,
        mark=round(mark, 3) if mark else None,
        ret=round(total - 1, 4), last_t=last['t'], n_trades=len(xs),
    )


def main():
    paths = load_paths()
    positions = []
    for m, xs in paths.items():
        if len(xs) < 50:
            continue
        rec = trade_position(xs)
        if rec:
            positions.append(rec)
    positions.sort(key=lambda r: r['entry_t'])

    with open(OUT, 'w') as f:
        for r in positions:
            f.write(json.dumps(r) + '\n')

    closed = [r for r in positions if r['status'] == 'closed']
    open_ = [r for r in positions if r['status'] == 'open']
    print(f'paper positions: {len(positions)} ({len(closed)} closed, {len(open_)} open)\n')
    print(f'{"mint":10s} {"status":7s} {"exit":9s} {"freeRoll":8s} {"peak":6s} {"return":>8s}')
    for r in positions:
        print(f"{r['mint'][:8]}… {r['status']:7s} {str(r['exit_reason']):9s} "
              f"{str(r['freerolled']):8s} {r['peak']:5.1f}x {r['ret']*100:+7.0f}%")
    if closed:
        vals = [r['ret'] for r in closed]
        wins = sum(1 for v in vals if v > 0)
        print(f'\nclosed expectancy: {sum(vals)/len(vals)*100:+.0f}%/trade, win {wins}/{len(closed)}')
    if open_:
        vals = [r['ret'] for r in open_]
        print(f'open marks     : {sum(vals)/len(vals)*100:+.0f}%/trade avg (unrealized)')
    print('\npaper only — no real orders. Log:', OUT)


if __name__ == '__main__':
    main()
