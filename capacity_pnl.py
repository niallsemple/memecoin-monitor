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

def main():
    prefix = sys.argv[1] if len(sys.argv) > 1 else "5rCf1DM8"
    lookback_min = float(sys.argv[2]) if len(sys.argv) > 2 else 30
    addr, meta, rows = load(prefix, lookback_min * 60)
    if len(rows) < 3:
        sys.exit("not enough snapshots")
    from capacity_watch import fees_sol, sol_price_ref
    sol_usdc = sol_price_ref({addr: rows})
    # burst window: first->last row where consecutive flow >= spike
    def pair_flow(a, b):
        dt_h = (b["t"] - a["t"]) / 3600
        fs = fees_sol(a, b, meta, sol_usdc)
        return (fs * LP_MULT / dt_h) if (fs is not None and dt_h > 0) else 0.0
    seg_i = None
    for i in range(len(rows) - 1):
        if pair_flow(rows[i], rows[i + 1]) >= SPIKE_SOL_H:
            seg_i = i
            break
    if seg_i is None:
        print(f"{meta['name']}: no burst in last {lookback_min:.0f}m "
              f"(max flow {max(pair_flow(rows[i], rows[i+1]) for i in range(len(rows)-1)):.4f} SOL/h)")
        return
    entry, exit_ = rows[seg_i], rows[-1]
    dt_min = (exit_["t"] - entry["t"]) / 60
    p_in, p_out = price_of(entry), price_of(exit_)
    fs = fees_sol(entry, exit_, meta, sol_usdc) or 0.0
    lp_fees_sol = fs * LP_MULT
    tvl_usd = meta.get("tvl_usd") or 1
    il_pct = abs((p_out - p_in) / p_in) / 2 if p_in and p_out else 0
    print(f"== {meta['name']} ({addr[:8]}) burst capture ==")
    print(f"window {dt_min:.1f} min | X price {p_in:.4f} -> {p_out:.4f} "
          f"({(p_out-p_in)/p_in*100:+.2f}%) | TVL ${tvl_usd:,}")
    print(f"LP fees over window: {lp_fees_sol:.4f} SOL "
          f"(={lp_fees_sol/dt_min*60:.3f} SOL/h) | IL proxy {il_pct*100:.3f}%")
    print("(share = size_usd/TVL — pool-wide avg; active-bin positions do better,")
    print(" stranded bins do worse; JIT competition not modeled)")
    print(f"\n{'size SOL':>9} {'share':>9} {'fees':>9} {'IL drag':>9} {'net':>9} {'net%':>8}")
    sol_px = sol_usdc or 100
    for size in (0.1, 1, 10, 50, 100, 500):
        share = (size * sol_px) / (tvl_usd + size * sol_px)
        fees = lp_fees_sol * share
        il = size * il_pct
        net = fees - il
        print(f"{size:>9.1f} {share*100:>8.4f}% {fees:>9.5f} {il:>9.5f} "
              f"{net:>+9.5f} {net/size*100:>+7.3f}%")

if __name__ == "__main__":
    main()
