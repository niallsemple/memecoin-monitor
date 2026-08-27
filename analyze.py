#!/usr/bin/env python3
"""Mine state.json histories for optimal trader settings.

For every audited Solana token with history, compute detection features and
outcome stats, then compare cohorts to find what separates winners/rugs.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

ROOT = Path(__file__).parent
state = json.loads((ROOT / "state.json").read_text())["seen"]

def ts(s):
    return datetime.fromisoformat(s).timestamp()

rows = []
for key, v in state.items():
    if not key.startswith("solana:") or not v.get("audited"):
        continue
    hist = v.get("history") or []
    det = v.get("detect") or {}
    d_mcap = det.get("mcap")
    if not hist or not d_mcap:
        continue
    t0 = ts(hist[0]["t"])
    pts = [(ts(h["t"]) - t0, (h.get("mcap") or 0) / d_mcap) for h in hist if h.get("mcap")]
    if len(pts) < 3:
        continue
    peak = max(r for _, r in pts)
    final = pts[-1][1]
    t_peak = next(dt for dt, r in pts if r == peak)
    # ratio at +5/+15 min (first point at/after)
    def at(sec):
        c = [r for dt, r in pts if dt >= sec]
        return c[0] if c else None
    r5, r15 = at(300), at(900)
    # rug: drops below 0.2x within 15 min of detection
    rug_fast = any(r <= 0.2 and dt <= 900 for dt, r in pts)
    buys, sells = det.get("txns_h1_buys") or 0, det.get("txns_h1_sells") or 0
    age_min = (t0 * 1000 - (det.get("pair_created") or 0)) / 60000 if det.get("pair_created") else None
    rows.append({
        "key": key, "verdict": v.get("verdict"), "flags": v.get("flags") or [],
        "d_mcap": d_mcap, "liq": det.get("liq_usd"), "vol": det.get("vol_h1"),
        "bs_ratio": buys / sells if sells else None,
        "age_min": age_min, "peak": peak, "t_peak": t_peak, "final": final,
        "r5": r5, "r15": r15, "rug_fast": rug_fast,
        "tracked_min": (pts[-1][0]) / 60,
    })

print(f"cohort: {len(rows)} audited Solana tokens with history")
by_v = {}
for r in rows:
    by_v.setdefault(r["verdict"], []).append(r)
for vd, g in sorted(by_v.items()):
    print(f"  {vd}: {len(g)}")

def stats(g, label):
    if not g: return
    pk = sorted(r["peak"] for r in g)
    fn = sorted(r["final"] for r in g)
    win2 = sum(1 for r in g if r["peak"] >= 2) / len(g) * 100
    rug = sum(1 for r in g if r["rug_fast"]) / len(g) * 100
    print(f"{label:34s} n={len(g):3d} | peak med={median(pk):5.2f}x | final med={median(fn):5.2f}x | P(peak>=2x)={win2:4.0f}% | fast-rug={rug:4.0f}%")

print("\n== outcomes by audit verdict ==")
for vd in ("PASS", "CAUTION", "FAIL"):
    stats(by_v.get(vd), f"verdict={vd}")

print("\n== PASS cohort: detection-liquidity buckets ==")
p = by_v.get("PASS", [])
for lo, hi in [(0, 20000), (20000, 50000), (50000, 150000), (150000, 10**9)]:
    stats([r for r in p if r["liq"] and lo <= r["liq"] < hi], f"liq ${lo//1000}k-{hi//1000 if hi<10**9 else '∞'}k")

print("\n== PASS cohort: detection-mcap buckets ==")
for lo, hi in [(0, 30000), (30000, 100000), (100000, 500000), (500000, 10**9)]:
    stats([r for r in p if lo <= r["d_mcap"] < hi], f"mcap ${lo//1000}k-{hi//1000 if hi<10**9 else '∞'}k")

print("\n== PASS cohort: buy/sell ratio buckets ==")
for lo, hi in [(0, 1.0), (1.0, 1.5), (1.5, 2.5), (2.5, 99)]:
    stats([r for r in p if r["bs_ratio"] and lo <= r["bs_ratio"] < hi], f"buys/sells {lo}-{hi}")

print("\n== PASS cohort: age at detection ==")
for lo, hi in [(0, 5), (5, 15), (15, 40), (40, 10**6)]:
    stats([r for r in p if r["age_min"] is not None and lo <= r["age_min"] < hi], f"age {lo}-{hi}min")

print("\n== PASS cohort: momentum at +5min (r5) buckets ==")
for lo, hi in [(0, 1.0), (1.0, 1.25), (1.25, 1.5), (1.5, 99)]:
    g = [r for r in p if r["r5"] and lo <= r["r5"] < hi]
    stats(g, f"r5 {lo}-{hi}")

print("\n== PASS cohort: momentum at +15min (r15) buckets ==")
for lo, hi in [(0, 1.0), (1.0, 1.5), (1.5, 99)]:
    g = [r for r in p if r["r15"] and lo <= r["r15"] < hi]
    stats(g, f"r15 {lo}-{hi}")

print("\n== fast-rug signature (PASS tokens that rugged <=15min) ==")
rugs = [r for r in p if r["rug_fast"]]
ok = [r for r in p if not r["rug_fast"]]
def med(g, k):
    vs = [r[k] for r in g if r[k] is not None]
    return f"{median(vs):.1f}" if vs else "-"
print(f"rugs n={len(rugs)}: med mcap=${med(rugs,'d_mcap')} med liq=${med(rugs,'liq')} med bs={med(rugs,'bs_ratio')} med age={med(rugs,'age_min')}min")
print(f"ok   n={len(ok)}: med mcap=${med(ok,'d_mcap')} med liq=${med(ok,'liq')} med bs={med(ok,'bs_ratio')} med age={med(ok,'age_min')}min")
from collections import Counter
print("rug flags:", Counter(f for r in rugs for f in r["flags"]))
print("ok flags:", Counter(f for r in ok for f in r["flags"]))

json.dump(rows, (ROOT / "analysis_rows.json").open("w"), indent=1)
print("\nrows saved to analysis_rows.json")
