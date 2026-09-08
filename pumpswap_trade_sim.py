#!/usr/bin/env python3
"""
pumpswap_trade_sim.py — trade-rule simulator over pumpswap_snapshots.jsonl
(the TRADABLE curves: real venue, real liquidity, real volume).

Tests the owner's strategy family on newborn tokens, worst-case netted:

  MOMENTUM variant: enter when a young pair shows ignition —
      age <= MAX_AGE, liq >= MIN_LIQ, vol_5m/liq >= TURNOVER,
      buys > sells in the last 5m.
  DIP-BUY variant (--dip): same gates, but only enter after price has
      retraced >= DIP_PCT from the pair's running peak (buy the -40% dip
      in a still-liquid, still-trading pool).

  Exits: target +TARGET%, stop -STOP%, trailing stop TRAIL% below the
  post-entry peak, max hold MAX_HOLD_H. Rug override: if liq falls below
  RUG_LIQ_PCT of entry liq, the position is worth RUG_RECOVERY of entry
  (you cannot sell into a drained pool) — exit 'rug'.

  Worst-case costs: SLIP_PCT per side (fee + slippage + priority) applied
  adversely to both entry and exit. 20-min snapshot cadence means intrabar
  moves are unseen — the trailing stop fires at the batch price, and the
  slippage allowance is sized to cover that gap.

Per-pool independent $TRADE_USD books (like meteora_lp_sim), grid over the
entry/exit parameters. Verdict standard: mean net positive with n>=10
across BOTH igniters and duds.

Usage: python3 pumpswap_trade_sim.py [--dip] [--grid]
"""
import json, os, sys
from collections import defaultdict

MON = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(MON, "pumpswap_snapshots.jsonl")

TRADE_USD = 1000.0
MAX_AGE_H = 2.0
MIN_LIQ = 25000.0
TURNOVER = 1.0          # vol_5m >= 1.0x liq in the last 5 min
NEED_BUY_PRESSURE = True
TARGET_PCT = 0.50
STOP_PCT = 0.40
TRAIL_PCT = 0.35
MAX_HOLD_H = 3.0
DIP_PCT = 0.40          # --dip: only enter after -40% from running peak
RUG_LIQ_PCT = 0.30      # liq < 30% of entry liq => rug
RUG_RECOVERY = 0.10     # you salvage 10% in a rug
SLIP_PCT = 0.02         # per side, worst case (fee + slippage + 20min gap)
BATCH_S = 600


def load_series():
    by = defaultdict(list)
    for l in open(SNAP):
        try:
            r = json.loads(l)
        except Exception:
            continue
        if r.get("mint") and r.get("t") and r.get("price"):
            by[r["mint"]].append(r)
    for rows in by.values():
        rows.sort(key=lambda r: r["t"])
    return by


def gates(r, max_age, min_liq, turnover, need_bp):
    if r.get("age_h") is None or r["age_h"] > max_age:
        return False
    liq = r.get("liq") or 0
    if liq < min_liq:
        return False
    if (r.get("vol_5m") or 0) < turnover * liq:
        return False
    if need_bp and (r.get("txns_m5_b") or 0) <= (r.get("txns_m5_s") or 0):
        return False
    return True


def sim_pool(rows, dip, max_age, min_liq, turnover, need_bp,
             target, stop, trail, max_hold_h):
    """One position per pool max. Returns trade dict or None."""
    peak_seen = 0.0
    pos = None
    for r in rows:
        px = r["price"]
        peak_seen = max(peak_seen, px)
        if pos is None:
            if dip and peak_seen > 0 and px > peak_seen * (1 - DIP_PCT):
                continue  # not dipped enough yet
            if not gates(r, max_age, min_liq, turnover, need_bp):
                continue
            pos = {"entry": r, "p0": px * (1 + SLIP_PCT), "peak": px,
                   "entry_liq": r.get("liq") or 0}
            continue
        # manage
        pos["peak"] = max(pos["peak"], px)
        r_now = px / pos["p0"]
        held_h = (r["t"] - pos["entry"]["t"]) / 3600
        liq = r.get("liq") or 0
        reason, ret = None, r_now * (1 - SLIP_PCT)
        if pos["entry_liq"] > 0 and liq < pos["entry_liq"] * RUG_LIQ_PCT:
            reason, ret = "rug", RUG_RECOVERY
        elif r_now - 1 >= target:
            reason = "target"
        elif 1 - r_now >= stop:
            reason = "stop"
        elif pos["peak"] > pos["p0"] and px <= pos["peak"] * (1 - trail):
            reason = "trail"
        elif held_h >= max_hold_h:
            reason = "max_hold"
        if reason:
            hold_h = (r["t"] - pos["entry"]["t"]) / 3600
            return {"name": pos["entry"].get("name"), "mint": pos["entry"]["mint"],
                    "entry_t": pos["entry"]["t"], "hold_h": round(hold_h, 2),
                    "exit": reason, "ret": round(ret, 3),
                    "net": round(TRADE_USD * (ret - 1), 2),
                    "entry_age": pos["entry"].get("age_h"),
                    "entry_liq": pos["entry_liq"]}
    if pos:  # data_end close at last price
        last = rows[-1]
        ret = last["price"] / pos["p0"] * (1 - SLIP_PCT)
        hold_h = (last["t"] - pos["entry"]["t"]) / 3600
        return {"name": pos["entry"].get("name"), "mint": pos["entry"]["mint"],
                "entry_t": pos["entry"]["t"], "hold_h": round(hold_h, 2),
                "exit": "data_end", "ret": round(ret, 3),
                "net": round(TRADE_USD * (ret - 1), 2),
                "entry_age": pos["entry"].get("age_h"),
                "entry_liq": pos["entry_liq"]}
    return None


def summarize(trades):
    if not trades:
        return "n=0"
    n = len(trades)
    tot = sum(t["net"] for t in trades)
    pos = sum(1 for t in trades if t["net"] > 0)
    rugs = sum(1 for t in trades if t["exit"] == "rug")
    return (f"n={n} total={tot:+.0f} mean={tot / n:+.1f} "
            f"pos={pos}/{n} rugs={rugs}")


def run(by, dip, **kw):
    trades = []
    for mint, rows in by.items():
        if len(rows) < 2:
            continue
        t = sim_pool(rows, dip, **kw)
        if t:
            trades.append(t)
    return trades


def main():
    dip = "--dip" in sys.argv
    if not os.path.exists(SNAP):
        print("no pumpswap snapshots yet")
        return
    by = load_series()
    print(f"pools with 2+ snapshots: {sum(1 for r in by.values() if len(r) >= 2)}")

    if "--grid" in sys.argv:
        print(f"{'variant':<9}" + "grid (mean net per $1000, worst-case):")
        for age in (0.5, 1.0, 2.0):
            for hold in (0.5, 1.0, 3.0):
                for tgt in (0.25, 0.50):
                    tr = run(by, dip, max_age=age, max_hold_h=hold, target=tgt,
                             min_liq=MIN_LIQ, turnover=TURNOVER,
                             need_bp=NEED_BUY_PRESSURE,
                             stop=STOP_PCT, trail=TRAIL_PCT)
                    print(f"age<={age:3.1f}h hold<={hold:3.1f}h "
                          f"tgt=+{int(tgt * 100)}%  " + summarize(tr))
        return

    tr = run(by, dip, max_age=MAX_AGE_H, min_liq=MIN_LIQ, turnover=TURNOVER,
             need_bp=NEED_BUY_PRESSURE, target=TARGET_PCT, stop=STOP_PCT,
             trail=TRAIL_PCT, max_hold_h=MAX_HOLD_H)
    print(f"{'DIP-BUY' if dip else 'MOMENTUM'} trades: {len(tr)}")
    for t in sorted(tr, key=lambda x: x["entry_t"]):
        print(f"  {(t['name'] or '?')[:20]:<22} entry_age={t['entry_age']}h "
              f"liq=${(t['entry_liq'] or 0):>9,.0f} hold={t['hold_h']:5.2f}h "
              f"ret={t['ret']:6.3f} net={t['net']:8.2f} ({t['exit']})")
    print("\n" + summarize(tr))
    from collections import Counter
    print("exits:", Counter(t["exit"] for t in tr))


if __name__ == "__main__":
    main()
