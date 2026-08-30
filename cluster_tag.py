#!/usr/bin/env python3
"""Cluster tag (stage 4): is a known cluster wallet among this token's
earliest buyers? (REPORT.md §17/§18 — H09/H10 forward validation.)

v2 (2026-08-27, §27 instrumentation fix): the first version broke pagination
on Helius short pages (type=SWAP pages often return 94-99 txs even when more
history exists), so it stopped at page 1 and missed the birth window; it also
only recognised buys via events.swap tokenOutputs, missing txs where the swap
event is absent or the mint leg sits in tokenTransfers / innerSwaps.
Validated against 37 known cluster-positive tokens (wallet_firstbuyers.json).

Pagination now continues until the oldest fetched tx predates pair creation
(created_ts, unix seconds) or MAX_PAGES is reached. Buyer rule:
  (a) events.swap: mint in tokenOutputs and not in tokenInputs -> feePayer buy
  (b) fallback: feePayer receives the mint via tokenTransfers (amount > 0)
  (c) innerSwaps legs are checked the same way as (a)

Cost: 1-12 Helius enhanced-API calls per token, only for Solana tokens.
"""
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
HELIUS_TXS = "https://api.helius.xyz/v0/addresses/{}/transactions?api-key={}&type=SWAP&limit=100"
MAX_PAGES = 12
MAX_BUYERS = 25


def _key():
    f = ROOT / "helius_key.txt"
    return f.read_text().strip() if f.exists() else ""


def cluster_wallets():
    f = ROOT / "cluster_wallets.txt"
    if not f.exists():
        return set()
    return {w.strip() for w in f.read_text().splitlines() if w.strip()}


def _is_buy(tx, mint):
    """True if feePayer acquired `mint` in this tx."""
    sw = (tx.get("events") or {}).get("swap") or {}
    legs = [sw] + list(sw.get("innerSwaps") or [])
    for leg in legs:
        outs = [t.get("mint") for t in (leg.get("tokenOutputs") or [])]
        ins = [t.get("mint") for t in (leg.get("tokenInputs") or [])]
        if mint in outs and mint not in ins:
            return True
    fp = tx.get("feePayer")
    for x in (tx.get("tokenTransfers") or []):
        if (x.get("mint") == mint and x.get("toUserAccount") == fp
                and (x.get("tokenAmount") or 0) > 0):
            return True
    return False


def tag(mint, created_ts=None, max_pages=MAX_PAGES):
    """Return {'hit': [wallets...], 'first_buyers': N, 'pages': P,
    'reached_birth': bool} or {'error': ...}. Empty hit list = no cluster
    wallet seen. created_ts: unix seconds of pair creation (birth anchor).
    max_pages: detection-time calls should pass a small cap (a ~13-min-old
    token's birth is 1-3 pages deep); the +15-min re-tag uses the full depth."""
    key = _key()
    if not key:
        return {"error": "no_helius_key"}
    cluster = cluster_wallets()
    if not cluster:
        return {"error": "no_cluster_list"}

    url = HELIUS_TXS.format(mint, key)
    all_tx, before, reached_birth = [], None, False
    empty_streak = 0
    for _ in range(max_pages):
        u = url + (f"&before={before}" if before else "")
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "memecoin-monitor/1.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                txs = json.loads(r.read().decode())
        except Exception as e:
            return {"error": str(e)[:100], "pages": len(all_tx) // 100 + 1}
        if not txs:
            empty_streak += 1
            if empty_streak >= 2:
                reached_birth = True
                break
            time.sleep(0.8)
            continue
        empty_streak = 0
        all_tx.extend(txs)
        oldest = txs[-1].get("timestamp", 0)
        before = txs[-1].get("signature")
        time.sleep(0.8)
        if created_ts and oldest and oldest <= created_ts:
            reached_birth = True
            break
    else:
        pass
    if not created_ts and all_tx and len(all_tx) < 100:
        reached_birth = True

    if not all_tx:
        return {"hit": [], "first_buyers": 0, "pages": 0, "reached_birth": True}

    all_tx.sort(key=lambda t: t.get("timestamp", 0))
    buyers, seen = [], set()
    for tx in all_tx:
        if _is_buy(tx, mint):
            b = tx.get("feePayer")
            if b and b not in seen:
                seen.add(b)
                buyers.append(b)
        if len(buyers) >= MAX_BUYERS:
            break
    hits = [b for b in buyers if b in cluster]
    return {"hit": hits, "first_buyers": len(buyers),
            "pages": len(all_tx) // 100 + 1, "reached_birth": reached_birth}


if __name__ == "__main__":
    import sys
    cts = int(sys.argv[2]) if len(sys.argv) > 2 else None
    print(json.dumps(tag(sys.argv[1], cts), indent=1))
