#!/usr/bin/env python3
"""Serial-deployer scan (playbook-2 #3): does the CREATOR address separate
winners from losers?

For each token in the 41-token cohort (21 winners / 20 losers from
rotation_scan.json + losers_scan.json), paginate the mint's Helius history
to the BIRTH transaction and take its feePayer as the deployer/pool-creator.
Then check deployer recurrence across tokens and deployer -> outcome.

Checkpointed to deployer_scan.json; re-run until complete.
"""
import json, time, urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
KEY = (ROOT / "helius_key.txt").read_text().strip()
TXS = "https://api.helius.xyz/v0/addresses/{}/transactions?api-key={}&limit=100"
OUT = ROOT / "deployer_scan.json"
MAX_PAGES = 15

def birth_deployer(mint):
    """feePayer of the oldest reachable tx on the mint address."""
    before, oldest = None, None
    pages = 0
    for _ in range(MAX_PAGES):
        u = TXS.format(mint, KEY) + (f"&before={before}" if before else "")
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "deployer-scan/1.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                page = json.loads(r.read().decode())
        except Exception as e:
            return {"error": str(e)[:80], "pages": pages}
        pages += 1
        if not page:
            break
        oldest = page[-1]
        before = page[-1].get("signature")
        time.sleep(0.7)
        if len(page) < 100:
            break
    if not oldest:
        return {"error": "no_txs", "pages": pages}
    return {"deployer": oldest.get("feePayer"), "birth_ts": oldest.get("timestamp"),
            "pages": pages, "reached_birth": len(page) < 100 if page else True}

def main():
    done = json.loads(OUT.read_text()) if OUT.exists() else {}
    cohort = []
    for x in json.loads((ROOT / "rotation_scan.json").read_text()):
        if x["id"].startswith("solana:") and x.get("buyers"):
            cohort.append(("W", x["id"].split(":", 1)[1], x.get("peak_x")))
    for x in json.loads((ROOT / "losers_scan.json").read_text()):
        if x["id"].startswith("solana:") and x.get("buyers"):
            cohort.append(("L", x["id"].split(":", 1)[1], None))
    todo = [c for c in cohort if c[1] not in done]
    print(f"cohort {len(cohort)}, remaining {len(todo)}")
    t0 = time.time()
    for label, mint, peak in todo:
        if time.time() - t0 > 250:
            print("time budget hit — re-run"); break
        r = birth_deployer(mint)
        r.update({"label": label, "peak_x": peak})
        done[mint] = r
        OUT.write_text(json.dumps(done, indent=1))
        print(f"{label} {mint[:8]} deployer={(r.get('deployer') or 'ERR')[:12]} pages={r.get('pages')}")
    if all(c[1] in done for c in cohort):
        by_dep = defaultdict(list)
        for mint, r in done.items():
            if r.get("deployer"):
                by_dep[r["deployer"]].append((mint[:8], r["label"], r.get("peak_x")))
        repeat = {d: v for d, v in by_dep.items() if len(v) >= 2}
        print(f"\n== RESULT: unique deployers={len(by_dep)}, repeat deployers={len(repeat)} ==")
        for d, v in sorted(repeat.items(), key=lambda x: -len(x[1])):
            print(f"  {d[:16]}… -> {v}")
        w_deps = {r["deployer"] for r in done.values() if r["label"] == "W" and r.get("deployer")}
        l_deps = {r["deployer"] for r in done.values() if r["label"] == "L" and r.get("deployer")}
        print(f"deployer overlap W∩L: {len(w_deps & l_deps)}")
        print("saved ->", OUT)

if __name__ == "__main__":
    main()
