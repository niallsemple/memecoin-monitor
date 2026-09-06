#!/usr/bin/env python3
"""H13 — first-passage formulation on the curve tape.
Question: is P(+20% before -8%) a better prediction target than raw return?
Method: for every mint's curve phase in mfg_trades.jsonl, at each candidate
entry delay (1,3,5,10 min after first tick), walk the mcap path and record
which barrier (+20% / -8% from entry) is hit first, plus path to +60m.
Then: (a) base rates by entry delay; (b) does hitting +20% first predict
+60m outcome? (c) does the tape support abort-style exits (hit -8% first =>
final outcome distribution)?
Farm seeds excluded.
"""
import json
import pandas as pd
import numpy as np
from pathlib import Path

MON = Path(__file__).parent
UP, DN = 1.20, 0.92

farm = set()
for line in open(MON / "mfg_tokens.jsonl"):
    try:
        d = json.loads(line)
    except Exception:
        continue
    if (d.get("seed") or 0) >= 50 and d.get("mint"):
        farm.add(d["mint"])

rows = []
with open(MON / "mfg_trades.jsonl") as f:
    for line in f:
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("venue") == "curve" and d.get("mcap_sol"):
            rows.append((d["t"], d["mint"], d["mcap_sol"]))
df = pd.DataFrame(rows, columns=["t", "mint", "mcap"])
print("curve ticks:", len(df), "mints:", df.mint.nunique())

def passage(g, entry_t, horizon=3600):
    e = g[g.t >= entry_t]
    if len(e) < 3:
        return None
    p0 = e.mcap.iloc[0]
    if p0 <= 0:
        return None
    path = e[e.t <= entry_t + horizon].mcap.values / p0
    up_i = np.argmax(path >= UP)
    dn_i = np.argmax(path <= DN)
    hit_up = path[up_i] >= UP if (path >= UP).any() else False
    hit_dn = path[dn_i] <= DN if (path <= DN).any() else False
    if hit_up and hit_dn:
        first = "up" if up_i < dn_i else "dn"
    elif hit_up:
        first = "up"
    elif hit_dn:
        first = "dn"
    else:
        first = "none"
    # outcome: mcap at end of horizon (or last tick), and max excursion after first-up
    end = path[-1]
    mfe = path.max()
    if first == "up":
        post = path[up_i:]
        mae_after_up = post.min()
    else:
        mae_after_up = np.nan
    return dict(barrier=first, end=end, mfe=mfe, mae_after_up=mae_after_up)

results = []
for mint, g in df.groupby("mint"):
    if mint in farm:
        continue
    g = g.sort_values("t")
    t0 = g.t.iloc[0]
    for delay in (60, 180, 300, 600):
        r = passage(g, t0 + delay)
        if r:
            results.append(dict(mint=mint, delay=delay, **r))

ev = pd.DataFrame(results)
ev.to_json(MON / "first_passage.json", orient="records")
print("passage obs:", len(ev))

for delay in (60, 180, 300, 600):
    s = ev[ev.delay == delay]
    if len(s) < 30:
        continue
    rates = s.barrier.value_counts(normalize=True) * 100
    print(f"\nentry +{delay//60}m (n={len(s)}): up-first {rates.get('up',0):.0f}%  dn-first {rates.get('dn',0):.0f}%  neither {rates.get('none',0):.0f}%")
    for grp, name in (("up", "hit +20% first"), ("dn", "hit -8% first"), ("none", "neither")):
        sub = s[s.barrier == grp]
        if len(sub) > 10:
            print(f"  {name}: n={len(sub)} median end={sub.end.median():.2f}x  median MFE={sub.mfe.median():.2f}x")
    ups = s[s.barrier == "up"]
    if len(ups) > 10:
        held = ups.mae_after_up.dropna()
        print(f"  after hitting +20% first: median worst dip afterwards = {held.median():.2f}x of entry; "
              f"{100*(held < 0.92).mean():.0f}% later round-trip below -8%")
