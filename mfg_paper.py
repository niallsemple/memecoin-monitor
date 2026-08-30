#!/usr/bin/env python3
"""mfg_paper.py — forward paper-trade validator for MFG runner alerts (§56d).

Answers the only question that matters before real money: if we had BOUGHT
every runner alert at alert time, what happened next?

Joins mfg_alerts.jsonl (entry: alert-time pool_mcap / pool_liq_sol) to later
mfg_tokens.jsonl snapshots of the same mint and to current mfg_state.json:
  - forward return at +1h/+4h/+12h/+24h after alert (pool_mcap ratio)
  - liquidity path (drain detection: min liq after alert vs alert liq)
  - simulated exit rule: EXIT when pool liq falls below 30% of post-alert peak
    (uses snapshot sequence; coarse — snapshots are point-in-time)

Caveats printed with output: pool_mcap is marginal price; fills at alert
price are optimistic; snapshot granularity understates intraday whipsaw.

Usage: python3 mfg_paper.py
"""
import json
import time
from pathlib import Path

MON = Path("/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor")
ALERTS = MON / "mfg_alerts.jsonl"
SNAPS = MON / "mfg_tokens.jsonl"
STATE = MON / "mfg_state.json"
EXIT_LIQ_FRAC = 0.30   # simulated stop: exit when liq < 30% of post-alert peak


def main():
    alerts = [json.loads(l) for l in ALERTS.read_text().splitlines()] if ALERTS.exists() else []
    snaps = {}
    if SNAPS.exists():
        for l in SNAPS.read_text().splitlines():
            try:
                r = json.loads(l)
            except Exception:
                continue
            snaps.setdefault(r.get("mint"), []).append(r)
    for v in snaps.values():
        v.sort(key=lambda r: r["t"])
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    now = time.time()

    print(f"MFG paper-trade validator — {len(alerts)} alerts\n")
    rows = []
    for a in alerts:
        mint = a["mint"]
        t0, mc0, liq0 = a["t"], a.get("pool_mcap"), a.get("pool_liq_sol")
        if not mc0 or not liq0:
            continue
        # forward path from snapshots taken after the alert
        path = [r for r in snaps.get(mint, []) if r["t"] > t0
                and r.get("pool_mcap_sol") is not None]
        # current live state as the final point
        cur = state.get(mint, {})
        pts = [(r["t"], r.get("pool_mcap_sol"), r.get("pool_liq_sol")) for r in path]
        if cur.get("pool_mcap") is not None:
            pts.append((now, cur.get("pool_mcap"), cur.get("pool_liq_sol")))
        rets = {}
        for h in (1, 4, 12, 24):
            cand = [p for p in pts if p[0] >= t0 + h * 3600 - 600]
            if cand:
                rets[h] = (cand[0][1] / mc0 - 1) * 100
        # simulated liq-stop exit
        peak = liq0
        exit_ret = None
        for ts, mc, liq in pts:
            if liq is None or mc is None:
                continue
            peak = max(peak, liq)
            if liq < EXIT_LIQ_FRAC * peak:
                exit_ret = (mc / mc0 - 1) * 100
                break
        latest_ret = (pts[-1][1] / mc0 - 1) * 100 if pts and pts[-1][1] else None
        rows.append({"sym": a.get("symbol") or mint[:8], "age_m": (now - t0) / 60,
                     "liq0": liq0, "rets": rets, "stop_ret": exit_ret,
                     "latest": latest_ret,
                     "liq_now": pts[-1][2] if pts else None})

    print(f"{'token':<10}{'age':>7}{'liq@entry':>10}{'+1h':>9}{'+4h':>9}"
          f"{'+12h':>9}{'+24h':>9}{'stop-exit':>11}{'latest':>10}")
    for r in rows:
        def f(h):
            v = r["rets"].get(h)
            return f"{v:+.0f}%" if v is not None else "—"
        stp = f"{r['stop_ret']:+.0f}%" if r["stop_ret"] is not None else "open"
        lat = f"{r['latest']:+.0f}%" if r["latest"] is not None else "—"
        print(f"{r['sym']:<10}{r['age_m']:>5.0f}m{r['liq0']:>10.1f}"
              f"{f(1):>9}{f(4):>9}{f(12):>9}{f(24):>9}{stp:>11}{lat:>10}")

    # expectancy on matured alerts (latest return known and age >= 1h)
    done = [r for r in rows if r["latest"] is not None and r["age_m"] >= 60]
    if done:
        exp = sum(r["latest"] for r in done) / len(done)
        wins = sum(1 for r in done if r["latest"] > 0)
        print(f"\nmatured alerts (>=1h): {len(done)} | win rate {wins}/{len(done)} "
              f"| mean fwd return {exp:+.1f}%")
        stopped = [r for r in done if r["stop_ret"] is not None]
        if stopped:
            sexp = sum(r["stop_ret"] for r in stopped) / len(stopped)
            print(f"stop-rule exits: {len(stopped)} | mean stop-exit return {sexp:+.1f}%")
    print("\ncaveats: pool_mcap = marginal price x supply (inflated on thin pools);")
    print("alert-price fills are optimistic; snapshots understate intraday whipsaw;")
    print("tiny sample — directional only until n >= 30.")


if __name__ == "__main__":
    main()
