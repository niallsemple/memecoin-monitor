#!/usr/bin/env python3
"""backtest_lag.py — §431: does the §418/§424 edge survive realistic entry lag?

The backtest enters at the last tick <= t0+60. The live bridge can only fire
when a pass SCORES the coin: pass cadence ~93s + scoring means a real fill
lands ~+90-160s, and observed scored_at lags were 35-967s. This script
re-runs the exact §418 pipeline (same files, same metric definitions as
h16_early2.py) but moves the ENTRY tick later while keeping the QUALIFYING
window at 60s — which is what a live fill would actually get.

Qualification (unchanged, on ticks <= t0+60):
  mom = last/first >= 1.0; dd = min/peak >= 0.90; bf = buys/n >= 0.50;
  >=3 window ticks; liveness: last window tick within final 15s.
Entry: last tick <= t0+LAG for LAG in {60, 90, 120, 150, 180}.
  (A silent coin's price doesn't move without trades, so the last tick <=
  t0+LAG IS the executable price — realistic for an on-chain curve buy.)
Exits (unchanged): +20% bank / -8% panic / 1h timeout, first crossing tick,
  walking ticks AFTER the entry tick. Gross of fees.
"""
import json
from pathlib import Path

MON = Path(__file__).parent
CURVES = MON / "curves.jsonl"
TRADES = MON / "mfg_trades.jsonl"

SEED_LO, SEED_HI = 2.0, 10.0
WINDOW = 60
HORIZON = 3600
UP, DN = 1.20, 0.92
LAGS = [60, 90, 120, 150, 180]
# cap post-entry ticks kept per mint: 1h of ticks is plenty
MAX_TICKS_AGE = HORIZON + 200


def main():
    seeds = {}
    with CURVES.open() as f:
        for ln in f:
            try:
                d = json.loads(ln)
            except Exception:
                continue
            if d.get("txType") == "create" and d.get("mint"):
                s = d.get("solAmount") or 0
                if SEED_LO <= s < SEED_HI and d.get("_ts"):
                    seeds[d["mint"]] = (d["_ts"], s)
    print(f"seeds in band: {len(seeds)}")

    ticks = {}
    with TRADES.open() as f:
        for ln in f:
            try:
                d = json.loads(ln)
            except Exception:
                continue
            m = d.get("mint")
            sd = seeds.get(m)
            if not sd or not d.get("mcap_sol") or not d.get("t"):
                continue
            t0 = sd[0]
            if t0 <= d["t"] <= t0 + MAX_TICKS_AGE:
                ticks.setdefault(m, []).append(
                    (d["t"], d.get("side") or "", d["mcap_sol"]))

    # per-lag tallies
    res = {lag: {"n": 0, "w": 0, "l": 0, "t": 0, "ret": 0.0, "noentry": 0}
           for lag in LAGS}
    qualified = 0
    for m, (t0, seed) in seeds.items():
        ts = sorted(ticks.get(m, []), key=lambda x: x[0])
        if len(ts) < 3:
            continue
        m0 = ts[0][2]
        if not m0:
            continue
        win = [x for x in ts if x[0] <= t0 + WINDOW]
        if len(win) < 3:
            continue
        if win[-1][0] < t0 + WINDOW - 15:   # §424 liveness
            continue
        mom = win[-1][2] / m0
        peak = max(x[2] for x in win)
        dd = min(x[2] for x in win) / peak if peak else 0
        bf = sum(1 for x in win if x[1] == "buy") / len(win)
        if not (mom >= 1.0 and dd >= 0.90 and bf >= 0.50):
            continue
        qualified += 1
        for lag in LAGS:
            elig = [x for x in ts if x[0] <= t0 + lag]
            if not elig:
                res[lag]["noentry"] += 1
                continue
            e_t, _, e_p = elig[-1]
            post = [x for x in ts if x[0] > e_t and x[2] > 0]
            r = None
            for x in post:
                rr = x[2] / e_p
                if rr >= UP:
                    r = UP
                    break
                if rr <= DN:
                    r = DN
                    break
            if r is None:
                if post:
                    r = post[-1][2] / e_p if t0 + HORIZON <= (
                        post[-1][0] if post else t0) else (post[-1][2] / e_p)
                else:
                    r = 1.0
            d = res[lag]
            d["n"] += 1
            d["ret"] += r - 1
            if r >= UP:
                d["w"] += 1
            elif r <= DN:
                d["l"] += 1
            else:
                d["t"] += 1

    print(f"qualified (60s bars + liveness): {qualified}")
    print(f"{'lag':>5} {'n':>5} {'W':>4} {'L':>4} {'T':>4} {'%/trade':>8}")
    for lag in LAGS:
        d = res[lag]
        if d["n"]:
            print(f"{lag:>4}s {d['n']:>5} {d['w']:>4} {d['l']:>4} {d['t']:>4} "
                  f"{100*d['ret']/d['n']:>7.1f}%")


if __name__ == "__main__":
    main()
