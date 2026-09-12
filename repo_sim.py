#!/usr/bin/env python3
"""Repositioning sim: does follow-the-price re-centering pay for itself?

For each post-fix trade window, simulate a repositioning 3-bin policy:
  - anchor position [a-2, a] where a = active bin at entry (or last reposition)
  - if active bin drifts > DRIFT bins from anchor, re-center at current ab,
    pay REPO_COST (0.0005 SOL tx), new anchor = ab
  - capture fees only when ab inside current range (same share model as
    hfna_paper: SIZE/(liq_active+SIZE), fee cap 5% SIZE per interval)
Compare vs the recorded fixed-position outcome of the same window.

Caveat: 64s snapshot cadence (15s during fast-tail windows) means in-range
visits between snapshots are missed both ways; relative comparison stands.
"""
import json, datetime
from collections import defaultdict

FIX = datetime.datetime(2026, 9, 12, 20, 3, 3,
                        tzinfo=datetime.timezone(datetime.timedelta(hours=1))).timestamp()
SIZE = 0.1
REPO_COST = 0.0005
DRIFT = 2
FEE_CAP = 0.05 * SIZE

snaps = defaultdict(list)
for line in open('bin_snapshots.jsonl'):
    try:
        r = json.loads(line)
    except Exception:
        continue
    if r.get('prot_fee_y') is not None and r.get('liq_active'):
        snaps[r['pool']].append(r)
for p in snaps:
    snaps[p].sort(key=lambda r: r['t'])

trades = []
for fn, fix in [('hfna_paper.jsonl', FIX), ('hfna_paper_w7.jsonl', None)]:
    for line in open(fn):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if 'net' not in r:
            continue
        if fix and r['t'] < fix:
            continue
        if r['t'] - r.get('entry_t', r['t']) > 7200:  # skip state artifact
            continue
        trades.append(r)

def sim_repos(tr, lp_mult=9.0):
    path = [r for r in snaps.get(tr['pool'], [])
            if tr['entry_t'] - 10 <= r['t'] <= tr['t'] + 30]
    if len(path) < 3:
        return None
    anchor = path[0]['active_bin']
    fees = 0.0
    repos = 0
    prev = path[0]
    for r in path[1:]:
        ab = r['active_bin']
        if abs(ab - anchor) > DRIFT:
            anchor = ab
            repos += 1
        dpf = r['prot_fee_y'] - prev['prot_fee_y']
        if dpf > 0 and anchor - 2 <= ab <= anchor:
            share = SIZE / (r['liq_active'] / 1e9 + SIZE)
            fees += min(dpf / 1e9 * lp_mult * share, FEE_CAP)
        prev = r
    return fees, repos

tot_f, tot_r, tot_rec, n = 0.0, 0, 0.0, 0
better = 0
for tr in trades:
    s = sim_repos(tr)
    if s is None:
        continue
    fees, repos = s
    repo_net = fees - repos * REPO_COST - 0.001  # same fixed cost as engines
    tot_f += fees
    tot_r += repos
    tot_rec += tr['net']
    n += 1
    if repo_net > tr['net']:
        better += 1
    print(f"{tr['pool'][:8]} recorded {tr['net']:+.5f} | repos {repos} "
          f"repo-fees {fees:.5f} repo-net {repo_net:+.5f}")

print(f"\nn={n}: recorded total {tot_rec:+.4f} | repositioning total "
      f"{tot_f - tot_r*REPO_COST - n*0.001:+.4f} ({tot_r} repositions) | "
      f"beats recorded on {better}/{n} windows")
