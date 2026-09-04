#!/usr/bin/env python3
"""§288 wallet intelligence: per-wallet PnL from tape + persistence test.

Pass 1: mfg_trades.jsonl -> per-mint sorted (t, mcap) price path.
Pass 2: mfg_wallet_trades.jsonl -> per wallet-mint: sol_in, sol_out, est tokens.
PnL = sol_out + tokens_left * final_mcap - sol_in  (SOL units).
Persistence: split wallet tape at time midpoint; Spearman corr of H1 vs H2 wallet PnL.
"""
import json, bisect, statistics
from collections import defaultdict

MON = '/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor'

def load_prices():
    series = defaultdict(list)
    with open(f'{MON}/mfg_trades.jsonl') as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            m, t, c = r.get('mint'), r.get('t'), r.get('mcap_sol')
            if m and t and c:
                series[m].append((t, c))
    for m in series:
        series[m].sort()
    return series

def price_at(series, ts_cache, m, t):
    pts = series.get(m)
    if not pts:
        return None
    ts = ts_cache.get(m)
    if ts is None:
        ts = [p[0] for p in pts]
        ts_cache[m] = ts
    i = bisect.bisect_right(ts, t) - 1
    if i < 0:
        i = 0
    return pts[i][1]

def main():
    series = load_prices()
    print('mints priced:', len(series))
    ts_cache = {}
    # wallet -> mint -> [sol_in, sol_out, tokens]
    wm = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, 0.0]))
    t_min, t_max = None, 0
    with open(f'{MON}/mfg_wallet_trades.jsonl') as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            w, m, t, side, sol = r.get('wallet'), r.get('mint'), r.get('t'), r.get('side'), r.get('sol')
            if not (w and m and t and side and sol):
                continue
            if t_min is None or t < t_min:
                t_min = t
            if t > t_max:
                t_max = t
            px = price_at(series, ts_cache, m, t)
            if not px:
                continue
            cell = wm[w][m]
            if side == 'buy':
                cell[0] += sol
                cell[2] += sol / px
            else:
                cell[1] += sol
                cell[2] -= sol / px
    print('wallets:', len(wm), '| span: %.1f days' % ((t_max - t_min) / 86400))
    # per-wallet totals + per-half splits
    mid = (t_min + t_max) / 2
    half = defaultdict(lambda: [[0.0, 0, 0], [0.0, 0, 0]])  # wallet -> [ [pnl_proxy,n,spent] x2 ]
    totals = []
    for w, mints in wm.items():
        pnl = 0.0
        spent = 0.0
        n = 0
        for m, (si, so, tk) in mints.items():
            final = series[m][-1][1] if series.get(m) else 0
            pnl += so + max(tk, 0) * final - si
            spent += si
            n += 1
        if n >= 3 and spent >= 0.05:
            totals.append((w, pnl, spent, n))
    totals.sort(key=lambda x: -x[1])
    print('wallets with >=3 mints and >=0.05 SOL spent:', len(totals))
    print('\nTOP 15 by est PnL:')
    for w, pnl, spent, n in totals[:15]:
        print('  %s pnl %+.3f spent %.3f n=%d roi %+.0f%%' % (w[:10], pnl, spent, n, 100 * pnl / spent))
    # persistence: recompute per half (price-valued at final mcap; approximation ok for ranking)
    h1, h2 = {}, {}
    ts_cache2 = {}
    with open(f'{MON}/mfg_wallet_trades.jsonl') as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            w, m, t, side, sol = r.get('wallet'), r.get('mint'), r.get('t'), r.get('side'), r.get('sol')
            if not (w and m and t and side and sol):
                continue
            px = price_at(series, ts_cache2, m, t)
            if not px:
                continue
            d = h1 if t < mid else h2
            cell = d.setdefault(w, defaultdict(lambda: [0.0, 0.0, 0.0]))[m]
            if side == 'buy':
                cell[0] += sol; cell[2] += sol / px
            else:
                cell[1] += sol; cell[2] -= sol / px
    def pnl_of(d, w):
        p = 0.0
        for m, (si, so, tk) in d[w].items():
            final = series[m][-1][1] if series.get(m) else 0
            p += so + max(tk, 0) * final - si
        return p
    common = [w for w in h1 if w in h2 and len(h1[w]) >= 3 and len(h2[w]) >= 3]
    if len(common) >= 30:
        x = [pnl_of(h1, w) for w in common]
        y = [pnl_of(h2, w) for w in common]
        rx = statistics.quantiles([sorted(x).index(v) for v in x]) if False else None
        # spearman via rank
        def ranks(v):
            order = sorted(range(len(v)), key=lambda i: v[i])
            r = [0] * len(v)
            for rank, i in enumerate(order):
                r[i] = rank
            return r
        rx, ry = ranks(x), ranks(y)
        n_ = len(rx)
        mx, my = statistics.mean(rx), statistics.mean(ry)
        cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
        sx = (sum((a - mx) ** 2 for a in rx)) ** .5
        sy = (sum((b - my) ** 2 for b in ry)) ** .5
        rho = cov / (sx * sy) if sx and sy else 0
        print('\npersistence: %d wallets active both halves (>=3 mints each)' % n_)
        print('Spearman rank corr H1 PnL vs H2 PnL: %+.3f' % rho)
        pos1 = [w for w in common if pnl_of(h1, w) > 0]
        pos2pos = sum(1 for w in pos1 if pnl_of(h2, w) > 0)
        print('wallets profitable in H1: %d; of those still profitable in H2: %d (%.0f%%)' % (
            len(pos1), pos2pos, 100 * pos2pos / len(pos1) if pos1 else 0))

if __name__ == '__main__':
    main()
