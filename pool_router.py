#!/usr/bin/env python3
"""pool_router.py — live shadow router. Runs each poll cycle.

For every tracked pool, runs the gated active-bin sim over the trailing
TRAIL_MIN minutes and records a select/reject decision in
router_state.json. No capital moves — this builds the honest walk-forward
record that tells us whether pool selection adds value over blind-all.

Decision rule (v1, deliberately soft): REJECT only on clearly negative
edge (net < -REJECT_SOL with >= MIN_TRADES in window). A quiet hour
alone never rejects — burst-driven edges look quiet most of the time.
"""
import json, os, sys, time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from active_bin_sim import load, simulate_all, sol_usdc_ref

POOLS = os.path.join(BASE, "capacity_pools.json")
STATE = os.path.join(BASE, "router_state.json")
HIST = os.path.join(BASE, "router_history.jsonl")
TRAIL_MIN = 60
SIZE = 0.3
MIN_TRADES = 3
REJECT_SOL = 0.003

def main():
    sol_usdc = sol_usdc_ref() or 100
    metas = {p["addr"]: p for p in json.load(open(POOLS))["pools"]}
    decisions = []
    for addr, meta in metas.items():
        try:
            _, m, rows = load(addr[:8], TRAIL_MIN * 60)
        except SystemExit:
            continue
        out = simulate_all(m, rows, SIZE, sol_usdc) if rows else []
        if isinstance(out, dict):   # skipped pool type
            continue
        net = sum(t["pnl"] for t in out) if out else 0.0
        decision = "select"
        reason = "ok"
        if len(out) >= MIN_TRADES and net < -REJECT_SOL:
            decision, reason = "reject", f"net {net:+.5f} over {len(out)} trades"
        elif not out:
            reason = "quiet"
        decisions.append({"name": meta["name"], "addr": addr[:8],
                          "trades": len(out), "net": round(net, 6),
                          "decision": decision, "reason": reason})
    state = {"t": time.time(), "trail_min": TRAIL_MIN, "size": SIZE,
             "pools": decisions}
    json.dump(state, open(STATE, "w"), indent=1)
    with open(HIST, "a") as f:
        f.write(json.dumps(state) + "\n")
    sel = [d["name"] for d in decisions if d["decision"] == "select"]
    rej = [d["name"] for d in decisions if d["decision"] == "reject"]
    print(f"router: select={sel} reject={rej}")

if __name__ == "__main__":
    main()
