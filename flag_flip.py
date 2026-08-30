#!/usr/bin/env python3
"""Audit flag-flip study (playbook-2 #10): how often do tokens change audit
state after detection, and what does price do around flips?

Sample N tracked solana tokens, re-pull RugCheck summary now, compare risk
count vs stored detection-time flags. For flip-ups (clean->flagged), check
the stored price path: did the token dump after detection (flag was
propagating) or stay healthy (flag was wrong/late)?
"""
import json, random, time, urllib.request
from pathlib import Path
from statistics import median

ROOT = Path(__file__).parent
RUG = "https://api.rugcheck.xyz/v1/tokens/{}/report/summary"
state = json.loads((ROOT / "state.json").read_text())["seen"]

cand = []
for key, v in state.items():
    if not key.startswith("solana:"):
        continue
    det = v.get("detect") or {}
    hist = v.get("history") or []
    if not det.get("mcap") or len(hist) < 10:
        continue
    if v.get("verdict") is None:
        continue
    cand.append((key.split(":", 1)[1], v))
random.seed(7)
random.shuffle(cand)
cand = cand[:120]
print(f"sampling {len(cand)} tokens")

rows = []
t0 = time.time()
for i, (mint, v) in enumerate(cand):
    if time.time() - t0 > 240:
        print("time budget — partial results"); break
    try:
        req = urllib.request.Request(RUG.format(mint),
                                     headers={"User-Agent": "flagflip/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            rep = json.loads(r.read().decode())
        now_risks = len(rep.get("risks") or [])
        now_score = rep.get("score_normalised")
    except Exception as e:
        now_risks, now_score = None, None
    det = v["detect"]
    pts = [(h.get("mcap") or 0) / det["mcap"] for h in v["history"] if h.get("mcap")]
    then_flags = len(v.get("flags") or [])
    rows.append({
        "mint": mint[:10], "then_flags": then_flags,
        "now_risks": now_risks, "now_score": now_score,
        "peak": max(pts) if pts else None, "final": pts[-1] if pts else None,
    })
    if (i + 1) % 20 == 0:
        print(f"  {i+1}/{len(cand)}")
    time.sleep(0.5)

ok = [r for r in rows if r["now_risks"] is not None and r["peak"]]
print(f"\nresolved: {len(ok)}/{len(rows)}")
flip_up = [r for r in ok if r["then_flags"] == 0 and r["now_risks"] > 0]
flip_dn = [r for r in ok if r["then_flags"] > 0 and r["now_risks"] == 0]
stable_clean = [r for r in ok if r["then_flags"] == 0 and r["now_risks"] == 0]
stable_flag = [r for r in ok if r["then_flags"] > 0 and r["now_risks"] > 0]
print(f"flip UP (clean->flagged): {len(flip_up)}")
print(f"flip DOWN (flagged->clean): {len(flip_dn)}")
print(f"stable clean: {len(stable_clean)}, stable flagged: {len(stable_flag)}")
for name, grp in (("flip_up", flip_up), ("stable_clean", stable_clean),
                  ("stable_flag", stable_flag)):
    if grp:
        print(f"{name}: median peak {median(r['peak'] for r in grp):.2f}x, "
              f"median final {median(r['final'] for r in grp):.2f}x")
json.dump(rows, (ROOT / "flagflip_scan.json").open("w"), indent=1)
print("saved -> flagflip_scan.json")
