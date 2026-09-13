#!/usr/bin/env python3
"""ab_score.py — running A/B scorecard: 3-bin engine vs w7 (boundary exit).

Reads hfna_paper.jsonl (post fee-cap fix only) and hfna_paper_w7.jsonl.
Prints per-engine: trades, wins, strikes (tripwire), dead fills (fees~0),
boundary saves, net, expectancy. Plus the decision metric:
  w7 value = avoided strike losses - density give-up on shared windows.
"""
import json, datetime, os

MON = os.path.dirname(os.path.abspath(__file__))
FIX = datetime.datetime(2026, 9, 12, 20, 3, 3,
                        tzinfo=datetime.timezone(datetime.timedelta(hours=1))).timestamp()

def load(fn, fix=None):
    out = []
    p = os.path.join(MON, fn)
    if not os.path.exists(p):
        return out
    for line in open(p):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if 'net' not in r:
            continue
        if fix and r['t'] < fix:
            continue
        out.append(r)
    return out

def summarize(name, rows):
    if not rows:
        print(f"{name}: no trades")
        return 0.0
    n = len(rows)
    wins = sum(1 for r in rows if r['net'] > 0)
    strikes = sum(1 for r in rows if 'tripwire' in r.get('reason', ''))
    dead = sum(1 for r in rows if r.get('fees', 1) < 0.0001)
    saves = sum(1 for r in rows if 'boundary' in r.get('reason', ''))
    net = sum(r['net'] for r in rows)
    print(f"{name}: {n} trades | {wins}W {n-wins}L | strikes {strikes} | "
          f"dead fills {dead} | boundary saves {saves} | "
          f"net {net:+.4f} | exp {net/n:+.5f}/trade")
    return net

a = load('hfna_paper.jsonl', fix=FIX)
b = load('hfna_paper_w7.jsonl')
c = load('hfna_paper_repo.jsonl')
d = load('hfna_paper_flow.jsonl')
d = [r for r in d if r['t'] - r.get('entry_t', r['t']) < 3600]  # drop replay-tainted trade #1 (25.7h hold)
e = load('hfna_paper_reflow.jsonl')
na = summarize('3-bin (post-fix)', a)
nb = summarize('w7 boundary    ', b)
nc = summarize('repo follow    ', c)
nd = summarize('flow-gated 3bin', d)
ne = summarize('reflow combined', e)
arms = [(len(a), na), (len(b), nb), (len(c), nc), (len(d), nd), (len(e), ne)]
if all(n > 0 for n, _ in arms):
    best = max(range(5), key=lambda i: arms[i][1]/arms[i][0])
    print(f"\nbest arm: {['3-bin','w7','repo','flow','reflow'][best]} (need ~15 trades/arm for a real read)")
