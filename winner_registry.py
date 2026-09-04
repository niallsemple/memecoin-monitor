#!/usr/bin/env python3
"""§289 winner-wallet registry: realized-PnL winners from graduated-coin wallet tape.

Criteria (whole-span): realized_pnl > 0 AND mints >= 5 AND spent >= 0.5 SOL.
Persistence flag: profitable on realized basis in BOTH tape halves (when active in both).
Output: winner_wallets.json  {wallet: {pnl, spent, mints, roi_pct, persistent}}
"""
import json
from collections import defaultdict

MON = '/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor'

def main():
    rows = []
    t_min, t_max = None, 0
    with open(f'{MON}/mfg_wallet_trades.jsonl') as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            w, m, t, side, sol = r.get('wallet'), r.get('mint'), r.get('t'), r.get('side'), r.get('sol')
            if w and m and t and side and sol:
                rows.append((w, m, t, side, sol))
                t_min = t if t_min is None else min(t_min, t)
                t_max = max(t_max, t)
    mid = (t_min + t_max) / 2
    span = defaultdict(lambda: [0.0, 0.0, set()])   # w -> [in, out, mints]
    h1 = defaultdict(lambda: [0.0, 0.0, 0])
    h2 = defaultdict(lambda: [0.0, 0.0, 0])
    for w, m, t, side, sol in rows:
        c = span[w]
        if side == 'buy':
            c[0] += sol
        else:
            c[1] += sol
        c[2].add(m)
        d = h1 if t < mid else h2
        if side == 'buy':
            d[w][0] += sol
        else:
            d[w][1] += sol
        d[w][2] += 1
    reg = {}
    for w, (si, so, mints) in span.items():
        pnl = so - si
        n = len(mints)
        if pnl > 0 and n >= 5 and si >= 0.5:
            p1 = h1[w][1] - h1[w][0] if h1[w][2] >= 3 else None
            p2 = h2[w][1] - h2[w][0] if h2[w][2] >= 3 else None
            persistent = (p1 is not None and p2 is not None and p1 > 0 and p2 > 0)
            reg[w] = dict(pnl=round(pnl, 4), spent=round(si, 4), mints=n,
                          roi_pct=round(100 * pnl / si, 1), persistent=persistent)
    out = f'{MON}/winner_wallets.json'
    with open(out, 'w') as f:
        json.dump(reg, f, indent=1)
    print('registry size:', len(reg))
    print('persistent winners:', sum(1 for v in reg.values() if v['persistent']))
    tot = sum(v['pnl'] for v in reg.values())
    print('combined realized pnl: %+.2f SOL' % tot)
    for w, v in sorted(reg.items(), key=lambda kv: -kv[1]['pnl'])[:10]:
        print('  %s pnl %+.2f roi %+.0f%% mints %d persistent %s' % (w[:10], v['pnl'], v['roi_pct'], v['mints'], v['persistent']))
    print('written:', out)

if __name__ == '__main__':
    main()
