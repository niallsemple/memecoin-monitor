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

def sol_price_ref(rows_by_pool):
    """SOL/USDC price from the main SOL-USDC pool's latest active-bin price."""
    for addr, rows in rows_by_pool.items():
        if not rows:
            continue
        b = rows[-1]
        p = next((bn["price"] for bn in b.get("bins", [])
                  if bn["binId"] == b["active_bin"]), None)
        if p and 20 < p < 1000:  # USDC per SOL sanity range
            return p
    return None

STABLES = {"USDC", "USDT", "USDH"}

def fees_sol(a, b, meta, sol_usdc):
    """Both-side protocol-fee delta between snapshots a->b, in SOL.
    DLMM bin price = Y per X. fee_x(in X units) * price = Y units;
    Y units -> SOL via y_sym (SOL direct, stable via sol_usdc)."""
    p = next((bn["price"] for bn in b.get("bins", [])
              if bn["binId"] == b["active_bin"]), None)
    if not p:
        return None
    y_units = max(0, b["prot_fee_x"] - a["prot_fee_x"]) / 10 ** meta["x_dec"] * p \
            + max(0, b["prot_fee_y"] - a["prot_fee_y"]) / 10 ** meta["y_dec"]
    # note: negative side delta = protocol fee claim reset; clamped to 0
    if meta["y_sym"] == "SOL":
        return y_units
    if meta["y_sym"] in STABLES and sol_usdc:
        return y_units / sol_usdc
    return None

def main():
    pools = {p["addr"]: p for p in json.load(open(POOLS))["pools"]}
    last2 = {}
    with open(SNAPS) as f:
        for l in f.readlines()[-3000:]:
            try:
                d = json.loads(l)
            except Exception:
                continue
            if d.get("pool") in pools:
                last2.setdefault(d["pool"], []).append(d)
    sol_usdc = sol_price_ref(last2)
    now = time.time()
    for addr, meta in pools.items():
        rows = sorted(last2.get(addr, []), key=lambda d: d["t"])[-2:]
        if len(rows) < 2:
            continue
        a, b = rows
        dt_h = (b["t"] - a["t"]) / 3600
        if dt_h <= 0:
            continue
        fs = fees_sol(a, b, meta, sol_usdc)
        if fs is None:
            continue
        flow_h = max(0.0, fs * LP_MULT / dt_h)
        if flow_h > 500:   # bogus pair (e.g. counter reset) — discard
            continue
        rec = {"t": now, "pool": addr[:8], "name": meta["name"],
               "lp_fee_sol_per_h": round(flow_h, 8),
               "liq_active_sol": round(b["liq_active"] / 1e9, 1),
               "spike": flow_h >= SPIKE_SOL_H}
        with open(OUT, "a") as f:
            f.write(json.dumps(rec) + "\n")
        flag = " <<< SPIKE" if rec["spike"] else ""
        print(f"{meta['name']:<16} LPfees {flow_h:.6f} SOL/h  active {rec['liq_active_sol']:.0f} SOL{flag}")

if __name__ == "__main__":
    main()
