#!/usr/bin/env python3
"""Backtest: naive buy-at-listing vs. rule-based (PASS + survive kill zone + exit ladder).

Strategy A (naive): buy every Solana listing at detection price, hold to latest.
Strategy B (rule): buy at first history point >= +38 min ONLY IF value >= 80% of
detection value (kill-zone survival filter), any verdict. Exit ladder on the
remaining window: 25% at 2x, 25% at 5x, 25% at 10x of entry, final 25% at last price.
Caveats: coarse 2-4 min mcap sampling (peaks between samples missed), verdicts are
post-backfill (mild lookahead), no fees/slippage. Equal $1 positions.
"""
import json
from datetime import datetime

def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

s = json.load(open("memecoin-monitor/state.json"))
naive, rule = [], []
skipped_young = 0
for k, v in s["seen"].items():
    h = v.get("history") or []
    if len(h) < 5 or v.get("chain") != "solana":
        continue
    p0 = fnum(h[0].get("mcap"))
    if not p0 or p0 <= 0:
        continue
    t0 = datetime.fromisoformat(h[0]["t"])
    pts = []
    for x in h:
        mc = fnum(x.get("mcap"))
        if mc:
            pts.append(((datetime.fromisoformat(x["t"]) - t0).total_seconds() / 60, mc))
    if len(pts) < 5:
        continue
    age = pts[-1][0]
    if age < 38:
        skipped_young += 1
        continue
    # naive: buy at detection, hold
    naive.append(pts[-1][1] / p0)
    # rule: entry at first point >= 38 min if >= 80% of p0
    entry = next(((m, mc) for m, mc in pts if m >= 38), None)
    if not entry:
        continue
    em, emc = entry
    if emc < 0.8 * p0:
        rule.append(1.0)  # no trade, capital preserved
        continue
    after = [mc for m, mc in pts if m >= em]
    peak = max(after)
    final = after[-1]
    ret = 0.0
    for mult, frac in ((2, .25), (5, .25), (10, .25)):
        ret += frac * (mult if peak >= emc * mult else final / emc)
    ret += 0.25 * final / emc
    rule.append(ret)

def report(name, arr):
    n = len(arr)
    if not n:
        print(name, "no data"); return
    total = sum(arr)
    wins = sum(1 for r in arr if r > 1.02)
    big = sum(1 for r in arr if r < 0.5)
    print(f"{name}: n={n} total_return={(total/n-1)*100:+.1f}% per $1  "
          f"winners={wins}  losers>-50%={big}  best={max(arr):.2f}x  worst={min(arr):.2f}x")

print(f"tokens old enough (>=38 min): {len(naive)}, skipped too young: {skipped_young}")
report("A naive buy-all-at-listing", naive)
report("B rule (killzone+ladder) ", rule)
