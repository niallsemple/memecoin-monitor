#!/usr/bin/env python3
"""Cluster expansion + hit-rate scoring (H09 validation, step 2).

1. Load the 15 repeat first-buyer wallets (wallet_firstbuyers.json).
2. Pull each wallet's last-100 swaps via Helius -> wallet -> token map.
3. Consolidate wallets into clusters via shared-token linkage (union-find).
4. Score each cluster against ALL tracked token outcomes:
   hit rate (peak>=2x), base-rate lift, loser exposure.
"""
import json, time, urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
KEY = (ROOT / "helius_key.txt").read_text().strip()
state = json.loads((ROOT / "state.json").read_text())["seen"]
repeat = json.loads((ROOT / "wallet_firstbuyers.json").read_text())["repeat"]
wallets = sorted(repeat)
print(f"repeat wallets to expand: {len(wallets)}")

# outcome map: all tracked tokens
outcome = {}
for key, v in state.items():
    if not key.startswith("solana:"): continue
    det = v.get("detect") or {}
    hist = v.get("history") or []
    if not hist or not det.get("mcap"): continue
    pts = [(h.get("mcap") or 0) / det["mcap"] for h in hist if h.get("mcap")]
    if len(pts) >= 3:
        outcome[key.split(":", 1)[1]] = (max(pts), pts[-1])

SOL = "So11111111111111111111111111111111111111112"
wallet_tokens = {}
for w in wallets:
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
                    if m and m != SOL and not m.startswith("EPjFWdd5"):  # exclude SOL/USDC
                        toks.add(m)
    except Exception as e:
        print(f"  {w[:8]} fetch error: {e}")
    wallet_tokens[w] = toks
    time.sleep(1.0)

# union-find over wallets sharing >=2 tokens
parent = {w: w for w in wallets}
def find(x):
    while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
    return x
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb: parent[rb] = ra

ws = list(wallet_tokens)
for i in range(len(ws)):
    for j in range(i+1, len(ws)):
        if len(wallet_tokens[ws[i]] & wallet_tokens[ws[j]]) >= 2:
            union(ws[i], ws[j])

clusters = defaultdict(list)
for w in wallets: clusters[find(w)].append(w)
print(f"\nclusters: {len(clusters)}")
for root, members in sorted(clusters.items(), key=lambda x: -len(x[1])):
    all_toks = set().union(*(wallet_tokens[m] for m in members))
    tracked = [m for m in all_toks if m in outcome]
    wins = [m for m in tracked if outcome[m][0] >= 2]
    big = [m for m in tracked if outcome[m][0] >= 3]
    losses = [m for m in tracked if outcome[m][0] < 1.5]
    hr = len(wins)/len(tracked)*100 if tracked else 0
    print(f"  cluster {root[:8]} ({len(members)}w): {len(all_toks)} tokens, {len(tracked)} tracked | "
          f">=2x: {len(wins)} ({hr:.0f}%) | >=3x: {len(big)} | <1.5x: {len(losses)}")
    for m in sorted(big, key=lambda m: -outcome[m][0])[:8]:
        print(f"      {m[:8]} peak={outcome[m][0]:.1f}x")

json.dump({"clusters": {r: ms for r, ms in clusters.items()},
           "wallet_tokens": {w: sorted(t) for w, t in wallet_tokens.items()}},
          (ROOT / "wallet_clusters.json").open("w"), indent=1)
print("\nsaved wallet_clusters.json")
