#!/usr/bin/env python3
"""Lifecycle trace (§55): manufactured graduates from birth -> graduation ->
post-migration path.

Joins curves.jsonl (birth seed, creator, grad time) to state.json
(minute-scale mcap history post-listing). For graduates missing from
state.json, falls back to dexscreener batch API for a current snapshot.

Classes:
  MFG   = seed >= 20 SOL (manufactured, 82% instant-graduate class)
  FAST  = seed >= 5 and < 20 SOL
  ORG   = graduated with seed < 5 SOL (slower/organic-ish graduates)
Outputs per class: n, % with state history, median peak, median final,
median time-to-peak, % >= 2x, % dead (<0.5x) at last point.
"""
import json, time, urllib.request
from pathlib import Path
from statistics import median
from datetime import datetime

ROOT = Path(__file__).parent
DEX = "https://api.dexscreener.com/latest/dex/tokens/{}"

births, mig = {}, {}
for l in (ROOT / "curves.jsonl").read_text().splitlines():
    try:
        d = json.loads(l)
    except Exception:
        continue
    if not isinstance(d, dict):
        continue
    if d.get("txType") == "create":
        births[d.get("mint")] = d
    elif d.get("txType") == "migrate":
        mig[d.get("mint")] = d

state = json.loads((ROOT / "state.json").read_text())["seen"]

def parse_t(t):
    if isinstance(t, (int, float)):
        return t / 1000 if t > 1e12 else t
    try:
        return datetime.fromisoformat(str(t).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None

def cls(seed):
    if seed is None:
        return None
    if seed >= 20:
        return "MFG"
    if seed >= 5:
        return "FAST"
    return "ORG"

rows = []
missing = []
for m, mg in mig.items():
    b = births.get(m)
    if not b:
        continue
    seed = b.get("solAmount")
    c = cls(seed)
    grad_s = (mg.get("_ts") or 0) - (b.get("_ts") or 0)
    v = state.get(f"solana:{m}")
    rec = {"mint": m, "cls": c, "seed": seed, "grad_s": grad_s,
           "creator": b.get("traderPublicKey"),
           "mcap_at_mig_sol": mg.get("marketCapSol")}
    if v and (v.get("history") or []) and (v.get("detect") or {}).get("mcap"):
        det = v["detect"]
        pts = []
        for h in v["history"]:
            mc, t = h.get("mcap"), parse_t(h.get("t"))
            if mc and t:
                pts.append((t, mc / det["mcap"]))
        pts.sort()
        if len(pts) >= 3:
            peak = max(p[1] for p in pts)
            ttp = (pts[[p[1] for p in pts].index(peak)][0] - pts[0][0]) / 60
            rec.update({"tracked": True, "peak": peak, "final": pts[-1][1],
                        "ttp_m": round(ttp, 1), "n_pts": len(pts),
                        "age_h": round((time.time() - (mg.get("_ts") or time.time())) / 3600, 1)})
            rows.append(rec)
            continue
    rec["tracked"] = False
    missing.append(rec)
    rows.append(rec)

print(f"graduates matched to births: {len(rows)} | tracked in state: "
      f"{sum(1 for r in rows if r['tracked'])} | missing: {len(missing)}")

# dexscreener fallback for missing (current snapshot only)
if missing:
    mints = [r["mint"] for r in missing]
    for i in range(0, len(mints), 30):
        batch = mints[i:i + 30]
        try:
            req = urllib.request.Request(DEX.format(",".join(batch)),
                                         headers={"User-Agent": "lifecycle/1.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                d = json.loads(r.read().decode())
        except Exception:
            continue
        for p in (d.get("pairs") or []):
            if p.get("chainId") != "solana":
                continue
            base = (p.get("baseToken") or {}).get("address")
            rec = next((x for x in missing if x["mint"] == base), None)
            if rec:
                pc = p.get("priceChange") or {}
                rec["dex_h24"] = (pc.get("h24"))
                rec["dex_liq"] = (p.get("liquidity") or {}).get("usd")
        time.sleep(1.0)

print("\n== LIFECYCLE BY CLASS (state-tracked only) ==")
print(f"{'cls':<5} {'n':>3} {'medPeak':>8} {'medFinal':>8} {'medTTPm':>8} {'>=2x':>5} {'dead':>5} {'medAgeH':>7}")
for c in ("MFG", "FAST", "ORG"):
    grp = [r for r in rows if r["cls"] == c and r.get("tracked")]
    if not grp:
        print(f"{c:<5} (none tracked)")
        continue
    pk = sorted(r["peak"] for r in grp)
    fn = sorted(r["final"] for r in grp)
    print(f"{c:<5} {len(grp):>3} {median(pk):>8.2f} {median(fn):>8.2f} "
          f"{median(r['ttp_m'] for r in grp):>8.1f} "
          f"{sum(1 for r in grp if r['peak']>=2)/len(grp):>5.2f} "
          f"{sum(1 for r in grp if r['final']<0.5)/len(grp):>5.2f} "
          f"{median(r['age_h'] for r in grp):>7.1f}")

print("\n== MFG individuals (tracked) ==")
for r in sorted([x for x in rows if x["cls"] == "MFG" and x.get("tracked")],
                key=lambda x: -x["peak"])[:15]:
    print(f"  {r['mint'][:10]} seed={r['seed']:.0f} grad={r['grad_s']:.0f}s "
          f"peak={r['peak']:.2f} final={r['final']:.2f} ttp={r['ttp_m']}m age={r['age_h']}h")

json.dump(rows, (ROOT / "lifecycle.json").open("w"), indent=1)
print("saved -> lifecycle.json")
