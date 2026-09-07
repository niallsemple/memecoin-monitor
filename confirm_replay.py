#!/usr/bin/env python3
"""§473: confirmation-entry replay over 72h of h16e2 qualifiers (n=55).
VERDICT (2026-09-07): NO EDGE in birth-momentum long, any entry variant.
  organic stop/timeout:   n=55 win=5%  avg -19.2%
  confirm  stop/timeout:  n=33 win=3%  avg -19.6%  (confirm skips 40% of flow)
  confirm  stop+TP20:     n=33 win=18% avg -12.6%
  seed 8-10 subcohort:    n=3  win=67% avg +12.6%  (TOO THIN - shadow only)
Confirms §470 dip-reclaim negative. Only gates (+0.094 SOL saved) and the
liquidation fronts carry demonstrable edge. Live confirm mode stays armed
to keep collecting forward data, but sizing stays minimal.
Replay: python3 confirm_replay.py (needs confirm_replay.json, rebuilt by
the extraction heredoc in conversation 2026-09-07)."""
import json
d = json.load(open("confirm_replay.json"))
opens, ticks = d["opens"], d["ticks"]
FEE, CMIN, CMAX = 0.01, 45, 150
org, con = [], []
for m, info in opens.items():
    t0, em = info["t"], info["entry_mcap"]
    if not em: continue
    win = sorted(x for x in ticks[m] if t0 < x[0] <= t0+1800)
    if not win: continue
    x = win[-1][1]
    for tt, mc in win:
        if mc <= 0.92*em: x = mc; break
    org.append(x/em - 1 - FEE)
    buy = None
    for tt, mc in win:
        ag = tt - t0
        if ag < CMIN: continue
        if ag > CMAX: break
        if mc >= em: buy = (tt, mc); break
    if not buy: continue
    bt, bP = buy
    post = [x for x in win if x[0] > bt]
    if not post: continue
    x = post[-1][1]
    for tt, mc in post:
        if mc <= 0.92*bP: x = mc; break
    con.append(x/bP - 1 - FEE)
for name, v in (("organic", org), ("confirm", con)):
    if v:
        w = sum(1 for x in v if x > 0)
        print(f"{name}: n={len(v)} win={w/len(v):.0%} avg={sum(v)/len(v):+.1%}")
