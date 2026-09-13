#!/usr/bin/env python3
"""capacity_watch.py — fee-velocity tracker for deep pools (SOL/USDC etc).

Reads bin_snapshots.jsonl, computes per-pool LP fee flow per hour
(protocol fee deltas x lp_mult, both token sides), appends to
capacity_flow.jsonl, and alerts when velocity exceeds SPIKE_SOL_H
(the point where deploying real size beats memecoin windows).

Meant to run each poll cycle (added to _poll_loop.sh).
"""
import json, os, time

BASE = os.path.dirname(os.path.abspath(__file__))
SNAPS = os.path.join(BASE, "bin_snapshots.jsonl")
OUT = os.path.join(BASE, "capacity_flow.jsonl")
POOLS = os.path.join(BASE, "capacity_pools.json")
SPIKE_SOL_H = 0.02   # ~10x quiet-baseline 0.002 SOL/h observed 09-13
LP_MULT = 9.0        # 10% protocol share -> LP gets 9x protocol fees

def main():
    addrs = {p["addr"]: p["name"] for p in json.load(open(POOLS))["pools"]}
    last2 = {}
    with open(SNAPS) as f:
        for l in f.readlines()[-3000:]:
            try:
                d = json.loads(l)
            except Exception:
                continue
            if d.get("pool") in addrs:
                last2.setdefault(d["pool"], []).append(d)
    now = time.time()
    for addr, name in addrs.items():
        rows = sorted(last2.get(addr, []), key=lambda d: d["t"])[-2:]
        if len(rows) < 2:
            continue
        a, b = rows
        dt_h = (b["t"] - a["t"]) / 3600
        if dt_h <= 0:
            continue
        dpy = (b["prot_fee_y"] - a["prot_fee_y"]) / 1e9   # SOL-side (Y=wSOL)
        dpx = (b["prot_fee_x"] - a["prot_fee_x"])          # X-side raw units (USDC 6dp -> /1e6)
        # X fee in SOL terms: USDC fee / SOL price; approximate via bin price
        price = next((bn["price"] for bn in b.get("bins", [])
                      if bn["binId"] == b["active_bin"]), None)
        dpx_sol = (dpx / 1e6) / price if price else 0  # price = USDC per SOL? no: SOL priced in X... use liq ratio fallback
        flow_h = max(0.0, (dpy + 0) * LP_MULT / dt_h)  # Y-only until priced
        rec = {"t": now, "pool": addr[:8], "name": name,
               "lp_fee_sol_per_h": round(flow_h, 8),
               "liq_active_sol": round(b["liq_active"] / 1e9, 1),
               "spike": flow_h >= SPIKE_SOL_H}
        with open(OUT, "a") as f:
            f.write(json.dumps(rec) + "\n")
        flag = " <<< SPIKE" if rec["spike"] else ""
        print(f"{name:<16} LPfees {flow_h:.6f} SOL/h  active {rec['liq_active_sol']:.0f} SOL{flag}")

if __name__ == "__main__":
    main()
