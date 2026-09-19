#!/usr/bin/env python3
"""broad_feed.py — graduated-token trade feed for the COPYABLE wallet hunt.

Problem (EDGE_CAPTURE.md): mfg_wallet_trades.jsonl samples manufactured
pre-graduation launches, so every high-activity wallet in it is a loser
(zero COPYABLE of 186,103). The copyable cohort trades coins that
SURVIVED the curve. PumpPortal's token-trade websocket needs a funded
API key (verified 2026-09-18: server rejects subscribeTokenTrade without
0.02 SOL on account), so instead we poll Helius enhanced transactions
(type=SWAP) for a rolling watchlist of the most active PumpSwap pools
(GeckoTerminal volume ranking) and write trades to broad_trades.jsonl
in the exact mfg_wallet_trades.jsonl schema, so wallet_vetter.py and
convergence_watch.py consume it via --ledger.

Schema per line: {"t", "wallet", "mint", "side", "sol", "src": "broad"}

Usage:
  python3 broad_feed.py                  # poll forever, 60s cadence
  python3 broad_feed.py --once           # single cycle (test)
  python3 broad_feed.py --watch 25 --interval 60
  python3 broad_feed.py --mints M1,M2    # manual watchlist (test)
"""
import argparse
import json
import ssl
import time
import urllib.request
from pathlib import Path

import certifi  # same TLS pattern as exec_dry.py

MON = Path(__file__).resolve().parent
OUT = MON / "broad_trades.jsonl"
STATE = MON / "broad_feed_state.json"
KEY = (MON / "helius_key.txt").read_text().strip()
HELIUS = "https://api.helius.xyz/v0/addresses/{mint}/transactions" \
         "?api-key=" + KEY + "&type=SWAP&limit=25"
GT_POOLS = "https://api.geckoterminal.com/api/v2/networks/solana" \
           "/dexes/pumpswap/pools?page={page}&sort=h24_tx_count_desc"
UA = {"User-Agent": "darwin-labs-broad-feed/1.0", "Accept": "application/json"}
CTX = ssl.create_default_context(cafile=certifi.where())
SEEN_CAP = 20000


def _http_json(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return json.loads(r.read())


def watchlist(n):
    """Top-N PumpSwap base mints by 24h tx count (most-traded graduates)."""
    mints = []
    for page in (1, 2):
        try:
            d = _http_json(GT_POOLS.format(page=page))
        except Exception as e:
            print(f"  watchlist page{page} error: {str(e)[:80]}")
            continue
        for p in d.get("data", []):
            attr = p.get("attributes", {})
            # base token address from the pool name relationship
            rel = p.get("relationships", {}).get("base_token", {})
            tid = (rel.get("data") or {}).get("id", "")
            mint = tid.split("_", 1)[-1] if "_" in tid else None
            if mint and mint != "So11111111111111111111111111111111111111112":
                mints.append(mint)
            if len(mints) >= n:
                return mints
        time.sleep(0.3)
    return mints[:n]


def parse_swaps(txs, mint):
    """Helius enhanced SWAP txs -> (wallet, side, sol, t, sig) for `mint`."""
    out = []
    for tx in txs or []:
        sw = (tx.get("events") or {}).get("swap") or {}
        sig = tx.get("signature")
        ts = tx.get("timestamp") or time.time()
        ins = sw.get("tokenInputs") or []
        outs = sw.get("tokenOutputs") or []
        ni, no = sw.get("nativeInput") or {}, sw.get("nativeOutput") or {}
        in_m = [t for t in ins if t.get("mint") == mint]
        out_m = [t for t in outs if t.get("mint") == mint]
        if out_m and ni.get("amount"):
            out.append({"wallet": out_m[0].get("userAccount"), "side": "buy",
                        "sol": float(ni["amount"]) / 1e9, "t": ts, "sig": sig})
        elif in_m and no.get("amount"):
            out.append({"wallet": in_m[0].get("userAccount"), "side": "sell",
                        "sol": float(no["amount"]) / 1e9, "t": ts, "sig": sig})
    return [r for r in out if r["wallet"]]


def cycle(mints, state, out):
    seen = set(state.get("seen", []))
    new_trades = 0
    for mint in mints:
        try:
            txs = _http_json(HELIUS.format(mint=mint))
        except Exception as e:
            print(f"  {mint[:10]}… helius error: {str(e)[:80]}")
            time.sleep(0.5)
            continue
        for r in parse_swaps(txs, mint):
            if r["sig"] in seen:
                continue
            seen.add(r["sig"])
            with out.open("a") as f:
                f.write(json.dumps({"t": r["t"], "wallet": r["wallet"],
                                    "mint": mint, "side": r["side"],
                                    "sol": r["sol"], "src": "broad"}) + "\n")
            new_trades += 1
        time.sleep(0.25)  # ~4 req/s, well under limits
    # bounded dedupe set
    state["seen"] = list(seen)[-SEEN_CAP:]
    STATE.write_text(json.dumps(state))
    return new_trades


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--watch", type=int, default=25)
    ap.add_argument("--interval", type=float, default=60)
    ap.add_argument("--mints", default="", help="comma list, skips GeckoTerminal")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    state = json.loads(STATE.read_text()) if STATE.exists() else {"seen": []}
    manual = [m.strip() for m in a.mints.split(",") if m.strip()]
    while True:
        mints = manual or watchlist(a.watch)
        if not mints:
            print("watchlist empty — GeckoTerminal unreachable?")
        else:
            n = cycle(mints, state, Path(a.out))
            print(f"[{time.strftime('%H:%M:%S')}] {len(mints)} mints polled, "
                  f"{n} new trades → {Path(a.out).name}", flush=True)
        if a.once:
            break
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
