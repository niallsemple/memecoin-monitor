#!/usr/bin/env python3
"""40-close verdict review for the live memecoin book.

Reads live_positions.json, pulls the on-chain wallet balance via public RPC,
reconciles book vs chain, and prints the verdict + sizing recommendation.

Usage: python3 review_40.py
"""
import json, time, urllib.request

WALLET = "CQcKkSee9bdHZ1bejYFDUXVtodbfKHe2KSx6AaAnTW2K"
RPC = "https://api.mainnet-beta.solana.com"
FUNDING_BASELINE = 2.68389          # first wallet tx 2026-09-01 18:23 UTC
PANIC_COHORT_FIRST = "Rhm9RvRQozJFiDzE688a21QbsrQsjhvUBmMDNKypump"  # first close after panic stop live


def rpc_balance():
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getBalance",
                       "params": [WALLET, {"commitment": "confirmed"}]}).encode()
    req = urllib.request.Request(RPC, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)["result"]["value"] / 1e9


def main():
    pos = json.load(open("live_positions.json"))
    closed = [(m, p) for m, p in pos.items() if not p.get("open")]
    closed.sort(key=lambda kv: kv[1].get("entry_t", 0))

    n = len(closed)
    wins = [p for _, p in closed if p.get("pnl_sol", 0) > 0]
    losses = [p for _, p in closed if p.get("pnl_sol", 0) <= 0]
    net = sum(p.get("pnl_sol", 0) for _, p in closed)
    staked = sum(p.get("size_sol", 0) for _, p in closed)

    # exit-reason breakdown
    reasons = {}
    for _, p in closed:
        r = p.get("closed_reason", "?")
        reasons.setdefault(r, [0, 0.0])
        reasons[r][0] += 1
        reasons[r][1] += p.get("pnl_sol", 0)

    # panic-stop cohort: everything closed after Rhm9 (inclusive)
    idx = next((i for i, (m, _) in enumerate(closed) if m.startswith(PANIC_COHORT_FIRST[:8])), 0)
    cohort = closed[idx:]
    c_net = sum(p.get("pnl_sol", 0) for _, p in cohort)
    c_wins = sum(1 for _, p in cohort if p.get("pnl_sol", 0) > 0)
    c_staked = sum(p.get("size_sol", 0) for _, p in cohort)

    print("=" * 64)
    print(f"40-CLOSE VERDICT REVIEW  —  {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
    print("=" * 64)
    print(f"\nCloses: {n}   Wins: {len(wins)} ({100*len(wins)/n:.1f}%)   Losses: {len(losses)}")
    print(f"Net PnL (book): {net:+.5f} SOL   Staked total: {staked:.3f} SOL")
    print(f"Expectancy/trade: {100*net/staked:+.2f}% of stake   Avg win: {sum(p['pnl_sol'] for p in wins)/max(len(wins),1):+.5f}")
    if losses:
        print(f"Avg loss: {sum(p['pnl_sol'] for p in losses)/len(losses):+.5f}   Worst: {min(p['pnl_sol'] for p in losses):+.5f}")

    print("\nExit-reason breakdown:")
    for r, (cnt, pnl) in sorted(reasons.items(), key=lambda kv: -kv[1][0]):
        print(f"  {r:28s} n={cnt:3d}  pnl={pnl:+.5f}")

    print(f"\nPanic-stop cohort (since {PANIC_COHORT_FIRST[:8]}…): {len(cohort)} closes, "
          f"{c_wins}/{len(cohort)} green, net {c_net:+.5f} SOL on {c_staked:.3f} staked "
          f"({100*c_net/c_staked:+.2f}%/trade)")

    print("\nOn-chain reconciliation (public RPC, confirmed):")
    try:
        bal = rpc_balance()
        print(f"  Wallet balance: {bal:.6f} SOL")
        print(f"  Funding baseline: {FUNDING_BASELINE:.5f} SOL")
        print(f"  On-chain net since funding: {bal - FUNDING_BASELINE:+.6f} SOL "
              f"({100*(bal - FUNDING_BASELINE)/FUNDING_BASELINE:+.2f}%)")
        implied = FUNDING_BASELINE + net
        print(f"  Book-implied balance: {implied:.6f} SOL   (drift vs chain: {bal - implied:+.6f})")
    except Exception as e:
        print(f"  RPC balance failed: {e}")

    print("\nSizing recommendation inputs:")
    print(f"  Cohort expectancy/trade: {100*c_net/max(c_staked,1e-9):+.2f}% of stake")
    print(f"  Worst cohort trade: {min((p.get('pnl_sol',0) for _,p in cohort), default=0):+.5f}")
    print("  Rule of thumb: scale only if cohort ≥20 closes, ≥85% green, worst ≥ -25% of stake.")
    print("=" * 64)


if __name__ == "__main__":
    main()
