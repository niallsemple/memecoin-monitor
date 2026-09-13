#!/usr/bin/env python3
"""capacity_pnl.py — paper P&L for hypothetical LP size in deep pools over a burst.

Scans bin_snapshots.jsonl for a pool, finds the burst window (fee velocity
>= spike threshold), computes both-side LP fee capture at a range of sizes,
and nets off IL from active-bin price move between entry and exit.

Usage: python3 capacity_pnl.py [pool_prefix] [lookback_min]
"""
import json, os, sys, time

BASE = os.path.dirname(os.path.abspath(__file__))
SNAPS = os.path.join(BASE, "bin_snapshots.jsonl")
POOLS = os.path.join(BASE, "capacity_pools.json")
LP_MULT = 9.0
SPIKE_SOL_H = 0.02

def load(pool_prefix, lookback_s):
    addrs = {p["addr"]: p for p in json.load(open(POOLS))["pools"]}
    addr = next((a for a in addrs if a.startswith(pool_prefix)), None)
    if not addr:
        sys.exit(f"pool {pool_prefix} not in capacity_pools.json")
    cutoff = time.time() - lookback_s
    rows = []
    with open(SNAPS) as f:
        for l in f.readlines()[-20000:]:
            try:
                d = json.loads(l)
            except Exception:
                continue
            if d.get("pool") == addr and d["t"] >= cutoff:
                rows.append(d)
    return addr, addrs[addr], sorted(rows, key=lambda d: d["t"])

def price_of(d):
    return next((bn["price"] for bn in d.get("bins", [])
                 if bn["binId"] == d["active_bin"]), None)

def flow_h(a, b):
    dt_h = (b["t"] - a["t"]) / 3600
    if dt_h <= 0:
        return 0.0, None
    p = price_of(b)
    dpy = (b["prot_fee_y"] - a["prot_fee_y"]) / 1e9
    dpx = ((b["prot_fee_x"] - a["prot_fee_x"]) / 1e6) / p if p else 0
    return max(0.0, (dpy + dpx) * LP_MULT / dt_h), p

def main():
    prefix = sys.argv[1] if len(sys.argv) > 1 else "5rCf1DM8"
    lookback_min = float(sys.argv[2]) if len(sys.argv) > 2 else 30
    addr, meta, rows = load(prefix, lookback_min * 60)
    if len(rows) < 3:
        sys.exit("not enough snapshots")
    # burst window: first->last row where consecutive flow >= spike
    seg_i = None
    for i in range(len(rows) - 1):
        f, _ = flow_h(rows[i], rows[i + 1])
        if f >= SPIKE_SOL_H:
            seg_i = i
            break
    if seg_i is None:
        print(f"{meta['name']}: no burst in last {lookback_min:.0f}m "
              f"(max flow {max(flow_h(rows[i], rows[i+1])[0] for i in range(len(rows)-1)):.4f} SOL/h)")
        return
    entry, exit_ = rows[seg_i], rows[-1]
    dt_min = (exit_["t"] - entry["t"]) / 60
    p_in, p_out = price_of(entry), price_of(exit_)
    dpy = (exit_["prot_fee_y"] - entry["prot_fee_y"]) / 1e9
    dpx = ((exit_["prot_fee_x"] - entry["prot_fee_x"]) / 1e6) / p_out if p_out else 0
    lp_fees_sol = (dpy + dpx) * LP_MULT
    liq_sol = entry["liq_active"] / 1e9
    il_pct = abs((p_out - p_in) / p_in) / 2 if p_in and p_out else 0  # rough LP IL proxy
    print(f"== {meta['name']} ({addr[:8]}) burst capture ==")
    print(f"window {dt_min:.1f} min | price {p_in:.3f} -> {p_out:.3f} "
          f"({(p_out-p_in)/p_in*100:+.2f}%) | active liq {liq_sol:,.0f} SOL")
    print(f"LP fees over window: {lp_fees_sol:.4f} SOL "
          f"(={lp_fees_sol/dt_min*60:.3f} SOL/h) | IL proxy {il_pct*100:.3f}%")
    print(f"\n{'size SOL':>9} {'share':>9} {'fees':>9} {'IL drag':>9} {'net':>9} {'net%':>8}")
    for size in (0.1, 1, 10, 50, 100, 500):
        share = size / (liq_sol + size)
        fees = lp_fees_sol * share
        il = size * il_pct
        net = fees - il
        print(f"{size:>9.1f} {share*100:>8.4f}% {fees:>9.5f} {il:>9.5f} "
              f"{net:>+9.5f} {net/size*100:>+7.3f}%")

if __name__ == "__main__":
    main()
