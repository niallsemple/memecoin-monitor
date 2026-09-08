#!/usr/bin/env python3
"""
meteora_rotation_sim.py — single-capital-pool LP ROTATION simulator over
meteora_fee_snapshots.jsonl.

Owner's strategy: constantly find the best new LP, harvest fees, and pull
liquidity BEFORE pools stop working — re-evaluating on every snapshot batch.

Unlike meteora_lp_sim.py (every qualifying pool gets its own hypothetical
$1000), here ONE pool of capital recycles through positions, so opportunity
cost and capital constraints are real:

  - In cash: enter the qualifying pool with the highest expected next-window
    fee yield for our size.
  - In position: accrue exact fees via cum_fees diffs; exit on fee death,
    dump stop, max hold, pool vanishing — OR rotate when a different pool's
    expected fee yield beats the current one by ROTATE_MARGIN (covers the
    friction of moving).
  - Costs: TX_COST_USD charged per entry and per exit (priority fees +
    slippage allowance). Decision number stays net_narrow (universal narrow-
    position worst case: pumps capped at 1.0, dumps ride to r).

Snapshot cadence (~20min) approximates the 15-min re-check loop; finer
cadence needs the per-pool fast poller (separate build).

Usage: python3 meteora_rotation_sim.py            # default, verbose
       python3 meteora_rotation_sim.py --grid     # rotate-margin sweep
"""
import json, os, sys
from collections import defaultdict

MON = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(MON, "meteora_fee_snapshots.jsonl")

LP_USD = 1000.0
ENTRY_AGE_H = 12.0        # only young pools (mania class)
ENTRY_FTR = 0.50          # >=50% fee/TVL per 30min
MIN_TVL = 10000.0
EXIT_FTR = 0.10           # fee stream dead below 10%/30min
STOP_R = 0.50             # price -50% => dump stop
MAX_HOLD_H = 2.0          # fast-exit evidence: harvest and leave
ROTATE_MARGIN = 0.50      # candidate must beat current expected fees by 50%
DECAY_EXIT_PCT = 0.25     # exit when ftr falls below 25% of entry ftr
TX_COST_USD = 1.00        # per entry AND per exit (priority fee + slippage)
BATCH_S = 600             # group snapshots into ~10min decision batches


def il_narrow_worst(r):
    return min(1.0, r)


def load_batches():
    """Return (pools: pid->[rows sorted], batches: [(t_batch, {pid: row})])."""
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
            # keep the earliest row in a batch (conservative entry timing)
            bt[b].setdefault(pid, r)
    return by, sorted(bt.items())


def qualifies(r, entry_age_h, entry_ftr, min_tvl):
    return (r.get("age_h") is not None and r["age_h"] <= entry_age_h
            and (r.get("ftr_30m") or 0) >= entry_ftr
            and (r.get("tvl") or 0) >= min_tvl
            and r.get("cum_fees") is not None and r.get("price"))


def expected_fees(r, lp_usd):
    """Expected next-30min fees for our share: ftr%/30min x TVL x share."""
    tvl = r.get("tvl") or 0
    share = lp_usd / (tvl + lp_usd)
    return (r.get("ftr_30m") or 0) / 100.0 * tvl * share


def run_rotation(batches, entry_age_h=ENTRY_AGE_H, entry_ftr=ENTRY_FTR,
                 min_tvl=MIN_TVL, exit_ftr=EXIT_FTR, stop_r=STOP_R,
                 max_hold_h=MAX_HOLD_H, rotate_margin=ROTATE_MARGIN,
                 lp_usd=LP_USD, tx_cost=TX_COST_USD):
    capital = lp_usd
    pos = None          # dict: pid, entry row, last row, fees, entry capital
    positions = []
    burned = set()      # pools already exited: never re-enter (you don't go
                        # back to a pool you left)
    last_seen = {}      # pid -> last row observed (for vanished pools)

    for t_batch, snap in batches:
        for pid, r in snap.items():
            last_seen[pid] = r

        # ---- manage open position
        if pos:
            cur = snap.get(pos["pid"])
            if cur is None:
                # pool vanished from the hot list: exit at last known price
                last = pos["last"]
                r_exit = (last.get("price") or pos["p0"]) / pos["p0"]
                positions.append(close(pos, r_exit, last["t"], "vanished",
                                       tx_cost))
                capital += positions[-1]["net_narrow"]
                pos = None
            else:
                # accrue exact fees
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
                reason = None
                if r_now <= stop_r:
                    reason = "dump_stop"
                elif ftr < max(exit_ftr, pos["entry_ftr"] * DECAY_EXIT_PCT):
                    reason = "fee_dead"
                elif held_h > max_hold_h:
                    reason = "max_hold"
                if reason:
                    positions.append(close(pos, r_now, cur["t"], reason,
                                           tx_cost))
                    capital += positions[-1]["net_narrow"]
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
                capital += positions[-1]["net_narrow"]
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

    # data_end close for a still-open position
    if pos:
        last = pos["last"]
        r_exit = (last.get("price") or pos["p0"]) / pos["p0"]
        positions.append(close(pos, r_exit, last["t"], "data_end", tx_cost))
        capital += positions[-1]["net_narrow"]

    return positions, capital


def close(pos, r_exit, t, reason, tx_cost):
    fees = pos["fees"]
    cap = pos["cap"]
    narrow = fees + cap * il_narrow_worst(r_exit) - cap - 2 * tx_cost
    hold_h = (t - pos["entry"]["t"]) / 3600
    return {"name": pos["entry"]["name"], "pid": pos["pid"],
            "entry_t": pos["entry"]["t"], "hold_h": round(hold_h, 2),
            "fees": round(fees, 2), "r_exit": round(r_exit, 3),
            "exit": reason, "cap_in": round(cap, 2),
            "net_narrow": round(narrow, 2)}


def summarize(positions, capital, lp_usd=LP_USD):
    if not positions:
        return "n=0"
    nw = sum(p["net_narrow"] for p in positions)
    pos_n = sum(1 for p in positions if p["net_narrow"] > 0)
    risk_h = sum(p["hold_h"] for p in positions)
    per_h = nw / risk_h if risk_h > 0 else 0.0
    return (f"n={len(positions)} total_net={nw:+.1f} "
            f"capital {lp_usd:.0f}->{capital:+.1f} "
            f"pos={pos_n}/{len(positions)} "
            f"net_per_risk_hour=${per_h:+.2f}")


def main():
    if not os.path.exists(SNAP):
        print("no snapshots yet")
        return
    _, batches = load_batches()
    if not batches:
        print("no batches")
        return

    if "--grid" in sys.argv:
        print("rotation sweep (net per $1000 recycled capital):")
        for margin in (0.25, 0.50, 1.0):
            for hold in (1.0, 2.0):
                res, cap = run_rotation(batches, max_hold_h=hold,
                                        rotate_margin=margin)
                print(f"margin={margin:4.2f} hold<={hold:3.1f}h  "
                      + summarize(res, cap))
        return

    res, cap = run_rotation(batches)
    print(f"rotation positions: {len(res)}")
    for p in res:
        print(f"  {p['name'][:20]:<22} hold={p['hold_h']:5.2f}h "
              f"cap_in=${p['cap_in']:8.2f} fees=${p['fees']:7.2f} "
              f"r_exit={p['r_exit']:6.3f} net={p['net_narrow']:8.2f} "
              f"({p['exit']})")
    print("\n" + summarize(res, cap))
    from collections import Counter
    print("exits:", Counter(p["exit"] for p in res))


if __name__ == "__main__":
    main()
