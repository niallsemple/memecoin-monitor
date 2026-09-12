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
na = summarize('3-bin (post-fix)', a)
nb = summarize('w7 boundary    ', b)
if a and b:
    print(f"\nw7 minus 3-bin expectancy: {(nb/len(b)) - (na/len(a)):+.5f}/trade "
          f"(n={len(a)} vs {len(b)} — need ~15+ each for a real read)")
