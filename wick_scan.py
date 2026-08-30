#!/usr/bin/env python3
"""Sniper-dump wick study (playbook-2 #7): do sharp early drawdowns on
otherwise-healthy tokens recover at a tradable rate?

Pattern: token pumps, then prints a sharp -25..-45% wick (1-3 minute bars)
within the first hour — sniper bots' mechanical exits — then absorbs.
Trade: buy the wick bottom, ride the recovery.

Data: state.json minute-scale mcap history (t/mcap/price per token).
For each token with >=20 history points:
  - find wicks: local min that is >=25% below the running peak so far,
    occurring at age <= 90 min, where the next bar stops falling
  - measure: recovery = max mcap in following 30 min / wick bottom
  - classification: 'recovered' if recovery >= 1.5x the wick bottom
Compare against audit/flag state and early momentum to see if filters help.
"""
import json
from pathlib import Path
from statistics import median

ROOT = Path(__file__).parent
state = json.loads((ROOT / "state.json").read_text())["seen"]

def parse_t(t):
    from datetime import datetime
    if isinstance(t, (int, float)):
        return t / 1000 if t > 1e12 else t
    try:
        return datetime.fromisoformat(str(t).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None

rows = []
for key, v in state.items():
    if not key.startswith("solana:"):
        continue
    det = v.get("detect") or {}
    hist = v.get("history") or []
    if not det.get("mcap") or len(hist) < 20:
        continue
    pts = []
    for h in hist:
        mc = h.get("mcap")
        t = parse_t(h.get("t"))
        if mc and t:
            pts.append((t, mc / det["mcap"]))
    pts.sort()
    if len(pts) < 20:
        continue
    t0 = pts[0][0]
    peak = 0
    wick = None
    for i, (t, x) in enumerate(pts):
        age_m = (t - t0) / 60
        if age_m > 90:
            break
        if x > peak:
            peak = x
        if peak >= 1.4 and x <= peak * 0.70 and age_m >= 4:
            # drawdown >=30% from a real peak; wick bottom = min of next 3 bars
            window = [p[1] for p in pts[i:i + 3]]
            bottom = min(window)
            after = [p[1] for p in pts[i:] if p[0] <= t + 1800]
            if len(after) >= 5:
                wick = {"age_m": round(age_m, 1), "peak": peak,
                        "bottom": bottom, "dd": 1 - bottom / peak,
                        "recovery": max(after) / bottom,
                        "post30": after[-1] / bottom}
            break
    if wick:
        wick["mint"] = key.split(":", 1)[1][:10]
        wick["flags"] = len(v.get("flags") or [])
        wick["final"] = pts[-1][1]
        rows.append(wick)

print(f"tokens with qualifying wick: {len(rows)}")
rec = [r for r in rows if r["recovery"] >= 1.5]
print(f"recovered >=1.5x off wick bottom within 30m: {len(rec)}/{len(rows)} "
      f"= {len(rec)/len(rows):.2f}" if rows else "none")
if rows:
    print(f"median recovery: {median(r['recovery'] for r in rows):.2f}x")
    print(f"median post-30m level vs bottom: {median(r['post30'] for r in rows):.2f}x")
    print(f"median drawdown: {median(r['dd'] for r in rows):.2f}")
    # does audit flag count filter help?
    clean = [r for r in rows if r["flags"] == 0]
    if clean:
        crec = sum(1 for r in clean if r["recovery"] >= 1.5)
        print(f"clean (0 flags): {len(clean)} wicks, recovery {crec}/{len(clean)}"
              f" = {crec/len(clean):.2f}, median recovery {median(r['recovery'] for r in clean):.2f}x")
    # age distribution of wicks
    print("wick ages (min):", sorted(r["age_m"] for r in rows)[:15], "...")
    # biggest recoveries
    for r in sorted(rows, key=lambda x: -x["recovery"])[:8]:
        print(f"  {r['mint']} peak={r['peak']:.2f} dd={r['dd']:.2f} "
              f"bottom={r['bottom']:.2f} rec={r['recovery']:.2f} flags={r['flags']} final={r['final']:.2f}")
json.dump(rows, (ROOT / "wick_scan.json").open("w"), indent=1)
print("saved -> wick_scan.json")
