#!/usr/bin/env python3
"""Gate-combination expectancy test over full dataset (live + post-fix paper).

Live rows: join live_enter -> next real_pnl for same pool (net of real friction).
Paper rows: only t >= fee-cap fix (2026-09-12 20:03:03 +0100) to drop artifacts.
Gates tested: elevation floor, pool whitelist (depth>=1500 pinned set),
UTC hour buckets, regime flow at entry (sparse, informational only).
"""
import json, datetime, itertools
from collections import defaultdict

FIX_EPOCH = datetime.datetime(2026, 9, 12, 20, 3, 3,
                              tzinfo=datetime.timezone(datetime.timedelta(hours=1))).timestamp()

PINNED = ["GbrDAq3R", "9Ndi", "BN7C", "GuPb", "42Jn"]  # depth>=1500 pinned prefixes
DEPTH_OK = set(PINNED)  # pools that passed >=1500 SOL depth validation

def load_live():
    rows = [json.loads(l) for l in open('hfna_live.jsonl') if l.strip()]
    rows.sort(key=lambda r: r['t'])
    # real_pnl rows followed by real_pnl_corrected (same pool, <15min) are
    # mid-settlement measurement artifacts (exit tx expired, proceeds swept back)
    corrected = [(r['t'], r['pool']) for r in rows if r.get('kind') == 'real_pnl_corrected']
    def is_artifact(r):
        return any(r['pool'] == p and 0 < ct - r['t'] < 900 for ct, p in corrected)
    trades = []
    dropped = 0
    for i, r in enumerate(rows):
        if r.get('kind') != 'live_enter':
            continue
        for r2 in rows[i+1:]:
            if r2.get('kind') == 'real_pnl' and r2['pool'] == r['pool']:
                if is_artifact(r2):
                    dropped += 1
                else:
                    trades.append({'src': 'live', 't': r['t'], 'pool': r['pool'],
                                   'elev': r.get('elev'), 'net': r2['real_pnl']})
                break
    return trades, dropped

def load_paper():
    trades = []
    for line in open('hfna_paper.jsonl'):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if 'net' not in r or r['t'] < FIX_EPOCH:
            continue
        trades.append({'src': 'paper', 't': r['t'], 'pool': r['pool'],
                       'elev': r.get('elev'), 'net': r['net'],
                       'reason': r.get('reason', '')})
    return trades

def load_regime():
    rows = []
    for line in open('regime_log.jsonl'):
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows

def regime_flow_at(reg, t):
    best = None
    for r in reg:
        if abs(r['t'] - t) < 600:
            best = r['flow_hr'] if best is None else max(best, r['flow_hr'])
    return best

def pool_ok(pool):
    return any(pool.startswith(p) for p in DEPTH_OK)

def evaluate(trades, name, fn):
    sel = [t for t in trades if fn(t)]
    if not sel:
        return (name, 0, 0, 0.0, 0.0)
    wins = sum(1 for t in sel if t['net'] > 0)
    net = sum(t['net'] for t in sel)
    return (name, len(sel), wins, net, net / len(sel))

def main():
    live, dropped = load_live()
    paper = load_paper()
    reg = load_regime()
    allt = live + paper
    print(f"dataset: {len(live)} live (real friction; {dropped} reconciled artifact(s) excluded), "
          f"{len(paper)} paper post-fix, regime rows {len(reg)}\n")

    results = []
    # 1. baseline
    results.append(evaluate(allt, "ALL (no gate)", lambda t: True))
    results.append(evaluate(live, "  live only", lambda t: True))
    results.append(evaluate(paper, "  paper only", lambda t: True))

    # 2. elevation floors
    for e in [1.5, 10, 100, 1000, 10000, 50000]:
        results.append(evaluate(allt, f"elev>={e}", lambda t, e=e: (t['elev'] or 0) >= e))

    # 3. pool whitelist
    results.append(evaluate(allt, "depth>=1500 pools", lambda t: pool_ok(t['pool'])))
    results.append(evaluate(allt, "NOT depth>=1500", lambda t: not pool_ok(t['pool'])))

    # 4. elev x pool combos
    for e in [1.5, 100, 10000]:
        results.append(evaluate(allt, f"depth1500 & elev>={e}",
                                lambda t, e=e: pool_ok(t['pool']) and (t['elev'] or 0) >= e))

    # 5. UTC hour buckets (combined dataset)
    hours = defaultdict(list)
    for t in allt:
        h = datetime.datetime.utcfromtimestamp(t['t']).hour
        hours[h].append(t['net'])
    print("UTC hour  n   net      avg")
    for h in sorted(hours):
        v = hours[h]
        print(f"  {h:02d}:00  {len(v):3d}  {sum(v):+.4f}  {sum(v)/len(v):+.5f}")
    print()

    # 6. regime flow at entry (sparse sample, informational)
    if reg:
        rf = [(regime_flow_at(reg, t['t']), t['net']) for t in allt]
        rf = [x for x in rf if x[0] is not None]
        if rf:
            lo = [n for f, n in rf if f < 0.5]
            hi = [n for f, n in rf if f >= 0.5]
            print(f"regime<0.5/hr: n={len(lo)} net={sum(lo):+.4f} | "
                  f">=0.5/hr: n={len(hi)} net={sum(hi):+.4f}\n")

    # ranked table
    print(f"{'config':28s} {'n':>4s} {'wins':>5s} {'net':>9s} {'exp/trade':>10s}")
    for name, n, w, net, exp in sorted(results, key=lambda x: -x[4]):
        print(f"{name:28s} {n:4d} {w:5d} {net:+9.4f} {exp:+10.5f}")

    positives = [r for r in results if r[1] >= 5 and r[4] > 0]
    print("\nVERDICT:", f"{len(positives)} config(s) with n>=5 and positive expectancy"
          if positives else "NO config with n>=5 shows positive expectancy after friction")

if __name__ == '__main__':
    main()
