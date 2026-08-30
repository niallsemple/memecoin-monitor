#!/usr/bin/env python3
"""Part 6 wallet intelligence, test 1b (H09): TRUE first-buyer overlap.

wallet_intel.py's window didn't reach token birth for heavily traded winners.
This paginates until transactions predate pair creation (cap 12 pages/token),
extracts the true first-25 unique buyers per winner, and measures overlap.
"""
import json, time, urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
state = json.loads((ROOT / "state.json").read_text())["seen"]
KEY = (ROOT / "helius_key.txt").read_text().strip()

def ts(s): return datetime.fromisoformat(s).timestamp()

cands = []
for key, v in state.items():
    if not key.startswith("solana:"): continue
    det = v.get("detect") or {}
    hist = v.get("history") or []
    if not hist or not det.get("mcap") or not det.get("pair_created"): continue
    pts = [(h.get("mcap") or 0) / det["mcap"] for h in hist if h.get("mcap")]
    if len(pts) < 3: continue
    peak = max(pts)
    if peak >= 3 and peak < 1000:  # drop data artifacts
        cands.append((key.split(":", 1)[1], peak, det["pair_created"] / 1000))

cands.sort(key=lambda x: -x[1])
cands = cands[:10]
print(f"winners to fully paginate: {len(cands)}")

def first_buyers(mint, created_ts, max_pages=12):
    url = f"https://api.helius.xyz/v0/addresses/{mint}/transactions?api-key={KEY}&type=SWAP&limit=100"
    all_tx, before = [], None
    for _ in range(max_pages):
        u = url + (f"&before={before}" if before else "")
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "research/1.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                txs = json.loads(r.read().decode())
        except Exception as e:
            print(f"  fetch error: {e}"); break
        if not txs: break
        all_tx.extend(txs)
        oldest = txs[-1].get("timestamp", 0)
        before = txs[-1].get("signature")
        time.sleep(1.0)
        if oldest and oldest <= created_ts: break  # reached birth
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
    return buyers, len(all_tx)

idx = defaultdict(set)
for mint, peak, created in cands:
    fb, ntx = first_buyers(mint, created)
    birth = "reached" if fb else "EMPTY"
    print(f"  {mint[:8]} peak={peak:6.1f}x txs_seen={ntx:4d} first_buyers={len(fb)}")
    for w in fb: idx[w].add(mint)

repeat = {w: ms for w, ms in idx.items() if len(ms) >= 2}
print(f"\nunique first-buyer wallets: {len(idx)}")
print(f"repeat across >=2 winners: {len(repeat)}")
for w, ms in sorted(repeat.items(), key=lambda x: -len(x[1])):
    print(f"  {w} -> {len(ms)} winners: {[m[:8] for m in sorted(ms)]}")

json.dump({"repeat": {w: sorted(ms) for w, ms in repeat.items()},
           "n_wallets": len(idx), "n_winners": len(cands)},
          (ROOT / "wallet_firstbuyers.json").open("w"), indent=1)
