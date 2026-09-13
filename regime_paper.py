#!/usr/bin/env python3
"""regime_paper.py — forward paper-trading of the flat-harvest rule.

Backtest (FINDINGS.md 2026-09-13) says the paying condition is fee bursts
while price is FLAT (regime_edge ratio >= EDGE_MIN). Grid test: positive for
all 15 EDGE_MIN x SUSTAIN combos; SUSTAIN 2-3 beats first-detection entry.
This validates forward on live data, no real SOL, and runs TWO books in
parallel to settle entry timing empirically:

  book s1: open on FIRST favorable snapshot      (max trade count)
  book s2: open on 2nd consecutive favorable     (grid sweet spot)

  CLOSE (both): ratio < EDGE_MIN at a later snapshot, or MAX_AGE_S
  P&L  : fees = protocol fee delta * LP_MULT * share (share capped 5%)
         IL = |drift|/2 * size ; minus FIXED. Per-size nets 0.05/0.5/1.0.

Evaluates EVERY bin snapshot (~30s cadence) — paying windows last 1-5 min.
Runs one-shot per poll cycle after regime_edge.py.
State: regime_paper_state.json ; closed trades: regime_paper.jsonl
"""
import json, os, sys, time

BASE = os.path.dirname(os.path.abspath(__file__))
SNAPS = os.path.join(BASE, "bin_snapshots.jsonl")
POOLS = os.path.join(BASE, "capacity_pools.json")
STATE = os.path.join(BASE, "regime_paper_state.json")
TRADES = os.path.join(BASE, "regime_paper.jsonl")

EDGE_MIN = 1.5
BOOKS = {"s1": 1, "s2": 2}        # book -> streak required to enter
SIZES = (0.05, 0.5, 1.0)
FIXED = 0.0002
LP_MULT = 9.0
MAX_AGE_S = 900
SHARE_CAP = 0.05
LOOKBACK_S = 3600
HIST_LOAD_S = 3 * 3600

sys.path.insert(0, BASE)
from capacity_watch import fees_sol, sol_price_ref, STABLES  # noqa: E402


def price_of(d):
    return next((bn["price"] for bn in d.get("bins", [])
                 if bn["binId"] == d["active_bin"]), None)


def ratio_at(rows, i, meta, tvl_sol, sol_usdc):
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


def close_rec(book, addr, meta, pos, snap, r, sol_usdc):
    a, b = pos["snap"], snap
    age = b["t"] - pos["t"]
    try:
        fs = (fees_sol(a, b, meta, sol_usdc) or 0) * LP_MULT
    except (KeyError, TypeError):
        fs = 0.0
    liq_act = float(b.get("liq_active") or 0)
    p_in, p_out = price_of(a), price_of(b)
    drift = abs(p_out - p_in) / p_in if p_in and p_out else 0
    nets = {}
    for size in SIZES:
        our_raw = (size * 1e9 if meta["y_sym"] == "SOL"
                   else size * sol_usdc * 10 ** meta["y_dec"])
        share = min(our_raw / liq_act, SHARE_CAP) if liq_act > 0 else 0
        nets[str(size)] = round(fs * share - drift / 2 * size - FIXED, 6)
    return {"t": b["t"], "book": book, "pool": meta["name"],
            "addr": addr[:8], "age_s": round(age),
            "ratio_in": round(pos["ratio_in"], 1), "nets": nets,
            "exit": "ratio_break" if (r is not None and r < EDGE_MIN)
                    else "max_age"}


def main():
    pools = {p["addr"]: p for p in json.load(open(POOLS))["pools"]}
    try:
        state = json.load(open(STATE))
    except Exception:
        state = {}
    state.setdefault("last_t", {})
    state.setdefault("streak", {})
    for bk in BOOKS:
        b = state.setdefault(bk, {})
        b.setdefault("open", {})
        b.setdefault("closed", 0)
        b.setdefault("net", {str(s): 0.0 for s in SIZES})

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
            state["last_t"][addr] = rows[-1]["t"]   # forward-only: no replay
        last_t = state["last_t"][addr]
        streak = state["streak"].get(addr, 0)

        for i, snap in enumerate(rows):
            if snap["t"] <= last_t:
                continue
            r = ratio_at(rows, i, meta, tvl_sol, sol_usdc)
            if r is None:
                continue
            streak = streak + 1 if r >= EDGE_MIN else 0
            for bk, need in BOOKS.items():
                book = state[bk]
                pos = book["open"].get(addr)
                if pos is None:
                    if streak >= need:
                        book["open"][addr] = {"t": snap["t"], "snap": snap,
                                              "ratio_in": r}
                        print(f"paper OPEN[{bk}] {meta['name']} "
                              f"{time.strftime('%H:%M:%S', time.localtime(snap['t']))}"
                              f" ratio {r:.1f} streak {streak}")
                else:
                    age = snap["t"] - pos["t"]
                    if r < EDGE_MIN or age > MAX_AGE_S:
                        rec = close_rec(bk, addr, meta, pos, snap, r, sol_usdc)
                        with open(TRADES, "a") as f:
                            f.write(json.dumps(rec) + "\n")
                        book["closed"] += 1
                        for k, v in rec["nets"].items():
                            book["net"][k] = round(book["net"][k] + v, 6)
                        del book["open"][addr]
                        print(f"paper CLOSE[{bk}] {meta['name']} "
                              f"age {rec['age_s']}s nets {rec['nets']} "
                              f"| cum {book['net']} over {book['closed']}")
        state["streak"][addr] = streak
        state["last_t"][addr] = rows[-1]["t"]

    json.dump(state, open(STATE, "w"))


if __name__ == "__main__":
    main()
