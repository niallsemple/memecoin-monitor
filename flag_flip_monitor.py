#!/usr/bin/env python3
"""Forward audit flag-flip monitor (playbook-2 #10 deliverable).

Re-polls RugCheck for tokens detected in the last 48h, logs every flag-state
change WITH TIMESTAMPS to flagflips.jsonl. §51 showed flip-up tokens die
(median final 0.01×) but retro data can't tell us flag-vs-dump ordering —
this monitor captures that ordering going forward.

Designed to run as one pass per invocation (cron/automation-friendly):
  python3 flag_flip_monitor.py
Appends flips to flagflips.jsonl; updates flagflip_state.json.
"""
import json, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
RUG = "https://api.rugcheck.xyz/v1/tokens/{}/report/summary"
PREV = ROOT / "flagflip_state.json"
LOG = ROOT / "flagflips.jsonl"
MAX_AGE_H = 48
MAX_CHECK = 40  # calls per pass

state = json.loads((ROOT / "state.json").read_text())["seen"]
prev = json.loads(PREV.read_text()) if PREV.exists() else {}

now = time.time()
cand = []
for key, v in state.items():
    if not key.startswith("solana:"):
        continue
    pc = (v.get("detect") or {}).get("pair_created")
    if not pc:
        continue
    age_h = (now - pc / 1000) / 3600
    if age_h <= MAX_AGE_H:
        cand.append((pc, key.split(":", 1)[1]))
cand.sort(reverse=True)  # newest first
cand = [m for _, m in cand][:MAX_CHECK]

flips = 0
for mint in cand:
    try:
        req = urllib.request.Request(RUG.format(mint),
                                     headers={"User-Agent": "flagflip-mon/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            rep = json.loads(r.read().decode())
        risks = len(rep.get("risks") or [])
        score = rep.get("score_normalised")
    except Exception:
        time.sleep(0.4)
        continue
    old = prev.get(mint)
    if old is not None and old != risks:
        rec = {"t": now, "mint": mint, "risks_from": old, "risks_to": risks,
               "score": score}
        with LOG.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        flips += 1
        print(f"FLIP {mint[:10]}: risks {old} -> {risks} (score {score})")
    prev[mint] = risks
    time.sleep(0.4)

PREV.write_text(json.dumps(prev))
print(f"checked {len(cand)} tokens, {flips} flips logged, state -> {PREV.name}")
