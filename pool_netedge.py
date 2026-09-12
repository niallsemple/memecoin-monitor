#!/usr/bin/env python3
"""Pool-agnostic fee model + real-time state classification + NetEdge.

Usage: python3 pool_netedge.py <pool_addr> <tag> [dep_sol] [width_bins]

Reads: <tag>_swaps.jsonl (from pool_recon.py), bin_snapshots.jsonl
Writes: <tag>_swap_fees.jsonl, prints interval reconciliation + NetEdge tables.

Fee model: rate = base + ceil(varFeeCtl*(vol*binStep)^2/1e11)/1e9, capped 10%.
vol(t) from nearest snapshot (90s). All fees treated as quote-denominated.
Checkpoints: protocol claims from <tag>_prot_claims.jsonl + protY drops in
snapshots; model-vs-exact ratio per interval validates the fee series.

Real-time states (no forward data at classification time):
  RT-POST-HFNA: 0-900s after a shock ends, trailing-300s |move| < 2%,
                trailing fee elevation >= 2x base
  RT-POST-TOXIC: 0-900s after shock, otherwise
  RT-OTHER: everything else
Trade model: Y-only entry, range [active-W, active], dep SOL, hold H, exit.
Share per swap = (DEP/W) / (DEP/W + liq_active). Costs 0.004 SOL.
"""
import json, math, bisect, sys

LOGSTEP = math.log(1.0001)
FEE_BASE_DIV = 1e9


def main():
    POOL, TAG = sys.argv[1], sys.argv[2]
    DEP = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
    W = int(sys.argv[4]) if len(sys.argv) > 4 else 30
    COSTS = 0.004

    # snapshots for this pool
    sn = []
    for line in open('bin_snapshots.jsonl'):
        if POOL not in line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get('pool') == POOL and 'vol_accum' in d:
            sn.append(d)
    sn.sort(key=lambda d: d['t'])
    if not sn:
        print('no snapshots for pool'); return
    BS = sn[0]['bin_step']
    BF = sn[0].get('base_factor', 20000)
    VFC = sn[0].get('var_fee_ctl', 0)
    base_rate = BF * BS * 10 / FEE_BASE_DIV
    print(f'pool params: binStep={BS} baseFactor={BF} varFeeCtl={VFC} base={base_rate*100:.2f}%')

    def var_rate(vol):
        if VFC <= 0:
            return 0.0
        v = VFC * (vol * BS) ** 2
        return (v + 99999999999) // 100000000000 / FEE_BASE_DIV

    # swaps
    sw = []
    for line in open(f'{TAG}_swaps.jsonl'):
        d = json.loads(line)
        if d.get('mixed') or d['dx'] == 0 or d['dy'] == 0:
            continue
        sw.append(d)
    sw.sort(key=lambda d: (d['blockTime'], d['slot']))
    print(f'swaps={len(sw)} snaps={len(sn)}')

    sn_t = [s['t'] for s in sn]

    def snap_near(t, field):
        i = bisect.bisect_left(sn_t, t)
        for j in (i - 1, i):
            if 0 <= j < len(sn) and abs(sn[j]['t'] - t) <= 90:
                return sn[j][field]
        return None

    # fee series
    out = open(f'{TAG}_swap_fees.jsonl', 'w')
    recs = []
    for d in sw:
        v = snap_near(d['blockTime'], 'vol_accum') or 0
        r = min(base_rate + var_rate(v), 0.10)
        vol_sol = abs(d['dy']) / 1e9
        fee_sol = vol_sol * r / (1 - r)
        p = abs(d['dy']) / abs(d['dx'])
        rec = dict(t=d['blockTime'], dir=d['dir'], vol_sol=vol_sol,
                   fee_sol=fee_sol, rate=r, vol=int(v), p=p)
        recs.append(rec)
        out.write(json.dumps(rec) + '\n')
    out.close()

    # checkpoints: protocol claims from txs
    claims = []
    try:
        for line in open(f'{TAG}_prot_claims.jsonl'):
            d = json.loads(line)
            claims.append((d['blockTime'], -d['dy'] / 1e9))
    except FileNotFoundError:
        pass
    claims.sort()
    if claims:
        print('\ninterval reconciliation (model protocol vs exact claim):')
        for i in range(1, len(claims)):
            t0, t1 = claims[i - 1][0], claims[i][0]
            seg = [r for r in recs if t0 <= r['t'] < t1]
            mp = sum(r['fee_sol'] for r in seg) * 0.10
            ep = claims[i][1]
            print(f'  [{t0}->{t1}] vol={sum(r["vol_sol"] for r in seg):8.1f} model={mp:7.4f} exact={ep:7.4f} ratio={mp/ep if ep else 0:5.2f}')

    # price series for classification/markout
    ts = [r['t'] for r in recs]
    ps = [math.log(r['p']) for r in recs]

    def price_at(t):
        i = bisect.bisect_right(ts, t) - 1
        return ps[i] if i >= 0 else None

    def bin_snap(t):
        i = bisect.bisect_right(sn_t, t) - 1
        return sn[i] if i >= 0 else None

    def logp_to_bin(lp, t):
        s = bin_snap(t)
        if not s:
            return None
        lp_ref = price_at(s['t'])
        if lp_ref is None:
            return None
        return s['active_bin'] + round((lp - lp_ref) / LOGSTEP)

    # shock detection: >3% in 60s
    shock = [False] * len(recs)
    for i in range(len(recs)):
        j = bisect.bisect_left(ts, ts[i] - 60)
        if abs(ps[i] - ps[j]) > 0.03:
            shock[i] = True
    shock_ends = []
    for i in range(len(recs)):
        if shock[i] and (i == len(recs) - 1 or not shock[i + 1]):
            shock_ends.append(ts[i])

    # grid + realtime classification + NetEdge
    t0, t1 = ts[0], ts[-1]
    grid = list(range(int(t0), int(t1), 60))
    HS = [300, 900, 1800, 3600]
    DEP_BIN = DEP / W
    res = {'RT-POST-HFNA': [], 'RT-POST-TOXIC': [], 'RT-OTHER': []}
    for g in grid:
        p = price_at(g)
        if p is None:
            continue
        a_bin = logp_to_bin(p, g)
        if a_bin is None:
            continue
        p3 = price_at(g - 300)
        tr = (p - p3) if p3 else 0.0
        i0 = bisect.bisect_left(ts, g - 300); i1 = bisect.bisect_left(ts, g)
        elev = sum(r['rate'] for r in recs[i0:i1]) / max(1, i1 - i0) / base_rate
        post_shock = any(se <= g < se + 900 for se in shock_ends)
        if post_shock and abs(tr) < 0.02 and elev >= 2:
            st = 'RT-POST-HFNA'
        elif post_shock:
            st = 'RT-POST-TOXIC'
        else:
            st = 'RT-OTHER'
        row = {}
        for H in HS:
            j0 = bisect.bisect_left(ts, g); j1 = bisect.bisect_left(ts, g + H)
            fsum = 0.0
            for r in recs[j0:j1]:
                b = logp_to_bin(math.log(r['p']), r['t'])
                if b is None or not (a_bin - W <= b <= a_bin):
                    continue
                s = bin_snap(r['t'])
                liq = s['liq_active'] if s else 0
                share = DEP_BIN * 1e9 / (DEP_BIN * 1e9 + liq) if liq > 0 else 0
                fsum += r['fee_sol'] * share
            p_exit = price_at(g + H)
            conv = 0.0; inv = 0.0
            if p_exit is not None:
                d_bins = (p_exit - p) / LOGSTEP
                conv = 1.0 if d_bins <= -W else (-d_bins / W if d_bins < 0 else 0.0)
                if conv > 0:
                    p_conv = p + LOGSTEP * (-conv * W / 2)
                    inv = DEP * conv * (math.exp(p_exit - p_conv) - 1)
            row[H] = fsum + inv - COSTS
        res[st].append(row)

    print(f'\nshock events={len(shock_ends)} grid={len(grid)} DEP={DEP} W={W}')
    print('state            n' + ''.join(f'  H={H}s med/mean/win' for H in HS))
    for st, rows in res.items():
        if not rows:
            continue
        cells = []
        for H in HS:
            v = sorted(r[H] for r in rows)
            med = v[len(v) // 2] / DEP * 100
            m = sum(v) / len(v) / DEP * 100
            wr = sum(1 for x in v if x > 0) / len(v) * 100
            cells.append(f'{med:+6.2f}/{m:+6.2f}/{wr:3.0f}%')
        print(f'{st:15s} {len(rows):4d} ' + ' '.join(cells))


if __name__ == '__main__':
    main()
