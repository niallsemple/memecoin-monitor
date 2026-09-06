#!/usr/bin/env python3
"""H14 v2 — graduation event study at trade resolution.
Source: mfg_trades.jsonl (t, mint, venue[curve|pool], side, sol, mcap_sol).
Event = venue switch curve -> pool (graduation). For each mint:
  pre features (curve phase): duration, total buy/sell SOL, last-5-min buy SOL,
    trade count, mcap at migration, drawdown into migration (last/first-5m mcap)
  outcomes (pool phase): mcap at +5/+15/+60m vs migration mcap
Then: distribution + feature discrimination of runners (>=2x @+60m) vs rest.
"""
import json, collections
import pandas as pd
import numpy as np
from pathlib import Path

MON = Path(__file__).parent
FARM_SEED = 50.0

# farm mints to exclude (seed>=50) from mfg_tokens.jsonl
farm = set()
for line in open(MON / "mfg_tokens.jsonl"):
    try:
        d = json.loads(line)
    except Exception:
        continue
    if (d.get("seed") or 0) >= FARM_SEED and d.get("mint"):
        farm.add(d["mint"])
print("farm mints:", len(farm))

rows = []
with open(MON / "mfg_trades.jsonl") as f:
    for line in f:
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("venue") in ("curve", "pool") and d.get("mcap_sol"):
            rows.append((d["t"], d["mint"], d["venue"], d.get("side") or "", d.get("sol") or 0.0, d["mcap_sol"]))
df = pd.DataFrame(rows, columns=["t", "mint", "venue", "side", "sol", "mcap"])
print("ticks:", len(df), "mints:", df.mint.nunique())

events = []
for mint, g in df.groupby("mint"):
    if mint in farm:
        continue
    g = g.sort_values("t")
    venues = g.venue.values
    # first pool tick = graduation moment
    pi = np.argmax(venues == "pool")
    if venues[pi] != "pool":
        continue  # never graduated in tape
    t0 = g.t.values[pi]
    curve = g[g.t < t0]
    pool = g[g.t >= t0]
    if len(curve) < 3 or len(pool) < 2:
        continue
    m_mig = pool.mcap.iloc[0]
    if not m_mig or m_mig <= 0:
        continue
    dur = t0 - curve.t.iloc[0]
    l5 = curve[curve.t >= t0 - 300]
    l5_buy = l5[l5.side == "buy"].sol.sum()
    tot_buy = curve[curve.side == "buy"].sol.sum()
    tot_sell = curve[curve.side == "sell"].sol.sum()
    m_first = curve.mcap.iloc[0]
    m_last = curve.mcap.iloc[-1]
    out = {}
    for lbl, dt in (("p5", 300), ("p15", 900), ("p60", 3600)):
        tgt = t0 + dt
        w = pool[(pool.t >= tgt - 210) & (pool.t <= tgt + 210)]
        if len(w):
            out[lbl] = w.mcap.iloc[-1] / m_mig
    events.append(dict(mint=mint, t0=t0, dur_s=dur, l5_buy=l5_buy,
                       tot_buy=tot_buy, tot_sell=tot_sell,
                       n_curve_trades=len(curve), m_mig=m_mig,
                       pre_mult=(m_last / m_first) if m_first else np.nan, **out))

ev = pd.DataFrame(events)
ev.to_json(MON / "grad_event_study_v2.json", orient="records")
print("graduation events (non-farm, trade-res):", len(ev))

for lbl in ("p5", "p15", "p60"):
    v = ev[lbl].dropna()
    if len(v) < 10:
        print(lbl, "n too small:", len(v)); continue
    print(f"{lbl}: n={len(v)} median={v.median():.2f}x mean={v.mean():.2f}x "
          f"runners(>=2x)={100*(v>=2).mean():.0f}% husks(<=0.5x)={100*(v<=0.5).mean():.0f}%")

# discrimination on +60m
e60 = ev.dropna(subset=["p60"])
if len(e60) >= 30:
    e60 = e60.copy()
    e60["runner"] = e60.p60 >= 2.0
    print("\n+60m outcome base rate: runners", round(100*e60.runner.mean()), "% of", len(e60))
    for feat in ("l5_buy", "dur_s", "pre_mult", "tot_buy", "n_curve_trades"):
        q = e60[feat].quantile([.33, .67]).values
        hi = e60[e60[feat] >= q[1]]; lo = e60[e60[feat] < q[0]]
        if len(hi) > 5 and len(lo) > 5:
            print(f"  {feat}: top3rd runners={100*hi.runner.mean():.0f}% (med {hi[feat].median():.3g}) "
                  f"vs bot3rd runners={100*lo.runner.mean():.0f}% (med {lo[feat].median():.3g}) "
                  f"| med ret hi={hi.p60.median():.2f}x lo={lo.p60.median():.2f}x")
