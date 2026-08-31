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

    def run_model(fill_mode):
        """fill_mode 'mark': exit at trigger trade price.
        'next': exit at NEXT trade's price (honest fill incl. gap)."""
        proceeds = 0.0
        pos = 1.0
        peak = 1.0
        freerolled = False
        exit_reason = None
        exit_t = None
        gaps = []
        body = xs[ti + 1:]
        for j, x in enumerate(body):
            r = x['mcap_sol'] / emc
            peak = max(peak, r)

            def fill_r(trig_r):
                if fill_mode == 'next' and j + 1 < len(body):
                    fr_ = body[j + 1]['mcap_sol'] / emc
                    gaps.append(fr_ / max(trig_r, 1e-9))
                    return fr_
                return trig_r

            if not freerolled and r >= T_TARGET:
                fr_price = fill_r(T_TARGET) if fill_mode == 'next' else T_TARGET
                proceeds += F_SELL * fr_price
                pos -= F_SELL
                freerolled = True
            if r <= TRAIL * peak and pos > 0:
                proceeds += pos * fill_r(r)
                pos = 0
                exit_reason = 'trail'
                exit_t = x['t']
                break
            if not freerolled and (x['t'] - t0) / 60 >= TIMESTOP_MIN:
                proceeds += pos * fill_r(r)
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
        return dict(total=total, status=status, exit_reason=exit_reason,
                    exit_t=exit_t, freerolled=freerolled, peak=peak,
                    mark=mark, gaps=gaps)

    mk = run_model('mark')
    nx = run_model('next')
    last = xs[-1]
    return dict(
        mint=xs[0]['mint'], entry_t=t0, entry_mcap=emc,
        freerolled=nx['freerolled'], peak=round(nx['peak'], 3),
        status=nx['status'], exit_reason=nx['exit_reason'], exit_t=nx['exit_t'],
        mark=round(nx['mark'], 3) if nx['mark'] else None,
        ret=round(nx['total'] - 1, 4),
        ret_mark=round(mk['total'] - 1, 4),
        gap_mult=round(sum(nx['gaps']) / len(nx['gaps']), 3) if nx['gaps'] else None,
        last_t=last['t'], n_trades=len(xs),
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
    print(f'paper positions: {len(positions)} ({len(closed)} closed, {len(open_)} open)')
    print('fills: REALISTIC = exit at next trade price (gap-inclusive); MARK = trigger price\n')
    print(f'{"mint":10s} {"status":7s} {"exit":9s} {"freeRoll":8s} {"peak":6s} {"real":>7s} {"mark":>7s} {"gap":>6s}')
    for r in positions:
        g = f"{r['gap_mult']:.2f}" if r.get('gap_mult') else '—'
        print(f"{r['mint'][:8]}… {r['status']:7s} {str(r['exit_reason']):9s} "
              f"{str(r['freerolled']):8s} {r['peak']:5.1f}x {r['ret']*100:+6.0f}% "
              f"{r['ret_mark']*100:+6.0f}% {g:>6s}")
    if closed:
        vals = [r['ret'] for r in closed]
        wins = sum(1 for v in vals if v > 0)
        mvals = [r['ret_mark'] for r in closed]
        print(f'\nclosed expectancy REALISTIC: {sum(vals)/len(vals)*100:+.0f}%/trade, win {wins}/{len(closed)}')
        print(f'closed expectancy MARK     : {sum(mvals)/len(mvals)*100:+.0f}%/trade')
        gaps = [r['gap_mult'] for r in closed if r.get('gap_mult')]
        if gaps:
            print(f'mean exit gap multiplier   : {sum(gaps)/len(gaps):.2f} (1.00 = no gap; <1 = slipped)')
    if open_:
        vals = [r['ret'] for r in open_]
        print(f'open marks     : {sum(vals)/len(vals)*100:+.0f}%/trade avg (unrealized)')
    print('\npaper only — no real orders. Log:', OUT)


if __name__ == '__main__':
    main()
