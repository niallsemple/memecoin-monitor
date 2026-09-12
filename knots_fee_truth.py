#!/usr/bin/env python3
"""KNOTS fee-truth reconciliation.

Anchors (exact, on-chain):
  protocol-fee claims reset protFeeY to ~0, so protocol fees accrued between
  consecutive claims are exactly the claimed amounts:
    I0 [149602->156802] = 8.588698  (deploy 156222 falls inside)
    I1 [156802->160401] = 2.430331
    I2 [160401->167602] = 8.217048
    I3 [167602->171201] = 2.624499
    I4 [171201->182001] = 4.049666
    I5 [182001->snap end 199027] = 0.785070 (protY residual at last snapshot)

Model: fee_rate = base + variable (FEE_PRECISION=1e9)
  base     = baseFactor*binStep*10*10^bpf          (bpf assumed 0 -> 2.0%)
  variable = ceil(varFeeCtl*(volAccum*binStep)^2 / 1e11) / 1e9
  volAccum(t): nearest snapshot when available; else volRef-estimate from
               consecutive-swap bin crossings.
All fees behave as quote(SOL)-denominated: protX==0 and every claim is Y-only.

Outputs: interval table (model vs exact), deploy-split of I0, pool-wide LP
fees post-deploy, our 0.1306 SOL share, and per-swap fee series for the
state-classification step (knots_swap_fees.jsonl).
"""
import json, math

DEPLOY = 1789156222
CLAIMS = [  # (time, protocol SOL claimed) — each resets protY to ~0
    (1789149602, 2.171479),
    (1789156802, 8.588698),
    (1789160401, 2.430331),
    (1789167602, 8.217048),
    (1789171201, 2.624499),
    (1789182001, 4.049666),
]
SNAP_END = 1789199027
PROT_Y_END = 0.785070
BASE_FACTOR, BIN_STEP, VAR_FEE_CTL = 20000, 100, 7500
MAX_FEE = 0.10                      # DLMM MAX_FEE_RATE = 10%
OUR_FEES = 0.1306                   # guardian claims + pending at exit (SOL)

base_rate = BASE_FACTOR * BIN_STEP * 10 / 1e9   # 0.02


def var_rate(vol):
    v = VAR_FEE_CTL * (vol * BIN_STEP) ** 2
    return (v + 99999999999) // 100000000000 / 1e9


def load_swaps():
    sw = []
    for fn in ('knots_swaps_pre.jsonl', 'knots_swaps.jsonl'):
        try:
            for line in open(fn):
                d = json.loads(line)
                if d.get('mixed') or d['dx'] == 0 or d['dy'] == 0:
                    continue
                sw.append(d)
        except FileNotFoundError:
            pass
    sw.sort(key=lambda d: (d['blockTime'], d['slot']))
    return sw


def load_snaps():
    sn = []
    for line in open('bin_snapshots.jsonl'):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get('pool') == 'nBXytBBfKLhj6teXarAv8rk6WNgUFBMyybUFRkuK7ad' and 'vol_accum' in d:
            sn.append((d['t'], d['vol_accum']))
    sn.sort()
    return sn


def main():
    sw = load_swaps()
    sn = load_snaps()
    print(f'swaps={len(sw)} vol-snaps={len(sn)}')

    # per-swap execution price (SOL per KNOTS; decimals cancel in ratios)
    # price p = |dy|/|dx|  (both raw)
    snaps_t = [s[0] for s in sn]

    def snap_vol(t):
        # nearest snapshot within 90s, else None
        import bisect
        i = bisect.bisect_left(snaps_t, t)
        best = None
        for j in (i - 1, i):
            if 0 <= j < len(sn) and abs(sn[j][0] - t) <= 90:
                best = sn[j][1]
        return best

    out = open('knots_swap_fees.jsonl', 'w')
    prev_price = None
    vol_est = 0
    recs = []
    for d in sw:
        p = abs(d['dy']) / abs(d['dx'])
        crossed = 0
        if prev_price and prev_price > 0:
            crossed = abs(math.log(p / prev_price)) / math.log(1.0001)
        prev_price = p
        v = snap_vol(d['blockTime'])
        if v is None:
            # estimate: volRef persists (no decay model) + bins crossed
            vol_est = vol_est + crossed
            v = vol_est
        else:
            vol_est = v
        r = min(base_rate + var_rate(v), MAX_FEE)
        vol_sol = abs(d['dy']) / 1e9
        fee_sol = vol_sol * r / (1 - r)         # quote-denominated fee
        rec = dict(t=d['blockTime'], dir=d['dir'], vol_sol=round(vol_sol, 6),
                   fee_sol=round(fee_sol, 8), rate=round(r, 6), vol=int(v),
                   crossed=round(crossed, 1))
        recs.append(rec)
        out.write(json.dumps(rec) + '\n')
    out.close()

    # interval reconciliation — accrual (claim[i-1] -> claim[i]] = claimed[i]
    ivals = []
    for i in range(1, len(CLAIMS)):
        ivals.append((CLAIMS[i-1][0], CLAIMS[i][0], CLAIMS[i][1]))
    ivals.append((CLAIMS[-1][0], SNAP_END, PROT_Y_END))
    print('\ninterval           seconds  vol_SOL   model_prot  exact_prot  ratio')
    tot_model_post = tot_exact_post = 0.0
    i0_pre_model = i0_post_model = 0.0
    for i, (t0, t1, ep) in enumerate(ivals):
        seg = [r for r in recs if t0 <= r['t'] < t1]
        vol = sum(r['vol_sol'] for r in seg)
        mf = sum(r['fee_sol'] for r in seg)
        mp = mf * 0.10                          # protocol share 10%
        print(f'I{i} [{t0}->{t1}] {t1-t0:6d} {vol:9.1f} {mp:9.4f} {ep:9.4f}  {mp/ep if ep else 0:5.2f}')
        if t0 < DEPLOY < t1:
            i0_pre_model = sum(r['fee_sol'] for r in seg if r['t'] < DEPLOY) * 0.10
            i0_post_model = sum(r['fee_sol'] for r in seg if r['t'] >= DEPLOY) * 0.10
            i0_exact = ep
            i0_idx = i
        elif t0 >= DEPLOY:
            tot_model_post += mp
            tot_exact_post += ep

    # split the deploy-spanning interval using model proportions
    frac_post = i0_post_model / (i0_pre_model + i0_post_model) if (i0_pre_model + i0_post_model) else 0
    i0_post_exact = i0_exact * frac_post
    print(f'\nI{i0_idx} split at deploy: model says {frac_post*100:.1f}% of its fees accrued post-deploy')
    print(f'  -> post-deploy protocol fees from it = {i0_post_exact:.4f} SOL')
    tot_exact_post += i0_post_exact
    tot_model_post += i0_post_model
    print(f'\npost-deploy protocol fees: model {tot_model_post:.4f} vs exact {tot_exact_post:.4f} SOL')
    lp_fees_post = tot_exact_post * 9
    print(f'pool-wide LP fees generated post-deploy (exact x9): {lp_fees_post:.4f} SOL')
    print(f'our actual fees: {OUR_FEES} SOL -> share = {OUR_FEES/lp_fees_post*100:.4f}% of pool LP fees')
    print(f'our position was ~0.77 SOL of a ~3000 SOL pool (~0.026% TVL) -> capture multiplier x{OUR_FEES/lp_fees_post/0.00026:.2f}')


if __name__ == '__main__':
    main()
