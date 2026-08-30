#!/usr/bin/env python3
"""
mfg_freeroll.py — backtest the "free roll" strategy on reconstructed pool paths.

Strategy: enter when the MFG alert rule would have fired (reconstructed from
trade flow), sell fraction f of the position when price hits target T x entry
(recovering principal if f*T >= 1), let the remainder ride to the end of the
observed path. Compare against hold-to-end baseline.

Entry trigger (proxy for live alert rule, from pool trades only):
  net_sol (buys - sells, cumulative) >= 100
  buy_sol >= 20, buys >= 30, buys/sells >= 3
"""
import json, collections

TRADES = 'mfg_trades.jsonl'

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

def find_trigger(xs):
    nb = ns = 0
    buy_sol = sell_sol = 0.0
    for i, x in enumerate(xs):
        if x.get('side') == 'buy':
            nb += 1; buy_sol += x.get('sol') or 0
        else:
            ns += 1; buy_sol += 0; sell_sol += x.get('sol') or 0
        net = buy_sol - sell_sol
        if net >= 100 and buy_sol >= 20 and nb >= 30 and nb / max(ns, 1) >= 3:
            return i
    return None

def simulate(xs, entry_i, target, frac):
    entry_mc = xs[entry_i]['mcap_sol']
    if entry_mc <= 0:
        return None
    proceeds = 0.0
    exited = False
    for x in xs[entry_i + 1:]:
        r = x['mcap_sol'] / entry_mc
        if not exited and r >= target:
            proceeds += frac * target   # sell frac of position at T x entry
            exited = True
    final_r = xs[-1]['mcap_sol'] / entry_mc
    remainder = (1 - frac) * final_r if exited else final_r
    total = proceeds + remainder      # value per 1 SOL invested
    return dict(total=total, exited=exited, final_r=final_r,
                peak_note=None)

def main():
    paths = load_paths()
    grid = [(1.5, 0.75), (2.0, 0.5), (2.0, 0.75), (3.0, 0.5)]
    rows = []
    for m, xs in sorted(paths.items(), key=lambda kv: -len(kv[1])):
        if len(xs) < 50:
            continue
        ti = find_trigger(xs)
        if ti is None:
            rows.append((m, len(xs), None))
            continue
        base = xs[-1]['mcap_sol'] / xs[ti]['mcap_sol']
        sims = {}
        for T, f in grid:
            s = simulate(xs, ti, T, f)
            sims[(T, f)] = s
        rows.append((m, len(xs), dict(trigger_i=ti, n=len(xs), base=base, sims=sims)))

    traded = [r for r in rows if r[2]]
    print(f'tokens with pool paths: {len(rows)}, alert-trigger reconstructed: {len(traded)}\n')

    hdr = 'token      trades  trig@   hold-end'
    for T, f in grid:
        hdr += f'  T{T}x f{int(f*100)}%'
    print(hdr)
    agg = collections.defaultdict(list)
    agg_base = []
    for m, n, d in rows:
        if not d:
            print(f'{m[:8]}…  {n:6d}  no-trigger')
            continue
        line = f'{m[:8]}…  {n:6d}  {d["trigger_i"]:5d}  {d["base"]*100-100:+7.0f}%'
        agg_base.append(d['base'])
        for T, f in grid:
            s = d['sims'][(T, f)]
            v = s['total']
            agg[(T, f)].append(v)
            mark = '*' if s['exited'] else ' '
            line += f'  {v*100-100:+7.0f}%{mark}'
        print(line)

    def stats(vals):
        n = len(vals)
        wins = sum(1 for v in vals if v > 1)
        mean = sum(vals) / n
        return f'mean {mean*100-100:+.0f}%/trade, win {wins}/{n}'
    print()
    print(f'hold-to-end baseline : {stats(agg_base)}')
    for T, f in grid:
        ex = sum(1 for r in traded if r[2]['sims'][(T, f)]['exited'])
        print(f'free-roll T{T}x f{int(f*100)}% : {stats(agg[(T,f)])}   (target hit {ex}/{len(traded)})')
    print()
    print('* = profit target hit, principal partially/fully recovered.')
    print('caveats: mcap = marginal price x supply; trigger is a proxy;')
    print('paths cover only the first ~4h post-graduation; fills assume trade-price execution;')
    print('n is small — directional only.')

if __name__ == '__main__':
    main()
