#!/usr/bin/env python3
"""Cluster ring-2 expansion: wallets that repeatedly appear among the first
buyers of cluster-touched tokens (but aren't in the core 15).

Co-buying the cluster's pushes across multiple tokens = likely same entity /
inner circle. Candidates appearing in >=3 cluster tokens get scored against
tracked outcomes before promotion to the watchlist.
"""
import json, time, urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
KEY = (ROOT / "helius_key.txt").read_text().strip()
state = json.loads((ROOT / "state.json").read_text())["seen"]
cl = json.loads((ROOT / "wallet_clusters.json").read_text())
core = set(cl["wallet_tokens"].keys())
cluster_tokens = set()
for toks in cl["wallet_tokens"].values():
    cluster_tokens |= set(toks)

def ts(s): return datetime.fromisoformat(s).timestamp()

# outcome map
outcome = {}
for key, v in state.items():
    if not key.startswith("solana:"): continue
    det = v.get("detect") or {}
    hist = v.get("history") or []
    if not hist or not det.get("mcap"): continue
    pts = [(h.get("mcap") or 0) / det["mcap"] for h in hist if h.get("mcap")]
    if len(pts) >= 3:
        outcome[key.split(":", 1)[1]] = (max(pts), pts[-1])

# pick cluster-touched tracked tokens with best outcomes, not already scanned
already = set(json.loads((ROOT / "wallet_firstbuyers.json").read_text()).get("n_winners") and [] or [])
scanned_mints = set()
for ms in json.loads((ROOT / "wallet_firstbuyers.json").read_text())["repeat"].values():
    scanned_mints |= set(ms)

cands = []
for key, v in state.items():
    if not key.startswith("solana:"): continue
    mint = key.split(":", 1)[1]
    if mint not in cluster_tokens or mint in scanned_mints: continue
    if mint in outcome and outcome[mint][0] >= 2 and outcome[mint][0] < 1000:
        cands.append((mint, outcome[mint][0]))
cands.sort(key=lambda x: -x[1])
cands = cands[:15]
print(f"cluster tokens to scan for ring-2: {len(cands)}")

def first_buyers(mint, max_pages=6):
    url = f"https://api.helius.xyz/v0/addresses/{mint}/transactions?api-key={KEY}&type=SWAP&limit=100"
    all_tx, before = [], None
    for _ in range(max_pages):
        u = url + (f"&before={before}" if before else "")
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "research/1.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                txs = json.loads(r.read().decode())
        except Exception as e:
            print(f"  err {mint[:8]}: {e}"); break
        if not txs: break
        all_tx.extend(txs)
        before = txs[-1].get("signature")
        time.sleep(0.8)
        if len(txs) < 100: break
    all_tx.sort(key=lambda t: t.get("timestamp", 0))
    buyers, seen = [], set()
    for tx in all_tx:
        sw = (tx.get("events") or {}).get("swap") or {}
        outs = [t.get("mint") for t in (sw.get("tokenOutputs") or [])]
        ins = [t.get("mint") for t in (sw.get("tokenInputs") or [])]
        if mint in outs and mint not in ins:
            b = tx.get("feePayer")
            if b and b not in seen:
                seen.add(b); buyers.append(b)
            if len(buyers) >= 25: break
    return buyers

co = defaultdict(set)
for mint, peak in cands:
    fb = first_buyers(mint)
    print(f"  {mint[:8]} peak={peak:5.1f}x first_buyers={len(fb)}")
    for w in fb:
        if w not in core:
            co[w].add(mint)

ring2 = {w: ms for w, ms in co.items() if len(ms) >= 3}
print(f"\nnon-core wallets seen: {len(co)}; ring-2 candidates (>=3 cluster tokens): {len(ring2)}")
for w, ms in sorted(ring2.items(), key=lambda x: -len(x[1])):
    print(f"  {w} in {len(ms)} cluster tokens")

# score ring-2 wallets against their own recent swaps
print("\n== ring-2 hit-rate scoring ==")
promoted = []
SOL = "So11111111111111111111111111111111111111112"
for w in sorted(ring2, key=lambda w: -len(ring2[w]))[:10]:
    url = f"https://api.helius.xyz/v0/addresses/{w}/transactions?api-key={KEY}&type=SWAP&limit=100"
    toks = set()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "research/1.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            txs = json.loads(r.read().decode())
        for tx in txs:
            sw = (tx.get("events") or {}).get("swap") or {}
            for side in ("tokenOutputs", "tokenInputs"):
                for t in (sw.get(side) or []):
                    m = t.get("mint")
                    if m and m != SOL and not m.startswith("EPjFWdd5"):
                        toks.add(m)
    except Exception as e:
        print(f"  {w[:8]} err: {e}"); continue
    time.sleep(1.0)
    tracked = [m for m in toks if m in outcome]
    wins = [m for m in tracked if outcome[m][0] >= 2]
    if tracked:
        hr = len(wins) / len(tracked) * 100
        print(f"  {w[:12]}… tokens={len(toks)} tracked={len(tracked)} >=2x={len(wins)} ({hr:.0f}%)")
        if hr >= 40 and len(tracked) >= 5:
            promoted.append(w)

print(f"\nPROMOTED to watchlist: {len(promoted)}")
if promoted:
    with (ROOT / "cluster_wallets.txt").open("a") as f:
        f.write("\n".join(promoted) + "\n")
    print("cluster_wallets.txt extended")
json.dump({"ring2": {w: sorted(ms) for w, ms in ring2.items()}, "promoted": promoted},
          (ROOT / "wallet_ring2.json").open("w"), indent=1)
