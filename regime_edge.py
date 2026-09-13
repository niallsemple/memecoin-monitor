#!/usr/bin/env python3
"""regime_edge.py — per-pool LP viability ratio: fee yield rate vs IL drag rate.

The capacity-branch falsification (see FINDINGS.md 2026-09-13) showed LP-ing
loses whenever IL drag/hour exceeds fee capture/hour. Both are measurable from
bin snapshots:

  fee_rate  = LP-capturable fees per hour / TVL   (SOL per SOL per hour)
  il_rate   = |price drift|/hour / 2              (IL proxy per hour)

edge_ratio = fee_rate / il_rate. LP-ing is only viable when ratio > 1 with
margin; we flag FAVORABLE when ratio >= EDGE_MIN sustained for SUSTAIN
consecutive poll cycles.

Runs one-shot per poll cycle from _poll_loop.sh. Appends to regime_edge.jsonl,
prints a one-line summary, and prints a loud banner when a pool flips
FAVORABLE (state in regime_edge_state.json).
"""
import json, os, sys, time

BASE = os.path.dirname(os.path.abspath(__file__))
SNAPS = os.path.join(BASE, "bin_snapshots.jsonl")
POOLS = os.path.join(BASE, "capacity_pools.json")
STATE = os.path.join(BASE, "regime_edge_state.json")
OUT = os.path.join(BASE, "regime_edge.jsonl")

LOOKBACK_S = 3600          # 1h window for rates
EDGE_MIN = 1.5             # fee rate must beat IL rate by 1.5x
SUSTAIN = 3                # consecutive favorable cycles to declare regime
LP_MULT = 9.0              # active-bin concentration multiplier (capacity_watch)

sys.path.insert(0, BASE)
from capacity_watch import fees_sol, sol_price_ref, STABLES  # noqa: E402


def price_of(d):
    return next((bn["price"] for bn in d.get("bins", [])
                 if bn["binId"] == d["active_bin"]), None)


def main():
    pools = {p["addr"]: p for p in json.load(open(POOLS))["pools"]}
    cutoff = time.time() - LOOKBACK_S
    recent = {a: [] for a in pools}
    with open(SNAPS) as f:
        for line in f.readlines()[-40000:]:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("pool") in recent and d["t"] >= cutoff:
                recent[d["pool"]].append(d)
    sol_usdc = sol_price_ref(recent) or 100

    try:
        state = json.load(open(STATE))
    except Exception:
        state = {}

    for addr, meta in pools.items():
        rows = sorted(recent[addr], key=lambda d: d["t"])
        if len(rows) < 3:
            continue
        a, b = rows[0], rows[-1]
        dt_h = (b["t"] - a["t"]) / 3600
        if dt_h <= 0:
            continue
        fs = fees_sol(a, b, meta, sol_usdc)
        if fs is None:
            continue
        lp_fees_h = fs * LP_MULT / dt_h                     # SOL/h LP-capturable
        tvl_usd = meta.get("tvl_usd") or 1
        tvl_sol = tvl_usd / sol_usdc
        fee_rate = lp_fees_h / tvl_sol                      # per-SOL-per-hour
        p_in, p_out = price_of(a), price_of(b)
        if not p_in or not p_out:
            continue
        drift_h = abs(p_out - p_in) / p_in / dt_h           # per hour
        # excursion guard: net drift hides round-trip chop. Use the max
        # deviation from window start seen anywhere in the window.
        exc = max((abs(price_of(r) - p_in) / p_in
                   for r in rows if price_of(r)), default=0.0)
        il_rate = max(drift_h, exc / dt_h) / 2
        ratio = (fee_rate / il_rate) if il_rate > 1e-9 else (
            999.0 if fee_rate > 0 else 0.0)
        name = meta["name"]
        rec = {"t": time.time(), "pool": name, "addr": addr[:8],
               "fee_rate_h": round(fee_rate, 6),
               "il_rate_h": round(il_rate, 6),
               "ratio": round(ratio, 2)}
        with open(OUT, "a") as f:
            f.write(json.dumps(rec) + "\n")

        st = state.setdefault(addr, {"name": name, "streak": 0,
                                     "favorable": False})
        if ratio >= EDGE_MIN:
            st["streak"] += 1
        else:
            st["streak"] = 0
            st["favorable"] = False
        if st["streak"] >= SUSTAIN and not st["favorable"]:
            st["favorable"] = True
            print(f"*** REGIME FAVORABLE: {name} fee_rate {fee_rate:.4%}/h "
                  f"> {EDGE_MIN}x IL rate {il_rate:.4%}/h "
                  f"(sustained {st['streak']} cycles) — LP edge is ON ***")
        print(f"edge: {name:<18} fee {fee_rate*100:7.4f}%/h  "
              f"il {il_rate*100:7.4f}%/h  ratio {ratio:7.2f}  "
              f"{'FAVORABLE' if st['favorable'] else 'off'}")

    json.dump(state, open(STATE, "w"))


if __name__ == "__main__":
    main()
