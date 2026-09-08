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

Usage: python3 meteora_lp_sim.py          # default criteria, verbose
       python3 meteora_lp_sim.py --grid   # entry-criteria sensitivity sweep
"""
import json, os, sys
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
    """Value multiplier for a full-range (v2-style) position."""
    return 2 * (r ** 0.5) / (1 + r) if r > 0 else 0.0


def il_all_token(r):
    """50/50 entry where the token side rides price all the way."""
    return (1 + r) / 2


def il_narrow_worst(r):
    """Universal worst case for a NARROW DLMM position (range -> 0):
    instant adverse move. Dump (r<1): fully converted to token at ~entry,
    multiplier -> r. Pump (r>1): fully converted to SOL at ~entry, misses
    the pump, multiplier -> 1. So worst = min(1, r)."""
    return min(1.0, r)


def load_pools():
    by = defaultdict(list)
    for l in open(SNAP):
        try:
            r = json.loads(l)
        except Exception:
            continue
        if r.get("pool"):
            by[r["pool"]].append(r)
    return by


def run_sim(by, entry_age_h, entry_ftr, lp_usd=LP_USD, min_tvl=MIN_TVL,
            exit_ftr=EXIT_FTR, stop_r=STOP_R, max_hold_h=MAX_HOLD_H):
    results = []
    for pool, rows in by.items():
        rows.sort(key=lambda r: r["t"])
        # entry
        e = None
        for r in rows:
            if (r.get("age_h") is not None and r["age_h"] <= entry_age_h
                    and (r.get("ftr_30m") or 0) >= entry_ftr
                    and (r.get("tvl") or 0) >= min_tvl
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
                share = lp_usd / ((last.get("tvl") or lp_usd) + lp_usd)
                fees += max(0.0, r["cum_fees"] - last["cum_fees"]) * share
            last = r
            rr = (r.get("price") or p0) / p0
            ftr = r.get("ftr_30m") or 0
            if rr <= stop_r:
                exit_reason = "dump_stop"
                break
            if ftr < exit_ftr:
                exit_reason = "fee_dead"
                break
            if (r.get("age_h") or 0) > max_hold_h:
                exit_reason = "max_hold"
                break
        r_exit = (last.get("price") or p0) / p0
        hold_h = (last["t"] - e["t"]) / 3600
        # three IL scenarios; net_worst is the decision-grade number
        narrow = fees + lp_usd * il_narrow_worst(r_exit) - lp_usd
        lo = fees + lp_usd * il_full_range(r_exit) - lp_usd
        hi = fees + lp_usd * il_all_token(r_exit) - lp_usd
        results.append({
            "name": e["name"], "entry_t": e["t"], "hold_h": round(hold_h, 2),
            "fees": round(fees, 2), "r_exit": round(r_exit, 3),
            "exit": exit_reason,
            "net_narrow": round(narrow, 2),
            "net_lo": round(lo, 2), "net_hi": round(hi, 2),
            "entry_tvl": round(e.get("tvl") or 0),
            "tvl_share": round(lp_usd / ((e.get("tvl") or lp_usd) + lp_usd), 3),
        })
    return results


def summarize(results, lp_usd=LP_USD):
    if not results:
        return "n=0"
    nw = sum(r["net_narrow"] for r in results) / len(results)
    lo = sum(r["net_lo"] for r in results) / len(results)
    hi = sum(r["net_hi"] for r in results) / len(results)
    pos_nw = sum(1 for r in results if r["net_narrow"] > 0)
    return (f"n={len(results)} mean_narrow_worst={nw:+.1f} "
            f"mean_net=[{lo:+.1f}, {hi:+.1f}] "
            f"pos_narrow_worst={pos_nw}/{len(results)}")


def main():
    if not os.path.exists(SNAP):
        print("no snapshots yet")
        return
    by = load_pools()

    if "--grid" in sys.argv:
        print("entry-criteria sensitivity sweep (net per $1000 position):")
        print(f"{'age<=h':>7s} {'ftr>=':>6s} {'tvl>=':>7s}  summary")
        for age in (3.0, 6.0, 12.0):
            for ftr in (0.25, 0.50, 1.0):
                res = run_sim(by, age, ftr)
                print(f"{age:7.0f} {ftr:6.2f} {'10k':>7s}  {summarize(res)}")
        # high-capacity class: big pools, lower fee rate, any age
        for ftr in (0.02, 0.05, 0.10):
            res = run_sim(by, 1e9, ftr, min_tvl=100000.0)
            print(f"{'any':>7s} {ftr:6.2f} {'100k':>7s}  {summarize(res)}")
        return

    results = run_sim(by, ENTRY_AGE_H, ENTRY_FTR)
    print(f"simulated LP positions: {len(results)}")
    for r in sorted(results, key=lambda x: -x["fees"]):
        print(f"  {r['name'][:20]:<22} hold={r['hold_h']:5.2f}h fees=${r['fees']:7.2f} "
              f"r_exit={r['r_exit']:6.3f} net_worst={r['net_narrow']:8.2f} "
              f"net=[{r['net_lo']:8.2f}, {r['net_hi']:8.2f}] "
              f"({r['exit']}) share={r['tvl_share']:.1%}")
    if results:
        print(f"\nmean net per ${LP_USD:.0f} position: {summarize(results)}")
        cap = [r for r in results if r["tvl_share"] > 0.10]
        if cap:
            print(f"capacity warning: {len(cap)} positions exceed 10% of pool TVL "
                  f"(fee-share model less reliable, entry moves market)")
        from collections import Counter
        print("exits:", Counter(r["exit"] for r in results))


if __name__ == "__main__":
    main()
