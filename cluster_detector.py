#!/usr/bin/env python3
"""Bundle/volume-bot cluster detector (§186, EDGE #7/#10).

Scores each mint in the wallet ledger for coordinated-cluster signature:
many distinct wallets firing many small, uniform buys in a tight span
with minimal selling. That pattern = bundler network faking volume.

Cluster criteria (per wallet, "bot-like"):
  >= MIN_TRADES buys, median buy <= MAX_MED_SOL, buys >= 4x sells
Cluster flag: >= MIN_BOTS bot-like wallets on the same mint.

Usage:
  python3 cluster_detector.py            # score every mint in ledger
  python3 cluster_detector.py <mint>...  # score specific mints
"""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

MON = Path(__file__).resolve().parent
LEDGER = MON / "mfg_wallet_trades.jsonl"

MIN_TRADES = 20
MAX_MED_SOL = 0.06
MIN_BOTS = 6
OWN = "CQcKkSee9bdHZ1bejYFDUXVtodbfKHe2KSx6AaAnTW2K"


def load(mints=None):
    rows = []
    for line in LEDGER.open():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r["wallet"] == OWN:
            continue
        if mints and r["mint"] not in mints:
            continue
        rows.append(r)
    return rows


def score_mint(mint, rows):
    by_wallet = defaultdict(lambda: {"buys": [], "sells": []})
    for r in rows:
        w = by_wallet[r["wallet"]]
        (w["buys"] if r["side"] == "buy" else w["sells"]).append(r)
    bots = []
    for w, d in by_wallet.items():
        nb, ns = len(d["buys"]), len(d["sells"])
        if nb < MIN_TRADES:
            continue
        med = statistics.median(b["sol"] for b in d["buys"])
        if med > MAX_MED_SOL or nb < 4 * max(ns, 1):
            continue
        bots.append({
            "wallet": w, "buys": nb, "sells": ns,
            "buy_sol": round(sum(b["sol"] for b in d["buys"]), 3),
            "med": round(med, 4),
            "span_m": round((max(b["t"] for b in d["buys"]) -
                             min(b["t"] for b in d["buys"])) / 60, 1),
        })
    ts = [r["t"] for r in rows]
    buy_sol = sum(r["sol"] for r in rows if r["side"] == "buy")
    sell_sol = sum(r["sol"] for r in rows if r["side"] == "sell")
    cluster_sol = round(sum(b["buy_sol"] for b in bots), 2)
    return {
        "mint": mint,
        "rows": len(rows),
        "wallets": len(by_wallet),
        "buy_sol": round(buy_sol, 2),
        "sell_sol": round(sell_sol, 2),
        "span_m": round((max(ts) - min(ts)) / 60, 1) if ts else 0,
        "bots": len(bots),
        "cluster": len(bots) >= MIN_BOTS,
        "cluster_sol": cluster_sol,
        "cluster_share": round(cluster_sol / buy_sol, 3) if buy_sol else 0,
        "bot_detail": sorted(bots, key=lambda b: -b["buy_sol"]),
    }


def main():
    args = sys.argv[1:]
    rows = load(set(args) if args else None)
    by_mint = defaultdict(list)
    for r in rows:
        by_mint[r["mint"]].append(r)
    results = [score_mint(m, rs) for m, rs in by_mint.items()]
    results.sort(key=lambda x: -x["cluster_sol"])
    for s in results:
        flag = "CLUSTER" if s["cluster"] else "clean "
        print(f"{flag} {s['mint'][:12]}… bots={s['bots']:>2} "
              f"clusterSOL={s['cluster_sol']:>7} share={s['cluster_share']:>5} "
              f"wallets={s['wallets']:>4} rows={s['rows']:>5} span={s['span_m']}m")
    return results


if __name__ == "__main__":
    main()
