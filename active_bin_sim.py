#!/usr/bin/env python3
"""active_bin_sim.py — paper simulator for active-bin LP entries on token-SOL pools.

Strategy modelled (the "skim" play):
  ENTRY:  fee velocity >= SPIKE_SOL_H -> deposit Y(SOL)-only into the active bin.
  HOLD:   while our bin stays active we earn LP fees * our share of that bin.
          If price moves up through our bin, our Y converts to X at entry-bin
          price; we keep earning only if the new active bin is still ours.
  EXIT:   flow drops below EXIT_SOL_H, OR fee accrual stalls > STALL_S,
          OR timeout MAX_HOLD_S. Position valued at exit price.

All accounting in SOL. Fee capture per interval = LP fees(both sides, SOL)
* our_share_of_active_bin. Bin Y amount from snapshots (liqY lamports);
X side valued at bin price to get total bin depth.

Usage: python3 active_bin_sim.py <pool_prefix> [lookback_min] [size_sol]
"""
import json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
SNAPS = os.path.join(BASE, "bin_snapshots.jsonl")
POOLS = os.path.join(BASE, "capacity_pools.json")
from capacity_watch import fees_sol, sol_price_ref, SPIKE_SOL_H, LP_MULT

EXIT_SOL_H = 0.02
STALL_S = 120
MAX_HOLD_S = 1800
EXEC_COST_SOL = 0.0001   # verified lifecycle cost ceiling (entry+exit txs)

def load(prefix, lookback_s):
    pools = {p["addr"]: p for p in json.load(open(POOLS))["pools"]}
    addr = next((a for a in pools if a.startswith(prefix)), None)
    if not addr:
        sys.exit(f"pool {prefix} not tracked")
    import time
    cutoff = time.time() - lookback_s
    rows = []
    with open(SNAPS) as f:
        for l in f.readlines()[-30000:]:
            try:
                d = json.loads(l)
            except Exception:
                continue
            if d.get("pool") == addr and d["t"] >= cutoff:
                rows.append(d)
    return addr, pools[addr], sorted(rows, key=lambda d: d["t"])

def bin_of(d, bid):
    return next((b for b in d.get("bins", []) if b["binId"] == bid), None)

def active_price(d):
    b = bin_of(d, d["active_bin"])
    return b["price"] if b else None

def simulate(meta, rows, size, sol_usdc):
    """Run one entry at first spike; return dict of results or None."""
    if len(rows) < 4:
        return None
    if meta.get("y_sym") != "SOL":
        return {"pool": meta["name"], "skip": "Y is USDC — SOL-Y pools only for now"}
    ydiv = 10 ** meta.get("y_dec", 9)
    # find entry: first interval with flow >= spike
    ei = None
    for i in range(len(rows) - 1):
        fs = fees_sol(rows[i], rows[i + 1], meta, sol_usdc)
        dt_h = (rows[i + 1]["t"] - rows[i]["t"]) / 3600
        if fs is not None and dt_h > 0 and fs * LP_MULT / dt_h >= SPIKE_SOL_H:
            ei = i + 1
            break
    if ei is None:
        return None
    entry = rows[ei]
    ebin_id = entry["active_bin"]
    ebin = bin_of(entry, ebin_id)
    if not ebin:
        return None
    p0 = ebin["price"]                    # SOL per X at entry bin
    fees_earned = 0.0
    last_fee_t = entry["t"]
    exit_row, why = None, "timeout"
    for j in range(ei, len(rows) - 1):
        a, b = rows[j], rows[j + 1]
        fs = fees_sol(a, b, meta, sol_usdc)
        dt = b["t"] - a["t"]
        if fs is None or dt <= 0:
            continue
        lp_fees = max(0.0, fs) * LP_MULT
        if b["t"] - entry["t"] > MAX_HOLD_S:
            exit_row, why = b, "max_hold"
            break
        # our share of OUR bin while it is the active bin
        if b["active_bin"] == ebin_id:
            cur = bin_of(b, ebin_id)
            if cur:
                bin_y = cur["liqY"] / ydiv
                share = size / (bin_y + size) if bin_y + size > 0 else 0
                fees_earned += lp_fees * share
                if lp_fees > 0:
                    last_fee_t = b["t"]
        # exit checks: trailing flow over last 3 intervals (>=45s window)
        dt_h = dt / 3600
        trail = rows[max(ei - 1, j - 2):j + 2]
        fs_t = fees_sol(trail[0], trail[-1], meta, sol_usdc)
        span_h = (trail[-1]["t"] - trail[0]["t"]) / 3600
        flow_h = (fs_t * LP_MULT / span_h) if (fs_t is not None and span_h > 0) else 0
        if flow_h < EXIT_SOL_H and b["t"] - entry["t"] > 60:
            exit_row, why = b, "flow_dead"
            break
        if b["t"] - last_fee_t > STALL_S:
            exit_row, why = b, "fee_stall"
            break
    if exit_row is None:
        exit_row, why = rows[-1], "window_end"
    p1 = active_price(exit_row) or p0
    # Y-only deposit at active bin: if price FALLS through our bin we get
    # filled into X at ~p0 (we bought the dip) -> worth size*p1/p0.
    # If price RISES, our Y sits below market unfilled -> still size.
    moved_bins = exit_row["active_bin"] - ebin_id
    if moved_bins < 0:                    # filled into X, now underwater
        pos_val = size / p0 * p1
    else:                                 # unfilled Y (or still in-bin mix)
        pos_val = size
    hold_s = exit_row["t"] - entry["t"]
    pnl = fees_earned + (pos_val - size) - 2 * EXEC_COST_SOL
    return {"pool": meta["name"], "entry_t": entry["t"], "hold_s": hold_s,
            "why": why, "size": size, "fees": fees_earned,
            "price_move_pct": (p1 - p0) / p0 * 100, "moved_bins": moved_bins,
            "pos_val": pos_val, "pnl": pnl, "pnl_pct": pnl / size * 100}

def main():
    prefix = sys.argv[1]
    lookback = float(sys.argv[2]) if len(sys.argv) > 2 else 60
    size = float(sys.argv[3]) if len(sys.argv) > 3 else 0.1
    addr, meta, rows = load(prefix, lookback * 60)
    sol_usdc = sol_price_ref({addr: rows}) or 100
    r = simulate(meta, rows, size, sol_usdc)
    if not r:
        print(f"{meta['name']}: no spike entry in last {lookback:.0f}m "
              f"({len(rows)} snaps)")
        return
    if r.get("skip"):
        print(f"{meta['name']}: skipped — {r['skip']}")
        return
    import time as _t
    print(f"== active-bin sim: {r['pool']} size={size} SOL ==")
    print(f"entered {_t.strftime('%H:%M:%S', _t.localtime(r['entry_t']))} | "
          f"held {r['hold_s']:.0f}s | exit: {r['why']}")
    print(f"fees {r['fees']:+.5f} SOL | price {r['price_move_pct']:+.2f}% "
          f"({r['moved_bins']:+d} bins) | pos value {r['pos_val']:.5f}")
    print(f"net P&L {r['pnl']:+.5f} SOL  ({r['pnl_pct']:+.2f}%) "
          f"incl 2x{EXEC_COST_SOL} exec cost")

if __name__ == "__main__":
    main()
