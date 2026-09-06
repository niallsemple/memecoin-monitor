#!/usr/bin/env python3
"""H16 — feature hunt: which organic big-seed (2-10 SOL) curve coins pop?
Cohort: mfg_trades.jsonl venue=curve mints with create seed 2-10 SOL.
Label: up-first = mcap hits +20% before -8% from entry at birth+180s,
horizon 1h (same definition as first_passage.py).
Features observable by entry time (+180s): early momentum m1/m2, trade counts,
buy fraction, buy-sol concentration, first-2m drawdown, seed size.
Output: base rate + lift per feature tercile/quintile.
"""
import json
import pandas as pd
import numpy as np
from pathlib import Path

MON = Path(__file__).parent
UP, DN = 1.20, 0.92
ENTRY_DELAY = 180
HORIZON = 3600

# seeds from create events
seed = {}
for line in open(MON / "curves.jsonl"):
    try:
        d = json.loads(line)
    except Exception:
        continue
    if d.get("txType") == "create" and d.get("mint"):
        seed[d["mint"]] = d.get("solAmount") or 0

rows = []
with open(MON / "mfg_trades.jsonl") as f:
    for line in f:
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("venue") == "curve" and d.get("mcap_sol"):
            m = d["mint"]
            s = seed.get(m)
            if s is not None and 2 <= s < 10:
                rows.append((d["t"], m, d.get("side") or "", d.get("sol") or 0.0, d["mcap_sol"]))
df = pd.DataFrame(rows, columns=["t", "mint", "side", "sol", "mcap"])
print("cohort ticks:", len(df), "mints:", df.mint.nunique())

recs = []
for mint, g in df.groupby("mint"):
    g = g.sort_values("t")
    t0 = g.t.iloc[0]
    pre = g[g.t <= t0 + ENTRY_DELAY]
    post = g[(g.t > t0 + ENTRY_DELAY) & (g.t <= t0 + ENTRY_DELAY + HORIZON)]
    if len(pre) < 3 or len(post) < 3:
        continue
    p0 = post.mcap.iloc[0]
    if p0 <= 0:
        continue
    path = post.mcap.values / p0
    up = path >= UP
    dn = path <= DN
    if up.any() and dn.any():
        lbl = "up" if np.argmax(up) < np.argmax(dn) else "dn"
    elif up.any():
        lbl = "up"
    elif dn.any():
        lbl = "dn"
    else:
        lbl = "none"
    pb = pre[pre.side == "buy"]
    m0 = pre.mcap.iloc[0]
    feat = dict(
        mint=mint, seed=seed[mint], label=lbl,
        n_pre=len(pre),
        buyfrac=len(pb) / len(pre),
        buysol=pb.sol.sum(),
        maxbuy=pb.sol.max() if len(pb) else 0.0,
        mom=(pre.mcap.iloc[-1] / m0) if m0 else np.nan,
        dd=(pre.mcap.min() / pre.mcap.max()) if pre.mcap.max() else np.nan,
    )
    recs.append(feat)

ev = pd.DataFrame(recs)
ev.to_json(MON / "h16_cohort.json", orient="records")
n = len(ev)
base = (ev.label == "up").mean()
print(f"cohort n={n}  base up-first rate: {100*base:.1f}%  "
      f"dn {100*(ev.label=='dn').mean():.0f}%  neither {100*(ev.label=='none').mean():.0f}%")

print("\nfeature lift (top tercile vs bottom tercile, label=up-first):")
for f in ("n_pre", "buyfrac", "buysol", "maxbuy", "mom", "dd", "seed"):
    q = ev[f].quantile([1/3, 2/3]).values
    hi = ev[ev[f] >= q[1]]
    lo = ev[ev[f] < q[0]]
    if len(hi) > 10 and len(lo) > 10:
        print(f"  {f:8s} top: {100*(hi.label=='up').mean():5.1f}% (med {hi[f].median():.4g})  "
              f"bot: {100*(lo.label=='up').mean():5.1f}% (med {lo[f].median():.4g})  "
              f"lift {((hi.label=='up').mean()+1e-9)/((lo.label=='up').mean()+1e-9):.2f}x")

# best combo: momentum + no-drawdown
combo = ev[(ev.mom >= ev.mom.quantile(2/3)) & (ev.dd >= ev.dd.quantile(2/3))]
if len(combo) > 10:
    print(f"\ncombo high-mom + shallow-dd: n={len(combo)} up-first {100*(combo.label=='up').mean():.1f}%")
