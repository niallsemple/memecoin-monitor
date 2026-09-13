#!/usr/bin/env python3
"""size_model.py — at what SIZE does each arm's expectancy flip positive?

Paper trades are 0.1 SOL with FIXED_COST 0.001/trade. In deep pools
(1000s SOL) our share is tiny, so fee capture scales ~linearly with SIZE
until the per-interval cap (0.05*SIZE), which itself scales linearly.
Markouts scale linearly too. Fixed cost does NOT scale.

Model: net(S) = fees*(S/0.1) - markout*(S/0.1) - FIXED_COST
Caveats: ignores share-curve sublinearity near cap, IL on held Y during
dumps, and assumes fixed cost really stays 0.001 at larger size (priority
fees may rise slightly). Dead fills (fees=0) stay negative at ANY size —
this model prices the bleed vs the wins, not placement.
"""
import json, os

MON = os.path.dirname(os.path.abspath(__file__))
FIXED = 0.001
BASE = 0.1
SIZES = [0.1, 0.2, 0.3, 0.5, 1.0]

def load(fn):
    p = os.path.join(MON, fn)
    if not os.path.exists(p):
        return []
    out = []
    for line in open(p):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if 'net' in r:
            out.append(r)
    return out

for name, fn in [("3-bin", "hfna_paper.jsonl"), ("w7", "hfna_paper_w7.jsonl"),
                 ("repo", "hfna_paper_repo.jsonl"), ("flow", "hfna_paper_flow.jsonl")]:
    rows = load(fn)
    if not rows:
        continue
    # use same post-fix window as scorecard for 3-bin
    if name == "3-bin":
        rows = [r for r in rows if r['t'] > 1789239783]
    n = len(rows)
    mf = sum(r['fees'] for r in rows) / n
    mm = sum(r.get('markout', 0) for r in rows) / n
    dead = sum(1 for r in rows if r['fees'] < 0.0001) / n
    print(f"\n{name} (n={n}, dead {dead:.0%}): mean fees {mf:.5f}, mean markout {mm:.5f} @0.1")
    flip = None
    for S in SIZES:
        k = S / BASE
        exp = mf * k - mm * k - FIXED
        marker = ""
        if exp > 0 and flip is None:
            flip = S
            marker = "  <-- positive"
        print(f"  SIZE {S:4.1f}: exp {exp:+.5f}/trade{marker}")
    if flip is None:
        print("  never positive in range (dead-fill share too high or markouts dominate)")

print("\nNote: positive-at-size requires dead-fill rate to fall with placement")
print("fix (repo follow). At 0% dead fills repo mean fees alone would be:")
rows = [r for r in load("hfna_paper_repo.jsonl") if r['fees'] >= 0.0001]
if rows:
    mf = sum(r['fees'] for r in rows) / len(rows)
    print(f"  repo paid-only mean fees {mf:.5f} (n={len(rows)}) -> breakeven SIZE ~{0.1*FIXED/mf:.2f} SOL")
