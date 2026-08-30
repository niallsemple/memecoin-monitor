"""Flag-flip monitor automation entry: one RugCheck re-poll pass per run.

Checks the newest tracked solana tokens (last 48h) against their previous
risk counts, timestamps flips to memecoin-monitor/flagflips.jsonl.
"""
import json
import time
import urllib.request
from pathlib import Path

MON = Path("/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor")
RUG = "https://api.rugcheck.xyz/v1/tokens/{}/report/summary"
PREV = MON / "flagflip_state.json"
LOG = MON / "flagflips.jsonl"
STATE = MON / "state.json"
MAX_AGE_H = 48
MAX_CHECK = 40


def run(ctx):
    state = json.loads(STATE.read_text())["seen"]
    prev = json.loads(PREV.read_text()) if PREV.exists() else {}
    now = time.time()

    cand = []
    for key, v in state.items():
        if not key.startswith("solana:"):
            continue
        pc = (v.get("detect") or {}).get("pair_created")
        if not pc:
            continue
        if (now - pc / 1000) / 3600 <= MAX_AGE_H:
            cand.append((pc, key.split(":", 1)[1]))
    cand.sort(reverse=True)
    cand = [m for _, m in cand][:MAX_CHECK]

    flips = []
    checked = 0
    for mint in cand:
        try:
            req = urllib.request.Request(
                RUG.format(mint),
                headers={"User-Agent": "flagflip-mon/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                rep = json.loads(r.read().decode())
            risks = len(rep.get("risks") or [])
            score = rep.get("score_normalised")
            checked += 1
        except Exception:
            time.sleep(0.4)
            continue
        old = prev.get(mint)
        if old is not None and old != risks:
            rec = {"t": now, "mint": mint, "risks_from": old,
                   "risks_to": risks, "score": score}
            with LOG.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            flips.append(rec)
        prev[mint] = risks
        time.sleep(0.4)

    PREV.write_text(json.dumps(prev))
    return {"artifact": {
        "summary": f"checked {checked} tokens, {len(flips)} flag flips logged",
        "checked": checked, "flips": len(flips),
        "flip_mints": [f["mint"][:10] for f in flips],
    }}
