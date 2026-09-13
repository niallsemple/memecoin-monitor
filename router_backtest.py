#!/usr/bin/env python3
"""router_backtest.py — walk-forward pool selection test.

Split each pool's snapshots at time T_split:
  - SELECTION window [start, T_split): run gated sim, keep pools with net > 0
  - TRADING window [T_split, end): run gated sim only on selected pools

This is the honest version of "only trade pools with positive trailing P&L":
no lookahead — selection uses only past data, exactly like a live router would.

Usage: python3 router_backtest.py [select_min] [trade_min] [size]
"""
import json, os, sys, time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from active_bin_sim import (load, simulate_all, sol_usdc_ref)

POOLS = os.path.join(BASE, "capacity_pools.json")

def main():
    select_min = float(sys.argv[1]) if len(sys.argv) > 1 else 60
    trade_min = float(sys.argv[2]) if len(sys.argv) > 2 else 60
    size = float(sys.argv[3]) if len(sys.argv) > 3 else 0.3
    sol_usdc = sol_usdc_ref() or 100
    metas = {p["addr"]: p for p in json.load(open(POOLS))["pools"]}
    now = time.time()
    t_split = now - trade_min * 60
    sel_rows_all, tr_rows_all = {}, {}
    for addr, meta in metas.items():
        a, m, rows = load(addr[:8], (select_min + trade_min) * 60)
        if not rows:
            continue
        sel = [r for r in rows if r["t"] < t_split]
        trd = [r for r in rows if r["t"] >= t_split]
        # selection window needs the tail of rows before split for drift context;
        # trading window keeps last few pre-split rows for drift warm-up
        warmup = sel[-5:]
        sel_rows_all[addr] = (m, sel)
        tr_rows_all[addr] = (m, warmup + trd)

    selected = []
    print(f"--- SELECTION window ({select_min:.0f}m) ---")
    for addr, (m, rows) in sel_rows_all.items():
        out = simulate_all(m, rows, size, sol_usdc)
        if isinstance(out, dict) or not out:
            print(f"  {m['name']:<16} no trades")
            continue
        net = sum(t["pnl"] for t in out)
        mark = "SELECT" if net > 0 else "reject"
        print(f"  {m['name']:<16} {len(out):>2} trades  net {net:+.5f}  {mark}")
        if net > 0:
            selected.append(addr)

    print(f"\n--- TRADING window ({trade_min:.0f}m), selected pools only ---")
    tot, ntr = 0.0, 0
    for addr in selected:
        m, rows = tr_rows_all[addr]
        out = simulate_all(m, rows, size, sol_usdc)
        if isinstance(out, dict) or not out:
            print(f"  {m['name']:<16} no trades")
            continue
        net = sum(t["pnl"] for t in out)
        wins = sum(1 for t in out if t["pnl"] > 0)
        tot += net
        ntr += len(out)
        print(f"  {m['name']:<16} {len(out):>2} trades ({wins}W)  net {net:+.5f}")
    # comparison: all pools traded blindly in trading window
    tot_all = 0.0
    for addr, (m, rows) in tr_rows_all.items():
        out = simulate_all(m, rows, size, sol_usdc)
        if isinstance(out, dict) or not out:
            continue
        tot_all += sum(t["pnl"] for t in out)
    print(f"\nROUTED total: {tot:+.5f} SOL over {ntr} trades "
          f"({len(selected)} pools selected)")
    print(f"BLIND  total: {tot_all:+.5f} SOL (all {len(tr_rows_all)} pools)")
    print(f"selection edge: {tot - tot_all:+.5f} SOL")

if __name__ == "__main__":
    main()
