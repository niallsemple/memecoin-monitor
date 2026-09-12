#!/usr/bin/env python3
"""KNOTS state classification + NetEdge curves.

Trade modelled: Y-only (SOL) DLMM entry at time t, range [active-W, active],
W=30 bins (~3%), held H seconds, then force-exited. Mirrors the wide-arm /
HFNA live mechanics.

  fees(t,H)   = sum over swaps in window of fee_sol * our_share(swap)
  our_share   = DEP / (DEP + bin_liq_active(t))   when inferred active bin in
                our range, else 0. bin_liq from nearest 60s snapshot.
  conversion  = fraction of our SOL turned into KNOTS by exit:
                0 if exit price >= range top; 1 if <= range bottom;
                linear in between (in log-price bins).
  inv_pnl     = DEP * conversion * (p_exit / p_avg_conversion - 1)
                (approximation: avg conversion price = geometric mean of the
                bins crossed while converting; here ~ price at range edge the
                price fell through)
  costs       = 0.004 SOL (entry+exit+claims, priority fees)

NetEdge(t,H) = fees + inv_pnl - costs, in SOL and in % of DEP.

States per minute: PRE-SHOCK (300s before a shock), SHOCK (|dlogp|/60s > 3%),
POST-TOXIC (0-900s after shock, forward 300s return < -2%),
POST-HFNA (0-900s after shock, forward 300s return >= -2% and fee elev >= 2x),
NORMAL otherwise.

Outputs knots_netedge.json + prints summary tables.
"""
import json, math, bisect
from collections import defaultdict

DEP = 0.77          # SOL, matches the live wide-arm deployment
W = 30              # range width in bins below active
COSTS = 0.004
POOL = 'nBXytBBfKLhj6teXarAv8rk6WNgUFBMyybUFRkuK7ad'
LOGSTEP = math.log(1.0001)


def load_prices():
    """Per-swap price series from raw swap files."""
    pts = []
    for fn in ('knots_swaps_pre.jsonl', 'knots_swaps.jsonl'):
        try:
            for line in open(fn):
                d = json.loads(line)
                if d.get('mixed') or d['dx'] == 0 or d['dy'] == 0:
                    continue
                pts.append((d['blockTime'], abs(d['dy']) / abs(d['dx'])))
        except FileNotFoundError:
            pass
    pts.sort()
    return pts


def load_fees():
    recs = [json.loads(l) for l in open('knots_swap_fees.jsonl')]
    recs.sort(key=lambda r: r['t'])
    return recs


def load_binliq():
    """(t, active_bin, liq_active_rawY) from snapshots."""
    sn = []
    for line in open('bin_snapshots.jsonl'):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get('pool') == POOL and 'liq_active' in d:
            sn.append((d['t'], d['active_bin'], d['liq_active']))
    sn.sort()
    return sn


def main():
    pts = load_prices()
    fees = load_fees()
    snaps = load_binliq()
    print(f'price pts={len(pts)} fee recs={len(fees)} snaps={len(snaps)}')

    ts = [p[0] for p in pts]
    ps = [math.log(p[1]) for p in pts]
    sn_t = [s[0] for s in snaps]

    def price_at(t):
        i = bisect.bisect_right(ts, t) - 1
        return ps[i] if i >= 0 else None

    def bin_at(t):
        i = bisect.bisect_right(sn_t, t) - 1
        return snaps[i][1] if i >= 0 else None

    def liq_at(t):
        i = bisect.bisect_right(sn_t, t) - 1
        return snaps[i][2] if i >= 0 else None

    def logp_to_bin(lp, t):
        """infer active bin from log price using snapshot calibration"""
        ab = bin_at(t)
        i = bisect.bisect_right(sn_t, t) - 1
        if i < 0:
            return None
        # calibrate: at snapshot i, active_bin corresponds to price_at(snap t)
        lp_ref = price_at(snaps[i][0])
        if lp_ref is None:
            return None
        return ab + round((lp - lp_ref) / LOGSTEP)

    # shock detection on 60s displacement
    shock = [False] * len(pts)
    for i in range(len(pts)):
        j = bisect.bisect_left(ts, ts[i] - 60)
        if abs(ps[i] - ps[j]) / 1 > 0.03:   # >3% in 60s
            shock[i] = True

    # bursts: fee elevation vs 2% base
    for r in fees:
        r['elev'] = r['rate'] / 0.02

    # minute grid over the whole covered span
    t0, t1 = pts[0][0], pts[-1][0]
    grid = list(range(int(t0), int(t1), 60))

    # state classification
    states = {}
    shock_times = [ts[i] for i in range(len(pts)) if shock[i] and (i == 0 or not shock[i - 1])]
    shock_ends = []
    for st in shock_times:
        i0 = bisect.bisect_left(ts, st)
        i1 = i0
        while i1 < len(pts) and shock[i1]:
            i1 += 1
        shock_ends.append(ts[min(i1, len(pts) - 1)])
    def fwd_ret(t, h=300):
        p0 = price_at(t); p1 = price_at(t + h)
        if p0 is None or p1 is None:
            return 0.0
        return math.exp(p1 - p0) - 1

    for g in grid:
        st = 'NORMAL'
        for s0, s1 in zip(shock_times, shock_ends):
            if s0 - 300 <= g < s0:
                st = 'PRE-SHOCK'; break
            if s0 <= g < s1:
                st = 'SHOCK'; break
            if s1 <= g < s1 + 900:
                fr = fwd_ret(g)
                elev_now = max((r['elev'] for r in fees if abs(r['t'] - g) < 30), default=1.0)
                st = 'POST-TOXIC' if fr < -0.02 else ('POST-HFNA' if elev_now >= 2 else 'POST-TOXIC')
                break
        states[g] = st

    # NetEdge per grid minute for horizons
    HS = [300, 900, 1800, 3600]
    fee_t = [r['t'] for r in fees]
    results = []
    for g in grid:
        a_bin = logp_to_bin(price_at(g), g) if price_at(g) is not None else None
        if a_bin is None:
            continue
        row = {'t': g, 'state': states[g]}
        p_entry = price_at(g)
        for H in HS:
            i0 = bisect.bisect_left(fee_t, g)
            i1 = bisect.bisect_left(fee_t, g + H)
            fsum = 0.0
            for r in fees[i0:i1]:
                b = logp_to_bin(math.log(abs(r['vol_sol'] * 1e9) + 1e-18) * 0 + price_at(r['t']), r['t'])
                if b is None:
                    continue
                if a_bin - W <= b <= a_bin:
                    liq = liq_at(r['t']) or 0
                    share = DEP * 1e9 / (DEP * 1e9 + liq) if liq > 0 else 0
                    fsum += r['fee_sol'] * share
            p_exit = price_at(g + H)
            conv = 0.0; inv_pnl = 0.0
            if p_exit is not None:
                d_bins = (p_exit - p_entry) / LOGSTEP   # negative = fell
                if d_bins <= -W:
                    conv = 1.0
                elif d_bins < 0:
                    conv = -d_bins / W
                if conv > 0:
                    p_conv = p_entry + math.log(1.0001) * (-conv * W / 2)  # avg conversion ~ halfway
                    inv_pnl = DEP * conv * (math.exp(p_exit - p_conv) - 1)
            row[f'net{H}'] = fsum + inv_pnl - COSTS
            row[f'fees{H}'] = fsum
        results.append(row)

    json.dump({'dep': DEP, 'w': W, 'costs': COSTS, 'results': results},
              open('knots_netedge.json', 'w'))

    # summary: mean net edge by state x horizon
    print('\nmean NET edge (% of 0.77 SOL) by state x horizon:')
    print('state        n' + ''.join(f'   H={H}s' for H in HS))
    for st in ('PRE-SHOCK', 'SHOCK', 'POST-TOXIC', 'POST-HFNA', 'NORMAL'):
        rows = [r for r in results if r['state'] == st]
        if not rows:
            continue
        cells = []
        for H in HS:
            m = sum(r[f'net{H}'] for r in rows) / len(rows)
            cells.append(f'{m / DEP * 100:+8.2f}%')
        print(f'{st:11s} {len(rows):5d} ' + ' '.join(cells))

    # positive-rate (fraction of minutes with net>0)
    print('\nfraction of entries with net>0:')
    for st in ('PRE-SHOCK', 'SHOCK', 'POST-TOXIC', 'POST-HFNA', 'NORMAL'):
        rows = [r for r in results if r['state'] == st]
        if not rows:
            continue
        cells = []
        for H in HS:
            pos = sum(1 for r in rows if r[f'net{H}'] > 0)
            cells.append(f'{pos / len(rows) * 100:7.0f}%')
        print(f'{st:11s} {len(rows):5d} ' + ' '.join(cells))


if __name__ == '__main__':
    main()
