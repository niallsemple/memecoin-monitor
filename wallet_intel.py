#!/usr/bin/env python3
"""Part 6 wallet intelligence, test 1 (H09): early-buyer overlap across winners.

H06 killed 'follow top-20 holders'. This tests the sharper question:
do any wallets show up as EARLY BUYERS of multiple winning tokens?

Method:
  - winners: tracked tokens with peak >= 3x detection mcap
  - control: tracked tokens that never exceeded 1.5x and ended < 0.5x
  - for each, pull earliest SWAP txs via Helius enhanced API, extract buyers
    (feePayer where the memecoin appears in tokenOutputs)
  - overlap = wallets appearing as early buyer in >=2 tokens of the group

If winners show materially more overlap than control, followable smart money
exists at the early-buyer level. If not, H09 dies next to H06.
"""
import json, time, urllib.request
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
state = json.loads((ROOT / "state.json").read_text())["seen"]
KEY = (ROOT / "helius_key.txt").read_text().strip()

def ts(s): return datetime.fromisoformat(s).timestamp()

def outcome(v):
    det = v.get("detect") or {}
    hist = v.get("history") or []
    if not hist or not det.get("mcap"): return None
    pts = [(h.get("mcap") or 0) / det["mcap"] for h in hist if h.get("mcap")]
    if len(pts) < 3: return None
    return max(pts), pts[-1]

winners, losers = [], []
for key, v in state.items():
    if not key.startswith("solana:"): continue
    o = outcome(v)
    if not o: continue
    peak, final = o
    mint = key.split(":", 1)[1]
    if peak >= 3: winners.append((mint, peak))
    elif peak < 1.5 and final < 0.5: losers.append((mint, peak))

winners.sort(key=lambda x: -x[1])
winners = winners[:12]
losers = losers[:12]
print(f"winners: {len(winners)}, control losers: {len(losers)}")

def early_buyers(mint, max_pages=2):
    """Wallets that RECEIVED the memecoin in the earliest swap txs."""
    url = f"https://api.helius.xyz/v0/addresses/{mint}/transactions?api-key={KEY}&type=SWAP&limit=100"
    buyers, before = [], None
    for _ in range(max_pages):
        u = url + (f"&before={before}" if before else "")
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "research/1.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                txs = json.loads(r.read().decode())
        except Exception as e:
            print(f"  fetch error {mint[:8]}: {e}"); break
        if not txs: break
        for tx in txs:
            sw = (tx.get("events") or {}).get("swap") or {}
            outs = [t.get("mint") for t in (sw.get("tokenOutputs") or [])]
            ins = [t.get("mint") for t in (sw.get("tokenInputs") or [])]
            if mint in outs and mint not in ins:
                buyers.append(tx.get("feePayer"))
        before = txs[-1].get("signature")
        time.sleep(1.0)
    # API returns newest-first; earliest buys are at the END
    buyers = [b for b in reversed(buyers) if b]
    seen, early = set(), []
    for b in buyers:
        if b not in seen:
            seen.add(b); early.append(b)
        if len(early) >= 25: break
    return early

def group_wallets(group, label):
    idx = defaultdict(set)
    for mint, peak in group:
        eb = early_buyers(mint)
        print(f"  {label} {mint[:8]} peak={peak:.1f}x early_buyers={len(eb)}")
        for w in eb: idx[w].add(mint)
    repeat = {w: ms for w, ms in idx.items() if len(ms) >= 2}
    print(f"{label}: unique wallets={len(idx)}, repeat (>=2 tokens)={len(repeat)}")
    for w, ms in sorted(repeat.items(), key=lambda x: -len(x[1]))[:10]:
        print(f"    {w[:12]}… in {len(ms)} tokens")
    return idx, repeat

print("\n== WINNERS ==")
w_idx, w_rep = group_wallets(winners, "W")
print("\n== CONTROL (losers) ==")
l_idx, l_rep = group_wallets(losers, "L")

print(f"\n== VERDICT ==")
print(f"winner overlap rate: {len(w_rep)}/{len(w_idx)} wallets repeat")
print(f"control overlap rate: {len(l_rep)}/{len(l_idx)} wallets repeat")
cross = set(w_rep) & set(l_idx)
print(f"wallets in winner-repeat set also buying losers: {len(cross)}")
json.dump({"winners": {w: sorted(ms) for w, ms in w_rep.items()},
           "control": {w: sorted(ms) for w, ms in l_rep.items()}},
          (ROOT / "wallet_overlap.json").open("w"), indent=1)
