#!/usr/bin/env python3
"""Smart-wallet leaderboard (§183, EDGE #6) — first pass.

Reads mfg_wallet_trades.jsonl (wallet-attributed pool trades from
wallet_ledger.py) and ranks wallets. v1 limitations: SOL legs only (no
token amounts), so realized PnL is approximate — we use per wallet-mint
net flow and sell-coverage (sell_sol/buy_sol) as profit proxies.
Depth caveat: ledger accrues forward from 2026-09-02 ~15:45 UTC; early
windows are shallow. Rankings mature with data.

Usage: python3 wallet_board.py [--min-trades N]
"""
import json
import sys
import collections
from pathlib import Path

MON = Path(__file__).resolve().parent
LEDGER = MON / "mfg_wallet_trades.jsonl"


def main():
    min_trades = 3
    if "--min-trades" in sys.argv:
        min_trades = int(sys.argv[sys.argv.index("--min-trades") + 1])
    rows = []
    if LEDGER.exists():
        for line in LEDGER.open():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    if not rows:
        print("ledger empty")
        return

    by_w = collections.defaultdict(list)
    for r in rows:
        by_w[r["wallet"]].append(r)

    board = []
    for w, rs in by_w.items():
        buys = [r for r in rs if r["side"] == "buy"]
        sells = [r for r in rs if r["side"] == "sell"]
        bsol = sum(r["sol"] for r in buys)
        ssol = sum(r["sol"] for r in sells)
        mints = {r["mint"] for r in rs}
        ts = [r["t"] for r in rs if r.get("t")]
        # per wallet-mint: net = sells - buys (negative = still holding
        # or lost); coverage = sell/buy (1.0 = fully round-tripped)
        net, cov_pairs = 0.0, 0
        for m in mints:
            mb = sum(r["sol"] for r in rs if r["mint"] == m and r["side"] == "buy")
            ms = sum(r["sol"] for r in rs if r["mint"] == m and r["side"] == "sell")
            net += ms - mb
            if mb > 0 and ms > 0:
                cov_pairs += 1
        board.append({
            "wallet": w, "trades": len(rs), "mints": len(mints),
            "buys": len(buys), "sells": len(sells),
            "buy_sol": round(bsol, 3), "sell_sol": round(ssol, 3),
            "net_flow": round(net, 3),
            "coverage_pairs": cov_pairs,
            "span_min": round((max(ts) - min(ts)) / 60, 1) if ts else 0,
            "med_trade": round(sorted(r["sol"] for r in rs)[len(rs) // 2], 4),
        })

    board = [b for b in board if b["trades"] >= min_trades]
    board.sort(key=lambda b: -b["net_flow"])
    print(f"wallets: {len(by_w)} total, {len(board)} with >= {min_trades} trades")
    print(f"ledger rows: {len(rows)}")
    print(f"\n{'wallet':10s} {'trd':>4s} {'mnt':>4s} {'buySOL':>9s} {'sellSOL':>9s} "
          f"{'net':>8s} {'cov':>4s} {'span_m':>7s} {'med':>8s}")
    for b in board[:20]:
        print(f"{b['wallet'][:10]:10s} {b['trades']:4d} {b['mints']:4d} "
              f"{b['buy_sol']:9.2f} {b['sell_sol']:9.2f} {b['net_flow']:8.2f} "
              f"{b['coverage_pairs']:4d} {b['span_min']:7.1f} {b['med_trade']:8.4f}")
    # repeat-mint wallets are the interesting ones (one-hit wonders filtered)
    repeat = [b for b in board if b["mints"] >= 2]
    print(f"\nwallets active on >=2 mints: {len(repeat)}")


if __name__ == "__main__":
    main()
