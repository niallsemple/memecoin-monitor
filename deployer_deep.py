#!/usr/bin/env python3
"""Deep re-scan of the 11 repeat-'deployer' mints: paginate to TRUE birth
(MAX_PAGES=80) and compare birth feePayer vs the truncated artifact."""
import json, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
KEY = (ROOT / "helius_key.txt").read_text().strip()
TXS = "https://api.helius.xyz/v0/addresses/{}/transactions?api-key={}&limit=100"
OUT = ROOT / "deployer_deep.json"
MAX_PAGES = 80

prev = json.loads((ROOT / "deployer_scan.json").read_text())
from collections import Counter
deps = Counter(r.get("deployer") for r in prev.values() if r.get("deployer"))
targets = [m for m, r in prev.items() if deps.get(r.get("deployer"), 0) >= 2]
state = json.loads((ROOT / "state.json").read_text())["seen"]

done = json.loads(OUT.read_text()) if OUT.exists() else {}
todo = [m for m in targets if m not in done]
print(f"targets: {len(targets)}, remaining: {len(todo)}")
t0 = time.time()
for mint in todo:
    if time.time() - t0 > 250:
        print("time budget — re-run"); break
    pc = (state.get(f"solana:{mint}", {}).get("detect") or {}).get("pair_created")
    pc_s = pc / 1000 if pc else None
    before, oldest, pages = None, None, 0
    for _ in range(MAX_PAGES):
        u = TXS.format(mint, KEY) + (f"&before={before}" if before else "")
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "deep/1.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                page = json.loads(r.read().decode())
        except Exception as e:
            page = []
        pages += 1
        if not page:
            break
        oldest = page[-1]
        before = page[-1].get("signature")
        if pc_s and oldest.get("timestamp", 0) <= pc_s + 60:
            break
        time.sleep(0.7)
        if len(page) < 100:
            break
    rec = {"deployer": oldest.get("feePayer") if oldest else None,
           "birth_ts": oldest.get("timestamp") if oldest else None,
           "pages": pages,
           "gap_min": round((oldest["timestamp"] - pc_s) / 60, 1) if oldest and pc_s else None,
           "label": prev[mint]["label"], "peak_x": prev[mint].get("peak_x")}
    done[mint] = rec
    OUT.write_text(json.dumps(done, indent=1))
    print(f"{rec['label']} {mint[:8]} true-birth feePayer={(rec['deployer'] or 'ERR')[:12]} gap={rec['gap_min']}m pages={pages}")

if all(m in done for m in targets):
    print("\n== TRUE-BIRTH DEPLOYERS for the 11 repeat rows ==")
    dd = Counter(r.get("deployer") for r in done.values() if r.get("deployer"))
    for m, r in sorted(done.items(), key=lambda x: x[1]["label"]):
        print(f"  {r['label']} {m[:8]} peak={r.get('peak_x')} -> {(r.get('deployer') or 'ERR')[:16]} gap={r['gap_min']}m")
    print("repeat true deployers:", {d[:12]: c for d, c in dd.items() if c >= 2} or "NONE")
