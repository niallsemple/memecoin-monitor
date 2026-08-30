#!/usr/bin/env python3
"""PHASE 3 base-rate study: what happens to the average new Solana listing?

Uses every tracked Solana token with price history (audited or not) —
this is the actual population our feed produces, warts included.
All ratios vs detection-time mcap (feed lag ~14 min after creation is a
known caveat; 'detection' is our earliest observable point, not birth).
"""
import json
from pathlib import Path
from datetime import datetime
from statistics import median

ROOT = Path(__file__).parent
state = json.loads((ROOT / "state.json").read_text())["seen"]

def ts(s): return datetime.fromisoformat(s).timestamp()

toks = []
for key, v in state.items():
    if not key.startswith("solana:"): continue
    hist = v.get("history") or []
    det = v.get("detect") or {}
    if not hist or not det.get("mcap"): continue
    t0 = ts(hist[0]["t"])
    pts = [(ts(h["t"]) - t0, (h.get("mcap") or 0) / det["mcap"]) for h in hist if h.get("mcap")]
    if len(pts) < 3: continue
    toks.append({"key": key, "verdict": v.get("verdict"), "pts": pts,
                 "age_min": (t0*1000 - (det.get("pair_created") or 0))/60000 if det.get("pair_created") else None})

print(f"population: {len(toks)} Solana tokens with usable history")

def at(pts, sec):
    c = [r for dt, r in pts if dt >= sec]
    return c[0] if c else None

# survival / multiples by horizon
print("\n== distribution of value vs detection at each horizon ==")
print(f"{'horizon':>10s} {'n':>5s} {'med':>6s} {'>=0.5x':>7s} {'>=1x':>6s} {'>=2x':>6s} {'>=5x':>6s} {'>=10x':>6s} {'<=0.1x':>7s}")
for lbl, sec in [("+1min",60),("+5min",300),("+15min",900),("+30min",1800),("+1h",3600),("+2h",7200),("+6h",21600),("+24h",86400)]:
    vals = [at(t["pts"], sec) for t in toks]
    vals = [v for v in vals if v is not None]
    if not vals: continue
    f = lambda p: sum(1 for v in vals if p(v))/len(vals)*100
    print(f"{lbl:>10s} {len(vals):5d} {median(vals):5.2f}x {f(lambda v:v>=0.5):6.0f}% {f(lambda v:v>=1):5.0f}% {f(lambda v:v>=2):5.0f}% {f(lambda v:v>=5):5.0f}% {f(lambda v:v>=10):5.0f}% {f(lambda v:v<=0.1):6.0f}%")

# ever-reach multiples (peak over full track)
print("\n== ever reached multiple of detection value (full track window) ==")
for m in (1.25, 1.5, 2, 3, 5, 10):
    n = sum(1 for t in toks if max(r for _, r in t["pts"]) >= m)
    print(f"  peak >= {m}x: {n} ({n/len(toks)*100:.0f}%)")

# time to peak
ttypeak = [next(dt for dt, r in t["pts"] if r == max(x for _, x in t["pts"]))/60 for t in toks]
print(f"\ntime-to-peak: median {median(ttypeak):.0f} min after detection; "
      f"{sum(1 for x in ttypeak if x <= 30)/len(ttypeak)*100:.0f}% peak within 30 min")

# detection age
ages = [t["age_min"] for t in toks if t["age_min"] is not None]
print(f"feed lag (detection age): median {median(ages):.1f} min after pair creation")

# audit verdict as rug/failure predictor at +1h
print("\n== verdict vs outcome at +1h ==")
for vd in ("PASS","CAUTION","FAIL","NO_AUDIT"):
    g = [t for t in toks if t["verdict"] == vd]
    vals = [at(t["pts"], 3600) for t in g]; vals = [v for v in vals if v is not None]
    if vals:
        print(f"  {vd:8s} n={len(vals):4d} med@1h={median(vals):5.2f}x  dead(<0.2x)={sum(1 for v in vals if v<0.2)/len(vals)*100:3.0f}%  >=2x={sum(1 for v in vals if v>=2)/len(vals)*100:3.0f}%")
