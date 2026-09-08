#!/usr/bin/env python3
"""
damm_v2_rotation_sim.py — single-capital-pool LP ROTATION simulator over
damm_v2_fee_snapshots.jsonl (cp-amm pools, the live memecoin birth venue).

Same strategy skeleton as meteora_rotation_sim.py (one pool of capital
recycles through the best young pools; exit on fee death / dump / max hold /
rotation), but with cp-amm economics instead of DLMM bins:

  - Positions are full-range: position value follows the exact constant-
    product curve 2*sqrt(r)/(1+r) (r = exit price / entry price). Dumps hurt
    (r=0.2 -> -25%) but there is no narrow-range wipeout; rugs are handled
    by the dump stop and the TVL-drain exit.
  - Fees accrue from cum_fees diffs x our share of pool TVL (exact).
  - Extra exit: TVL falls below TVL_DRAIN_PCT of entry TVL => LPs are
    pulling, leave immediately ("tvl_drain").

Data caveat: births are dust at age<1h (TVL~0) and fill in later; MIN_TVL
gates entry until a pool actually carries size. Run with --grid to sweep.

Usage: python3 damm_v2_rotation_sim.py            # default, verbose
       python3 damm_v2_rotation_sim.py --grid     # parameter sweep
"""
import json, os, sys
from collections import defaultdict

MON = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(MON, "damm_v2_fee_snapshots.jsonl")

LP_USD = 1000.0
ENTRY_AGE_H = 6.0         # young pools only (births tracked from ~10min)
ENTRY_FTR = 0.10          # >=10% fee/TVL per 30min (fraction, not %)
MIN_TVL = 5000.0          # newborns are dust; wait until pool carries size
EXIT_FTR = 0.03           # fee stream dead below 3%/30min
STOP_R = 0.50             # price -50% => dump stop
MAX_HOLD_H = 2.0          # harvest and leave
ROTATE_MARGIN = 0.50      # candidate must beat current expected fees by 50%
DECAY_EXIT_PCT = 0.25     # exit when ftr falls below 25% of entry ftr
TVL_DRAIN_PCT = 0.30      # exit when tvl falls below 30% of entry tvl
TX_COST_USD = 1.00        # per entry AND per exit (priority fee + slippage)
BATCH_S = 600             # group snapshots into ~10min decision batches


def cp_value(r):
    """Full-range constant-product position value vs entry (r=price ratio)."""
    if r <= 0:
        return 0.0
    sq = r ** 0.5
    return 2 * sq / (1 + r)


def load_batches():
    by = defaultdict(list)
    for l in open(SNAP):
        try:
            r = json.loads(l)
        except Exception:
            continue
        if r.get("pool") and r.get("t"):
            by[r["pool"]].append(r)
    for rows in by.values():
        rows.sort(key=lambda r: r["t"])
    bt = defaultdict(dict)
    for pid, rows in by.items():
        for r in rows:
            b = round(r["t"] / BATCH_S) * BATCH_S
            bt[b].setdefault(pid, r)  # earliest row per batch (conservative)
    return by, sorted(bt.items())


def qualifies(r, entry_age_h, entry_ftr, min_tvl):
    return (r.get("age_h") is not None and r["age_h"] <= entry_age_h
            and (r.get("ftr_30m") or 0) >= entry_ftr
            and (r.get("tvl") or 0) >= min_tvl
            and r.get("cum_fees") is not None and r.get("price"))


def expected_fees(r, lp_usd):
    """Expected next-30min fees for our share: ftr/30min x TVL x share."""
    tvl = r.get("tvl") or 0
    share = lp_usd / (tvl + lp_usd)
    return (r.get("ftr_30m") or 0) * tvl * share


def run_rotation(batches, entry_age_h=ENTRY_AGE_H, entry_ftr=ENTRY_FTR,
                 min_tvl=MIN_TVL, exit_ftr=EXIT_FTR, stop_r=STOP_R,
                 max_hold_h=MAX_HOLD_H, rotate_margin=ROTATE_MARGIN,
                 lp_usd=LP_USD, tx_cost=TX_COST_USD):
    capital = lp_usd
    pos = None
    positions = []
    burned = set()          # never re-enter a pool we already left
    last_seen = {}

    for t_batch, snap in batches:
        for pid, r in snap.items():
            last_seen[pid] = r

        # ---- manage open position
        if pos:
            cur = snap.get(pos["pid"])
            if cur is None:
                last = pos["last"]
                r_exit = (last.get("price") or pos["p0"]) / pos["p0"]
                positions.append(close(pos, r_exit, last["t"], "vanished",
                                       tx_cost))
                capital += positions[-1]["net"]
                pos = None
            else:
                if (cur.get("cum_fees") is not None
                        and pos["last"].get("cum_fees") is not None):
                    share = pos["cap"] / ((pos["last"].get("tvl") or pos["cap"])
                                          + pos["cap"])
                    pos["fees"] += max(0.0, cur["cum_fees"]
                                       - pos["last"]["cum_fees"]) * share
                pos["last"] = cur
                r_now = (cur.get("price") or pos["p0"]) / pos["p0"]
                ftr = cur.get("ftr_30m") or 0
                held_h = (cur["t"] - pos["entry"]["t"]) / 3600
                tvl_ratio = ((cur.get("tvl") or 0)
                             / (pos["entry"].get("tvl") or 1))
                reason = None
                if r_now <= stop_r:
                    reason = "dump_stop"
                elif tvl_ratio < TVL_DRAIN_PCT:
                    reason = "tvl_drain"
                elif ftr < max(exit_ftr, pos["entry_ftr"] * DECAY_EXIT_PCT):
                    reason = "fee_dead"
                elif held_h > max_hold_h:
                    reason = "max_hold"
                if reason:
                    positions.append(close(pos, r_now, cur["t"], reason,
                                           tx_cost))
                    capital += positions[-1]["net"]
                    burned.add(pos["pid"])
                    pos = None

        # ---- rotate check (still in position)
        if pos:
            cur_exp = expected_fees(pos["last"], pos["cap"])
            best, best_exp = None, 0.0
            for pid, r in snap.items():
                if pid == pos["pid"] or not qualifies(r, entry_age_h,
                                                      entry_ftr, min_tvl):
                    continue
                e = expected_fees(r, capital)
                if e > best_exp:
                    best, best_exp = r, e
            if best and cur_exp > 0 and best_exp > cur_exp * (1 + rotate_margin):
                last = pos["last"]
                r_exit = (last.get("price") or pos["p0"]) / pos["p0"]
                positions.append(close(pos, r_exit, last["t"], "rotate",
                                       tx_cost))
                capital += positions[-1]["net"]
                burned.add(pos["pid"])
                pos = None

        # ---- entry
        if pos is None and capital > 0:
            best, best_exp = None, 0.0
            for pid, r in snap.items():
                if pid in burned:
                    continue
                if not qualifies(r, entry_age_h, entry_ftr, min_tvl):
                    continue
                e = expected_fees(r, capital)
                if e > best_exp:
                    best, best_exp = r, e
            if best:
                pos = {"pid": best["pool"], "p0": best["price"],
                       "entry": best, "last": best, "fees": 0.0,
                       "cap": capital,
                       "entry_ftr": best.get("ftr_30m") or 0}

    if pos:
        last = pos["last"]
        r_exit = (last.get("price") or pos["p0"]) / pos["p0"]
        positions.append(close(pos, r_exit, last["t"], "data_end", tx_cost))
        capital += positions[-1]["net"]

    return positions, capital


def close(pos, r_exit, t, reason, tx_cost):
    fees = pos["fees"]
    cap = pos["cap"]
    net = fees + cap * cp_value(r_exit) - cap - 2 * tx_cost
    hold_h = (t - pos["entry"]["t"]) / 3600
    return {"name": pos["entry"]["name"], "pid": pos["pid"],
            "entry_t": pos["entry"]["t"], "hold_h": round(hold_h, 2),
            "fees": round(fees, 2), "r_exit": round(r_exit, 3),
            "exit": reason, "cap_in": round(cap, 2),
            "net": round(net, 2)}


def summarize(positions, capital, lp_usd=LP_USD):
    if not positions:
        return "n=0"
    nw = sum(p["net"] for p in positions)
    pos_n = sum(1 for p in positions if p["net"] > 0)
    risk_h = sum(p["hold_h"] for p in positions)
    per_h = nw / risk_h if risk_h > 0 else 0.0
    return (f"n={len(positions)} total_net={nw:+.1f} "
            f"capital {lp_usd:.0f}->{capital:+.1f} "
            f"pos={pos_n}/{len(positions)} "
            f"net_per_risk_hour=${per_h:+.2f}")


def main():
    if not os.path.exists(SNAP):
        print("no DAMM v2 snapshots yet")
        return
    _, batches = load_batches()
    if not batches:
        print("no batches")
        return

    if "--grid" in sys.argv:
        print("DAMM v2 rotation sweep (net per $1000 recycled capital):")
        for age in (1.0, 3.0, 6.0):
            for ftr in (0.05, 0.10, 0.25):
                for tvl in (1000.0, 5000.0, 10000.0):
                    res, cap = run_rotation(batches, entry_age_h=age,
                                            entry_ftr=ftr, min_tvl=tvl)
                    print(f"age<={age:3.1f}h ftr>={ftr:4.2f} tvl>={tvl:6.0f}  "
                          + summarize(res, cap))
        return

    res, cap = run_rotation(batches)
    print(f"rotation positions: {len(res)}")
    for p in res:
        print(f"  {p['name'][:20]:<22} hold={p['hold_h']:5.2f}h "
              f"cap_in=${p['cap_in']:8.2f} fees=${p['fees']:7.2f} "
              f"r_exit={p['r_exit']:6.3f} net={p['net']:8.2f} "
              f"({p['exit']})")
    print("\n" + summarize(res, cap))
    from collections import Counter
    print("exits:", Counter(p["exit"] for p in res))


if __name__ == "__main__":
    main()
