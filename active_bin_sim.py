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
EXIT_SLIP_PCT = float(os.environ.get("EXIT_SLIP_PCT", "0.005"))  # flat fill-exit slippage

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

def drift_pct(rows, i, back=4):
    """Trailing price drift over ~`back` snapshots ending at index i."""
    if i < back:
        return None
    p_now = active_price(rows[i])
    p_then = active_price(rows[i - back])
    if p_now and p_then:
        return (p_now - p_then) / p_then * 100
    return None

MOM_GATE_PCT = -0.10    # only enter if trailing ~60s drift >= this (flat-to-up)
MAX_SHARE = 0.25   # JIT/bot competition cap: we never get more than ~25% of a bin

def simulate(meta, rows, size, sol_usdc, momentum=True, start=0):
    """Run one entry from index `start`; return (result, exit_index) or (None, None)."""
    if len(rows) < 4:
        return None, None
    if meta.get("y_sym") != "SOL" and meta.get("y_sym") not in ("USDC", "USDT", "USDH"):
        return {"pool": meta["name"], "skip": f"Y={meta.get('y_sym')} unsupported"}, None
    y_stable = meta.get("y_sym") in ("USDC", "USDT", "USDH")
    if y_stable and not sol_usdc:
        return {"pool": meta["name"], "skip": "no SOL/USDC reference price"}, None
    ydiv = 10 ** meta.get("y_dec", 9)
    y_amt = size * sol_usdc if y_stable else size   # our deposit in Y units
    # find entry: first interval with flow >= spike (momentum-gated)
    ei = None
    for i in range(start, len(rows) - 1):
        fs = fees_sol(rows[i], rows[i + 1], meta, sol_usdc)
        dt_h = (rows[i + 1]["t"] - rows[i]["t"]) / 3600
        if fs is not None and dt_h > 0 and fs * LP_MULT / dt_h >= SPIKE_SOL_H:
            if momentum:
                d = drift_pct(rows, i + 1)
                if d is None or d < MOM_GATE_PCT:
                    continue          # skip: no history, or price falling into burst
            ei = i + 1
            break
    if ei is None:
        return None, None
    entry = rows[ei]
    ebin_id = entry["active_bin"]
    ebin = bin_of(entry, ebin_id)
    if not ebin:
        return None, None
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
                share = y_amt / (bin_y + y_amt) if bin_y + y_amt > 0 else 0
                share = min(share, MAX_SHARE)
                fees_earned += lp_fees * share
                if lp_fees > 0:
                    last_fee_t = b["t"]
        # exit checks: trailing flow over last 3 intervals (>=45s window)
        dt_h = dt / 3600
        trail = rows[max(ei - 1, j - 2):j + 2]
        fs_t = fees_sol(trail[0], trail[-1], meta, sol_usdc)
        span_h = (trail[-1]["t"] - trail[0]["t"]) / 3600
        flow_h = (fs_t * LP_MULT / span_h) if (fs_t is not None and span_h > 0) else 0
        # fill-stop: price dropped below our bin -> we just got filled into X;
        # bail immediately, capping IL at ~1 bin of adverse move
        if b["active_bin"] < ebin_id:
            exit_row, why = b, "fill_stop"
            break
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
    # exit slippage: on fill_stop we hold X and must swap X->Y on a thin token;
    # haircut scales with our share of the bin we just got filled in
    slip = 0.0
    if why == "fill_stop":
        slip = size * EXIT_SLIP_PCT   # flat assumption; live probes must measure truth
    pnl = fees_earned + (pos_val - size) - 2 * EXEC_COST_SOL - slip
    exit_idx = next((k for k, r in enumerate(rows) if r is exit_row), len(rows) - 1)
    return ({"pool": meta["name"], "entry_t": entry["t"], "hold_s": hold_s,
            "why": why, "size": size, "fees": fees_earned,
            "price_move_pct": (p1 - p0) / p0 * 100, "moved_bins": moved_bins,
            "pos_val": pos_val, "pnl": pnl, "pnl_pct": pnl / size * 100},
            exit_idx + 1)

COOLDOWN_S = 300   # after a fill_stop, wait before re-entering same pool

def simulate_all(meta, rows, size, sol_usdc, momentum=True):
    """Chain entries across the whole window: every gated spike, sequentially."""
    trades, start, cooldown_until = [], 0, 0
    while True:
        r, nxt = simulate(meta, rows, size, sol_usdc, momentum=momentum,
                          start=start)
        if r is None:
            break
        if r.get("skip"):
            return r
        if r["entry_t"] < cooldown_until:
            start = max(nxt or len(rows), start + 1)
            continue
        trades.append(r)
        if r["why"] == "fill_stop" and r["fees"] < 2 * EXEC_COST_SOL:
            cooldown_until = r["entry_t"] + r["hold_s"] + COOLDOWN_S
        start = max(nxt or len(rows), start + 1)
    return trades

SOL_USDC_POOL = "5rCf1DM8LjKTw4YqhnoLcngyZYeNnQqztScTogYHAS6"

def sol_usdc_ref():
    """Latest SOL/USDC price from the main pool's snapshots."""
    last = None
    with open(SNAPS) as f:
        for l in f.readlines()[-5000:]:
            try:
                d = json.loads(l)
            except Exception:
                continue
            if d.get("pool") == SOL_USDC_POOL:
                last = d
    if last:
        return active_price(last)
    return None

def main():
    prefix = sys.argv[1]
    lookback = float(sys.argv[2]) if len(sys.argv) > 2 else 60
    size = float(sys.argv[3]) if len(sys.argv) > 3 else 0.1
    addr, meta, rows = load(prefix, lookback * 60)
    sol_usdc = sol_usdc_ref() or 100
    import time as _t
    for mom in (False, True):
        out = simulate_all(meta, rows, size, sol_usdc, momentum=mom)
        tag = "MOMENTUM-GATED" if mom else "ungated       "
        if not out:
            print(f"[{tag}] {meta['name']}: no entries in {lookback:.0f}m")
            continue
        if isinstance(out, dict) and out.get("skip"):
            print(f"[{tag}] {meta['name']}: skipped — {out['skip']}")
            break
        tot = sum(t["pnl"] for t in out)
        wins = sum(1 for t in out if t["pnl"] > 0)
        print(f"[{tag}] {meta['name']:<12} {len(out)} trades "
              f"({wins}W/{len(out)-wins}L) net {tot:+.5f} SOL")
        for t in out:
            print(f"    {_t.strftime('%H:%M:%S', _t.localtime(t['entry_t']))} "
                  f"hold {t['hold_s']:>4.0f}s {t['why']:<10} "
                  f"fees {t['fees']:+.5f} move {t['price_move_pct']:+6.2f}% "
                  f"net {t['pnl']:+.5f} ({t['pnl_pct']:+.2f}%)")

if __name__ == "__main__":
    main()
