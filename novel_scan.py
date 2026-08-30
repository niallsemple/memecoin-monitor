#!/usr/bin/env python3
"""Part 8 — novel hypothesis scan. Every hypothesis has a stated mechanism
BEFORE the test (anti-data-mining rule). Tested on all tracked Solana tokens
with history. Outcome metrics: P(peak>=2x), dead rate (final<0.2x), med peak.
"""
import json
from datetime import datetime
from statistics import median
from pathlib import Path

ROOT = Path(__file__).parent
state = json.loads((ROOT / "state.json").read_text())["seen"]

def ts(s): return datetime.fromisoformat(s).timestamp()

rows = []
for key, v in state.items():
    if not key.startswith("solana:"): continue
    det = v.get("detect") or {}
    hist = v.get("history") or []
    if not hist or not det.get("mcap"): continue
    t0 = ts(hist[0]["t"])
    pts = [(ts(h["t"]) - t0, (h.get("mcap") or 0) / det["mcap"]) for h in hist if h.get("mcap")]
    if len(pts) < 3: continue
    buys, sells = det.get("txns_h1_buys") or 0, det.get("txns_h1_sells") or 0
    # first-15min path roughness: mean absolute step change
    early = [r for dt, r in pts if dt <= 900]
    rough = sum(abs(b - a) for a, b in zip(early, early[1:])) / max(1, len(early) - 1) if len(early) > 1 else None
    # dip-recovery: drops below 0.6x then recovers above 1.0x within track
    dip_rec = any(r < 0.6 for _, r in pts) and any(r > 1.0 for dt, r in pts if dt > 300)
    # late peak: max occurs >60min after detection
    peak = max(r for _, r in pts)
    t_peak = next(dt for dt, r in pts if r == peak)
    first_seen = datetime.fromisoformat(v.get("first_seen", hist[0]["t"]))
    rows.append({
        "mint": key.split(":", 1)[1], "verdict": v.get("verdict"),
        "peak": peak, "final": pts[-1][1], "t_peak_min": t_peak / 60,
        "mcap": det["mcap"], "liq": det.get("liq_usd") or 0, "vol": det.get("vol_h1") or 0,
        "bs": buys / sells if sells else (10.0 if buys else None),
        "age": (t0 * 1000 - (det.get("pair_created") or 0)) / 60000 if det.get("pair_created") else None,
        "hour": first_seen.hour, "dow": first_seen.weekday(),
        "rough": rough, "dip_rec": dip_rec,
        "top10": v.get("top10"),
        "pump_suffix": key.endswith("pump"),
        "tracked_min": pts[-1][0] / 60,
    })

print(f"population: {len(rows)}")

def stats(g, label):
    if len(g) < 5:
        print(f"{label:52s} n={len(g)} (too small)"); return
    w2 = sum(1 for r in g if r["peak"] >= 2) / len(g) * 100
    dead = sum(1 for r in g if r["final"] < 0.2) / len(g) * 100
    print(f"{label:52s} n={len(g):4d} P(>=2x)={w2:4.0f}% dead={dead:3.0f}% med_peak={median(r['peak'] for r in g):5.2f}x med_final={median(r['final'] for r in g):5.2f}x")

stats(rows, "BASELINE (all)")

print("\n-- H11 hour-of-day (mechanism: US/EU/Asia attention cycles) --")
for lo, hi, lbl in [(0,6,"00-06 UTC (Asia late)"),(6,12,"06-12 UTC (Asia/EU)"),(12,18,"12-18 UTC (EU/US overlap)"),(18,24,"18-24 UTC (US)")]:
    stats([r for r in rows if lo <= r["hour"] < hi], f"hour {lbl}")

print("\n-- H12 weekend effect (mechanism: thinner pro flow, more retail) --")
stats([r for r in rows if r["dow"] >= 5], "weekend")
stats([r for r in rows if r["dow"] < 5], "weekday")

print("\n-- H13 pump.fun suffix (mechanism: venue flow/graduation design differs) --")
stats([r for r in rows if r["pump_suffix"]], "mint ends 'pump'")
stats([r for r in rows if not r["pump_suffix"]], "other venues")

print("\n-- H14 vol/liq churn (mechanism: wash volume inflates vol vs locked liq) --")
for lo, hi in [(0,1),(1,3),(3,10),(10,10**9)]:
    stats([r for r in rows if r["liq"]>0 and lo <= r["vol"]/r["liq"] < hi], f"vol/liq {lo}-{hi if hi<10**9 else '∞'}")

print("\n-- H15 extreme buy/sell asymmetry (mechanism: manufactured pump flow) --")
for lo, hi in [(0,1),(1,2),(2,4),(4,99)]:
    stats([r for r in rows if r["bs"] and lo <= r["bs"] < hi], f"buys/sells {lo}-{hi}")

print("\n-- H16 liq/mcap ratio bands (mechanism: depth vs valuation = dump fuel) --")
for lo, hi in [(0,0.1),(0.1,0.3),(0.3,1.0),(1.0,99)]:
    stats([r for r in rows if r["mcap"]>0 and lo <= r["liq"]/r["mcap"] < hi], f"liq/mcap {lo}-{hi}")

print("\n-- H17 early path roughness (mechanism: bot churn vs smooth organic bid) --")
for lo, hi in [(0,0.02),(0.02,0.05),(0.05,0.15),(0.15,99)]:
    stats([r for r in rows if r["rough"] is not None and lo <= r["rough"] < hi], f"roughness {lo}-{hi}")

print("\n-- H18 dip-recovery (mechanism: survives first dump = real demand test) --")
stats([r for r in rows if r["dip_rec"]], "dipped <0.6x then recovered >1.0x")
stats([r for r in rows if not r["dip_rec"]], "no dip-recovery pattern")

print("\n-- H19 late peakers (mechanism: community builds after launch bots leave) --")
stats([r for r in rows if r["t_peak_min"] > 60], "peak >60min after detection")
stats([r for r in rows if r["t_peak_min"] <= 5], "peak <=5min (instant top)")

print("\n-- H20 top10 concentration bands (mechanism: moderate concentration = committed insiders?) --")
for lo, hi in [(0,15),(15,30),(30,50),(50,100)]:
    stats([r for r in rows if r["top10"] is not None and lo <= r["top10"] < hi], f"top10 {lo}-{hi}%")

print("\n-- H21 very fresh detection (mechanism: feed speed premium) --")
stats([r for r in rows if r["age"] is not None and r["age"] < 10], "age<10min at detection")
stats([r for r in rows if r["age"] is not None and 10 <= r["age"] < 30], "age 10-30min")
stats([r for r in rows if r["age"] is not None and r["age"] >= 60], "age >=60min")

print("\n-- H22 quiet start (mechanism: stealth accumulation before attention) --")
q25 = sorted(r["vol"] for r in rows)[len(rows)//4]
stats([r for r in rows if r["vol"] <= q25], f"vol_h1 <= p25 (${q25:,.0f})")
stats([r for r in rows if r["vol"] > 0 and r["peak"] >= 2 and r["vol"] <= q25], "quiet-start runners (diag)")
