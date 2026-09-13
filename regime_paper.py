#!/usr/bin/env python3
"""regime_paper.py — forward paper-trading of the flat-harvest rule.

Backtest (FINDINGS.md 2026-09-13) says the paying condition is fee bursts
while price is FLAT (regime_edge ratio >= 1.5, esp. ratio~999). This validates
that forward on live data, no real SOL.

IMPORTANT: evaluates EVERY bin snapshot (~30s cadence), not just poll-cycle
instants — paying windows last 1-5 min and a 4-min sampling cadence would
structurally miss them (that would make a negative result uninterpretable).

  OPEN  : trailing-1h ratio >= EDGE_MIN at a snapshot, no open paper position
  CLOSE : ratio < EDGE_MIN at a later snapshot, or MAX_AGE_S exceeded
  P&L   : fees = protocol fee delta (entry->exit snapshot) * LP_MULT * share
          share = size in Y raw / liq_active, capped at 5% (artifact guard)
          IL    = |price drift|/2 * size ;  minus FIXED probe overhead

Runs one-shot per poll cycle (after regime_edge.py in _poll_loop.sh),
processing all snapshots since the previous run.
State: regime_paper_state.json ; closed trades: regime_paper.jsonl
"""
import json, os, sys, time

BASE = os.path.dirname(os.path.abspath(__file__))
SNAPS = os.path.join(BASE, "bin_snapshots.jsonl")
POOLS = os.path.join(BASE, "capacity_pools.json")
STATE = os.path.join(BASE, "regime_paper_state.json")
TRADES = os.path.join(BASE, "regime_paper.jsonl")

EDGE_MIN = 1.5
SIZES = (0.05, 0.5, 1.0)   # parallel virtual sizes — learn scaling before risking
FIXED = 0.0002
LP_MULT = 9.0
MAX_AGE_S = 900
SHARE_CAP = 0.05
LOOKBACK_S = 3600
HIST_LOAD_S = 3 * 3600   # trailing data needed for ratios + backlog

sys.path.insert(0, BASE)
from capacity_watch import fees_sol, sol_price_ref, STABLES  # noqa: E402


def price_of(d):
    return next((bn["price"] for bn in d.get("bins", [])
                 if bn["binId"] == d["active_bin"]), None)


def ratio_at(rows, i, meta, tvl_sol, sol_usdc):
    """regime_edge ratio at rows[i] using trailing 1h window."""
    b = rows[i]
    lo = b["t"] - LOOKBACK_S
    j = i
    while j > 0 and rows[j - 1]["t"] >= lo:
        j -= 1
    a = rows[j]
    dt_h = (b["t"] - a["t"]) / 3600
    if dt_h < 0.25:
        return None
    try:
        fs = fees_sol(a, b, meta, sol_usdc)
    except (KeyError, TypeError):
        return None
    p_in, p_out = price_of(a), price_of(b)
    if fs is None or not p_in or not p_out:
        return None
    fee_rate = fs * LP_MULT / dt_h / tvl_sol
    il_rate = abs(p_out - p_in) / p_in / dt_h / 2
    return fee_rate / il_rate if il_rate > 1e-9 else (999.0 if fee_rate > 0
                                                      else 0.0)


def main():
    pools = {p["addr"]: p for p in json.load(open(POOLS))["pools"]}
    try:
        state = json.load(open(STATE))
    except Exception:
        state = {"open": {}, "closed": 0, "last_t": {}}
    state.setdefault("last_t", {})
    if not isinstance(state.get("net"), dict):
        state["net"] = {str(s): 0.0 for s in SIZES}   # v3: per-size ledgers

    cutoff = time.time() - HIST_LOAD_S
    series = {a: [] for a in pools}
    with open(SNAPS) as f:
        for line in f.readlines()[-30000:]:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("pool") in series and d["t"] >= cutoff:
                series[d["pool"]].append(d)
    sol_usdc = sol_price_ref(series) or 100

    for addr, meta in pools.items():
        rows = sorted(series[addr], key=lambda d: d["t"])
        if len(rows) < 10:
            continue
        tvl_sol = (meta.get("tvl_usd") or 1) / sol_usdc
        if addr not in state["last_t"]:
            # first sight of this pool: start from NOW — no backlog replay,
            # ledger must be purely forward-looking
            state["last_t"][addr] = rows[-1]["t"]
        last_t = state["last_t"][addr]
        pos = state["open"].get(addr)

        for i, snap in enumerate(rows):
            if snap["t"] <= last_t:
                continue
            r = ratio_at(rows, i, meta, tvl_sol, sol_usdc)
            if pos is None:
                if r is not None and r >= EDGE_MIN:
                    pos = {"t": snap["t"], "snap": snap, "ratio_in": r}
                    state["open"][addr] = pos
                    print(f"paper OPEN {meta['name']} "
                          f"{time.strftime('%H:%M:%S', time.localtime(snap['t']))}"
                          f" ratio {r:.1f}")
            else:
                age = snap["t"] - pos["t"]
                broken = r is not None and r < EDGE_MIN
                if broken or age > MAX_AGE_S:
                    a, b = pos["snap"], snap
                    try:
                        fs = (fees_sol(a, b, meta, sol_usdc) or 0) * LP_MULT
                    except (KeyError, TypeError):
                        fs = 0.0
                    liq_act = float(b.get("liq_active") or 0)
                    p_in, p_out = price_of(a), price_of(b)
                    drift = (abs(p_out - p_in) / p_in
                             if p_in and p_out else 0)
                    nets = {}
                    for size in SIZES:
                        if meta["y_sym"] == "SOL":
                            our_raw = size * 1e9
                        else:
                            our_raw = size * sol_usdc * 10 ** meta["y_dec"]
                        share = (min(our_raw / liq_act, SHARE_CAP)
                                 if liq_act > 0 else 0)
                        fees = fs * share
                        il = drift / 2 * size
                        nets[str(size)] = round(fees - il - FIXED, 6)
                    net = nets[str(SIZES[0])]
                    rec = {"t": b["t"], "pool": meta["name"],
                           "addr": addr[:8], "age_s": round(age),
                           "ratio_in": round(pos["ratio_in"], 1),
                           "nets": nets,
                           "exit": "ratio_break" if broken else "max_age"}
                    with open(TRADES, "a") as f:
                        f.write(json.dumps(rec) + "\n")
                    state["closed"] += 1
                    for k, v in nets.items():
                        state["net"][k] = round(state["net"][k] + v, 6)
                    pos = None
                    del state["open"][addr]
                    print(f"paper CLOSE {meta['name']} age {age:.0f}s "
                          f"nets {nets} | cum {state['net']} "
                          f"over {state['closed']}")
        state["last_t"][addr] = rows[-1]["t"]

    json.dump(state, open(STATE, "w"))


if __name__ == "__main__":
    main()
