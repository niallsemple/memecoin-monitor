#!/usr/bin/env python3
"""
meteora_lp_sim.py — paper-LP simulator over meteora_fee_snapshots.jsonl.

Question (memo #32 priority 2): does supplying narrow liquidity to fresh,
high-fee memecoin DLMM pools earn more in fees than it loses to IL/dumps?

Model:
  Entry:  first snapshot with age_h <= ENTRY_AGE_H, ftr_30m >= ENTRY_FTR,
          tvl >= MIN_TVL, cum_fees present.
  Size:   LP_USD added to pool; fee share = LP_USD / (tvl_i + LP_USD)
          (conservative: capture == TVL share, no active-bin bonus).
  Fees:   exact via cum_fees diffs (no rolling-window double counting).
  IL:     reported as two bounds on position value ratio at exit
            lower-bound loss = full-range IL 2*sqrt(r)/(1+r)
            upper-bound loss = all-token inventory: (1+r)/2  (50/50 entry,
                               token side rides price all the way)
          where r = exit_price / entry_price.
  Exit:   ftr_30m < EXIT_FTR (fee stream dead) | r <= STOP_R (dump stop) |
          age > MAX_HOLD_H | pool vanishes from snapshots (last price).
  Survivorship: pools never hot enough to enter are never simulated — fine,
  the entry rule IS the filter.

Usage: python3 meteora_lp_sim.py
"""
import json, os
from collections import defaultdict

MON = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(MON, "meteora_fee_snapshots.jsonl")

LP_USD = 1000.0
ENTRY_AGE_H = 12.0
ENTRY_FTR = 0.50          # >=50% fee/TVL per 30min
MIN_TVL = 10000.0
EXIT_FTR = 0.10           # fee stream dead below 10%/30min
STOP_R = 0.50             # price -50% => dump stop
MAX_HOLD_H = 24.0


def il_full_range(r):
    return 2 * (r ** 0.5) / (1 + r) if r > 0 else 0.0


def il_all_token(r):
    return (1 + r) / 2


def main():
    if not os.path.exists(SNAP):
        print("no snapshots yet")
        return
    by = defaultdict(list)
    for l in open(SNAP):
        try:
            r = json.loads(l)
        except Exception:
            continue
        if r.get("pool"):
            by[r["pool"]].append(r)

    results = []
    for pool, rows in by.items():
        rows.sort(key=lambda r: r["t"])
        # entry
        e = None
        for r in rows:
            if (r.get("age_h") is not None and r["age_h"] <= ENTRY_AGE_H
                    and (r.get("ftr_30m") or 0) >= ENTRY_FTR
                    and (r.get("tvl") or 0) >= MIN_TVL
                    and r.get("cum_fees") is not None and r.get("price")):
                e = r
                break
        if not e:
            continue
        p0 = e["price"]
        fees = 0.0
        last = e
        exit_reason = "data_end"
        for r in rows[rows.index(e) + 1:]:
            if r.get("cum_fees") is not None and last.get("cum_fees") is not None:
                share = LP_USD / ((last.get("tvl") or LP_USD) + LP_USD)
                fees += max(0.0, r["cum_fees"] - last["cum_fees"]) * share
            last = r
            rr = (r.get("price") or p0) / p0
            ftr = r.get("ftr_30m") or 0
            if rr <= STOP_R:
                exit_reason = "dump_stop"
                break
            if ftr < EXIT_FTR:
                exit_reason = "fee_dead"
                break
            if (r.get("age_h") or 0) > MAX_HOLD_H:
                exit_reason = "max_hold"
                break
        r_exit = (last.get("price") or p0) / p0
        hold_h = (last["t"] - e["t"]) / 3600
        lo = fees + LP_USD * il_full_range(r_exit) - LP_USD
        hi = fees + LP_USD * il_all_token(r_exit) - LP_USD
        results.append({
            "name": e["name"], "entry_t": e["t"], "hold_h": round(hold_h, 2),
            "fees": round(fees, 2), "r_exit": round(r_exit, 3),
            "exit": exit_reason,
            "net_lo": round(lo, 2), "net_hi": round(hi, 2),
            "entry_tvl": round(e.get("tvl") or 0),
        })

    print(f"simulated LP positions: {len(results)}")
    for r in sorted(results, key=lambda x: -x["fees"]):
        print(f"  {r['name'][:20]:<22} hold={r['hold_h']:5.2f}h fees=${r['fees']:7.2f} "
              f"r_exit={r['r_exit']:6.3f} net=[{r['net_lo']:8.2f}, {r['net_hi']:8.2f}] "
              f"({r['exit']})")
    if results:
        lo = sum(r["net_lo"] for r in results) / len(results)
        hi = sum(r["net_hi"] for r in results) / len(results)
        pos = sum(1 for r in results if r["net_lo"] > 0)
        print(f"\nmean net per ${LP_USD:.0f} position: [{lo:+.2f}, {hi:+.2f}] USD")
        print(f"positive even under full-range-IL bound: {pos}/{len(results)}")
        from collections import Counter
        print("exits:", Counter(r["exit"] for r in results))


if __name__ == "__main__":
    main()
