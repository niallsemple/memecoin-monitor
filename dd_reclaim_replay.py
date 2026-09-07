#!/usr/bin/env python3
"""§470: dip-reclaim strategy replay on h16 dd-only reject cohort.
RESULT (2026-09-07, 24h, n=48 reclaim entries, seed>=4.0):
  stop(-8%)/timeout(30m): 0% win, avg -11.5% net  -> NO EDGE
  stop(-8%)/TP(+20%):    27% win, avg -3.1% net   -> NO EDGE
The "56% hit +20%" headline was a depressed-baseline artifact: from an
executable reclaim-tick entry, median path is -10%. Idea killed with data.
Rebuild input with the extraction block from REPORT history; this file is
the canonical record of the negative result."""
import json, sys
d = json.load(open("dd_replay_data.json"))
rej, ticks = d["rej"], d["ticks"]
FWD, FEE = 1800, 0.01
res = {"stop_timeout": [], "stop_tp20": []}
for m, info in rej.items():
    if (info.get("seed") or 0) < 4.0: continue
    tk = [x for x in ticks.get(m, []) if info["t"]-5 <= x[0] <= info["t"]+FWD]
    pre = [x for x in ticks.get(m, []) if x[0] <= info["t"]]
    if not pre or len(tk) < 3: continue
    base = pre[-1][1]; dipped = False; entry = None
    for tt, mc in tk:
        if mc < 0.9*base: dipped = True
        if dipped and mc >= base: entry = (tt, mc); break
    if not entry: continue
    et, eP = entry
    post = [x for x in tk if x[0] > et]
    if not post: continue
    xA = post[-1][1]
    for tt, mc in post:
        if mc <= 0.92*eP: xA = mc; break
    res["stop_timeout"].append(xA/eP - 1 - FEE)
    xB = post[-1][1]
    for tt, mc in post:
        if mc <= 0.92*eP: xB = mc; break
        if mc >= 1.20*eP: xB = 1.20*eP; break
    res["stop_tp20"].append(xB/eP - 1 - FEE)
for k, v in res.items():
    if v:
        w = sum(1 for x in v if x > 0)
        print(f"{k}: n={len(v)} win={w/len(v):.0%} avg={sum(v)/len(v):+.1%}")
