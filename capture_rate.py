#!/usr/bin/env python3
"""Real capture-rate measurement: the ONLY trustworthy fee accounting.

Pairs lp_guardian's feeY_hist (real pending-fee observations on our live
position, epoch-stamped) with bin_snapshots prot_fee_y (pool-wide protocol
fee accumulator). Computes:

  pool LP fees  = d(prot_fee_y) * lpMult            (on-chain ground truth)
  real capture  = d(feeY_real)                       (our position, on-chain)
  capture_ratio = real_capture / pool_LP_fees        (our share of LP fees)

Compares against the paper model's implied share (SIZE/(liq_active+SIZE))
to quantify model error over many windows. Handles claim resets (feeY drop).

Usage: python3 capture_rate.py [min_dt_seconds]
"""
import json, os, statistics, sys

MON = os.path.dirname(os.path.abspath(__file__))
STATE_F = os.path.join(MON, "lp_positions.json")       # positions + feeY_hist
SNAP = os.path.join(MON, "bin_snapshots.jsonl")
WATCH_F = os.path.join(MON, "hfna_watchlist.json")

def lp_mult(pool):
    try:
        pp = json.load(open(WATCH_F)).get("pool_params", {})
        return float(pp.get(pool, {}).get("lpMult", 9.0))
    except Exception:
        return 9.0

def main():
    min_dt = float(sys.argv[1]) if len(sys.argv) > 1 else 300.0
    st = json.load(open(STATE_F))
    # snapshots per pool
    snaps = {}
    for ln in open(SNAP):
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get("prot_fee_y") is not None:
            snaps.setdefault(d["pool"], []).append(d)
    for p in snaps:
        snaps[p].sort(key=lambda r: r["t"])

    for pos in st.get("positions", []):
        fh = pos.get("feeY_hist") or []
        if len(fh) < 2:
            continue
        pool = pos["pool"]
        ss = snaps.get(pool, [])
        if not ss:
            continue
        mult = lp_mult(pool)
        pairs = []
        for i in range(1, len(fh)):
            a, b = fh[i - 1], fh[i]
            if b["feeY"] < a["feeY"]:
                continue  # claim reset
            d_real = (b["feeY"] - a["feeY"]) / 1e9
            # pool prot_fee_y delta over same window (nearest snaps)
            s0 = min(ss, key=lambda r: abs(r["t"] - a["t"]))
            s1 = min(ss, key=lambda r: abs(r["t"] - b["t"]))
            if s1["t"] <= s0["t"] or abs(s0["t"] - a["t"]) > 120 or abs(s1["t"] - b["t"]) > 120:
                continue
            d_pool = (s1["prot_fee_y"] - s0["prot_fee_y"]) / 1e9 * mult
            if d_pool > 0:
                pairs.append((b["t"] - a["t"], d_real, d_pool,
                              s1.get("liq_active", 0) / 1e9))
        pairs = [x for x in pairs if x[0] >= min_dt]
        if not pairs:
            print(f"{pos.get('name', pool[:8])}: no usable windows yet (need feeY_hist to accumulate)")
            continue
        ratios = [r / p for _, r, p, _ in pairs]
        tot_r, tot_p = sum(x[1] for x in pairs), sum(x[2] for x in pairs)
        print(f"{pos.get('name', pool[:8])} pool={pool[:8]} windows={len(pairs)}")
        print(f"  total: real {tot_r:.6f} SOL captured of {tot_p:.6f} pool LP fees "
              f"-> aggregate share {tot_r/tot_p:.4%}")
        print(f"  median window share {statistics.median(ratios):.4%}")
        # model comparison: paper share at median liq_active
        las = [x[3] for x in pairs if x[3] > 0]
        if las:
            la = statistics.median(las)
            model = 0.1 / (la + 0.1)
            per_sol_real = (tot_r / tot_p) / max(pos.get("sol", 0.77), 0.01)
            print(f"  liq_active median {la:.4f} SOL -> paper model share {model:.2%} per 0.1 SOL")
            print(f"  real {per_sol_real:.4%}/SOL vs model {model/0.1:.2%}/SOL "
                  f"-> model error {model/0.1/per_sol_real if per_sol_real>0 else float('inf'):.0f}x")

if __name__ == "__main__":
    main()
