#!/usr/bin/env python3
"""Meta-rotation stats (playbook-2 #6): do narrative metas exist in our feed,
and does meta membership carry outcome information?

Step 1: resolve names/symbols for all tracked solana mints via dexscreener
batch tokens endpoint (30 per call), cached to names.json.
Step 2: keyword mine names+symbols; per-meta stats: n launches, median peak,
median final ratio, births per 6h bucket (rotation over time).
"""
import json, time, urllib.request, re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).parent
NAMES = ROOT / "names.json"
DEX = "https://api.dexscreener.com/latest/dex/tokens/{}"

state = json.loads((ROOT / "state.json").read_text())["seen"]
mints = [k.split(":", 1)[1] for k in state if k.startswith("solana:")]
names = json.loads(NAMES.read_text()) if NAMES.exists() else {}

todo = [m for m in mints if m not in names]
print(f"mints {len(mints)}, named {len(names)}, to fetch {len(todo)}")
t0 = time.time()
for i in range(0, len(todo), 30):
    if time.time() - t0 > 230:
        print("time budget — re-run"); break
    batch = todo[i:i + 30]
    try:
        req = urllib.request.Request(DEX.format(",".join(batch)),
                                     headers={"User-Agent": "meta-scan/1.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.loads(r.read().decode())
    except Exception as e:
        print("fetch err:", str(e)[:60]); time.sleep(3); continue
    got = {}
    for p in (d.get("pairs") or []):
        if p.get("chainId") != "solana":
            continue
        base = (p.get("baseToken") or {}).get("address")
        if base in batch and base not in got:
            got[base] = (p.get("baseToken") or {})
    for m in batch:
        bt = got.get(m) or {}
        names[m] = {"name": bt.get("name", ""), "symbol": bt.get("symbol", "")}
    NAMES.write_text(json.dumps(names))
    print(f"fetched {i + len(batch)}/{len(todo)}")
    time.sleep(1.2)

if any(m not in names for m in mints):
    raise SystemExit("incomplete — re-run")

# outcome per mint
def outcome(mint):
    v = state.get(f"solana:{mint}") or {}
    det = v.get("detect") or {}
    hist = v.get("history") or []
    if not hist or not det.get("mcap"):
        return None
    pts = [(h.get("mcap") or 0) / det["mcap"] for h in hist if h.get("mcap")]
    if len(pts) < 3:
        return None
    born = det.get("pair_created") or 0
    return max(pts), pts[-1], born / 1000

# keyword mining on names+symbols
STOP = set("the of and a in on to for with ai coin token pepe doge cat dog".split())
kw = Counter()
per_mint_kws = {}
for m in mints:
    nm = names.get(m) or {}
    text = (nm.get("name", "") + " " + nm.get("symbol", "")).lower()
    words = set(w for w in re.findall(r"[a-z]{3,}", text) if w not in STOP)
    per_mint_kws[m] = words
    kw.update(words)

top = [w for w, c in kw.most_common(40) if c >= 12][:20]
print(f"\ntop keywords (n>=12): {[(w, kw[w]) for w in top]}")

print("\n== META STATS ==")
rows = []
for w in top:
    members = [m for m in mints if w in per_mint_kws[m]]
    outs = [o for m in members if (o := outcome(m))]
    if len(outs) < 8:
        continue
    peaks = [o[0] for o in outs]
    finals = [o[1] for o in outs]
    rows.append((w, len(members), len(outs), median(peaks), median(finals),
                 sum(1 for p in peaks if p >= 2) / len(peaks)))
rows.sort(key=lambda r: -r[5])
allouts = [o for m in mints if (o := outcome(m))]
allpeaks = [o[0] for o in allouts]
print(f"{'meta':<14} {'launch':>6} {'w/out':>6} {'medPeak':>8} {'medFinal':>8} {'hit>=2x':>8}")
for w, n, no, mp, mf, h in rows:
    print(f"{w:<14} {n:>6} {no:>6} {mp:>8.2f} {mf:>8.2f} {h:>8.2f}")
print(f"{'ALL-TOKENS':<14} {len(mints):>6} {len(allouts):>6} {median(allpeaks):>8.2f} "
      f"{median([o[1] for o in allouts]):>8.2f} {sum(1 for p in allpeaks if p>=2)/len(allpeaks):>8.2f}")

# rotation: births per 6h for the two hottest metas
if rows:
    print("\n== ROTATION (births per 6h UTC bucket) ==")
    for w, *_ in rows[:3]:
        members = [m for m in mints if w in per_mint_kws[m]]
        buckets = defaultdict(lambda: [0, []])
        for m in members:
            o = outcome(m)
            if not o:
                continue
            b = time.strftime("%d-%H", time.gmtime(o[2] // 21600 * 21600))
            buckets[b][0] += 1
            buckets[b][1].append(o[0])
        print(f"meta '{w}':")
        for b in sorted(buckets):
            n, ps = buckets[b]
            print(f"  {b}h: launches={n} medPeak={median(ps):.2f}")
json.dump({"rows": rows}, (ROOT / "meta_stats.json").open("w"), indent=1)
print("saved -> meta_stats.json")
