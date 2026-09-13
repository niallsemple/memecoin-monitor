#!/usr/bin/env python3
"""regime_paper.py — forward paper-trading of the flat-harvest rule.

Backtest (FINDINGS.md 2026-09-13) says the paying condition is fee bursts
while price is FLAT (regime_edge ratio >= 1.5, esp. ratio~999). This validates
that forward on live data, no real SOL:

  OPEN  : pool's latest regime_edge ratio >= EDGE_MIN, no open paper position
  CLOSE : ratio < EDGE_MIN on a later cycle, or MAX_AGE_S exceeded
  P&L   : fees = protocol fee delta (entry->exit snapshot) * LP_MULT * share
          share = size in Y raw / liq_active, capped at 5% (artifact guard)
          IL    = |price drift|/2 * size ;  minus FIXED probe overhead

Runs one-shot per poll cycle (after regime_edge.py in _poll_loop.sh).
State: regime_paper_state.json ; closed trades: regime_paper.jsonl
"""
import json, os, sys, time

BASE = os.path.dirname(os.path.abspath(__file__))
SNAPS = os.path.join(BASE, "bin_snapshots.jsonl")
POOLS = os.path.join(BASE, "capacity_pools.json")
EDGE_LOG = os.path.join(BASE, "regime_edge.jsonl")
STATE = os.path.join(BASE, "regime_paper_state.json")
TRADES = os.path.join(BASE, "regime_paper.jsonl")

EDGE_MIN = 1.5
SIZE = 0.05
FIXED = 0.0002
LP_MULT = 9.0
MAX_AGE_S = 900
SHARE_CAP = 0.05

sys.path.insert(0, BASE)
from capacity_watch import fees_sol, sol_price_ref, STABLES  # noqa: E402


def price_of(d):
    return next((bn["price"] for bn in d.get("bins", [])
                 if bn["binId"] == d["active_bin"]), None)


def main():
    pools = {p["addr"]: p for p in json.load(open(POOLS))["pools"]}

    # latest regime_edge ratio per pool (written by regime_edge.py this cycle)
    ratios = {}
    try:
        with open(EDGE_LOG) as f:
            for line in f.readlines()[-200:]:
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                ratios[d["addr"]] = d.get("ratio", 0.0)
    except FileNotFoundError:
        return

    # latest snapshot per pool
    snaps = {}
    with open(SNAPS) as f:
        for line in f.readlines()[-6000:]:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("pool") in pools:
                snaps[d["pool"]] = d

    try:
        state = json.load(open(STATE))
    except Exception:
        state = {"open": {}, "closed": 0, "net": 0.0}

    sol_usdc = None
    for addr, meta in pools.items():
        key = addr[:8]
        snap = snaps.get(addr)
        ratio = ratios.get(key, 0.0)
        pos = state["open"].get(addr)

        if pos is None:
            if snap and ratio >= EDGE_MIN:
                state["open"][addr] = {"t": time.time(), "snap": snap,
                                       "ratio_in": ratio}
                print(f"paper OPEN {meta['name']} ratio {ratio:.1f}")
            continue

        # position open: close?
        age = time.time() - pos["t"]
        if snap is None:
            continue
        if ratio < EDGE_MIN or age > MAX_AGE_S:
            if sol_usdc is None:
                sol_usdc = sol_price_ref({a: [s] for a, s in snaps.items()}) or 100
            a, b = pos["snap"], snap
            try:
                fs = (fees_sol(a, b, meta, sol_usdc) or 0) * LP_MULT
            except (KeyError, TypeError):
                fs = 0.0
            liq_act = float(b.get("liq_active") or 0)
            if meta["y_sym"] == "SOL":
                our_raw = SIZE * 1e9
            else:
                our_raw = SIZE * sol_usdc * 10 ** meta["y_dec"]
            share = min(our_raw / liq_act, SHARE_CAP) if liq_act > 0 else 0
            fees = fs * share
            p_in, p_out = price_of(a), price_of(b)
            il = abs(p_out - p_in) / p_in / 2 * SIZE if p_in and p_out else 0
            net = fees - il - FIXED
            rec = {"t": time.time(), "pool": meta["name"], "addr": key,
                   "age_s": round(age), "ratio_in": pos["ratio_in"],
                   "fees": round(fees, 6), "il": round(il, 6),
                   "net": round(net, 6),
                   "exit": "ratio_break" if ratio < EDGE_MIN else "max_age"}
            with open(TRADES, "a") as f:
                f.write(json.dumps(rec) + "\n")
            state["closed"] += 1
            state["net"] = round(state["net"] + net, 6)
            del state["open"][addr]
            print(f"paper CLOSE {meta['name']} age {age:.0f}s "
                  f"net {net:+.5f} | cum {state['net']:+.5f} "
                  f"over {state['closed']} trades")

    json.dump(state, open(STATE, "w"))


if __name__ == "__main__":
    main()
