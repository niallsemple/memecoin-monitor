#!/usr/bin/env python3
"""fee_drag_model.py — §208: sizing scale-up model for the 40-close verdict.

Replays the panic-stop cohort (market-action closes only) at 1x/2x/3x
stake. Fees are mostly FIXED per tx (priority fee), so they shrink as a
% of stake when size grows; slippage/price-impact GROWS with size.
Scenario grid over extra round-trip impact: 0% / 1% / 2%.

Per-trade gross ret% is taken from realized book pnl / size (wallet
deltas, so sell-side fees already netted). We then subtract the
estimated fixed fee drag per trade (~2 txs x 0.00094 SOL) scaled
relative to the 1x book, and apply the impact scenario.

Usage: python3 fee_drag_model.py
"""
import json

PANIC_COHORT_FIRST = "ro8Btws2BfLJNGD6BCNdPmwtxtZL2R6LMYGKERdpump"
INFRA = ("reclaim_bug_burned",)
FEE_PER_TRADE = 2 * 0.00094          # buy + sell priority/network fees
CAP_CURRENT = 0.2


def main():
    pos = json.load(open("live_positions.json"))
    closed = [(m, p) for m, p in pos.items() if not p.get("open")]
    closed.sort(key=lambda kv: kv[1].get("entry_t", 0))
    idx = next((i for i, (m, _) in enumerate(closed)
                if m.startswith(PANIC_COHORT_FIRST[:8])), 0)
    cohort = [(m, p) for m, p in closed[idx:]
              if p.get("closed_reason") not in INFRA]

    n = len(cohort)
    rets = [(p["pnl_sol"] / p["size_sol"], p["size_sol"])
            for _, p in cohort]
    avg_stake = sum(s for _, s in rets) / n
    print("=" * 64)
    print(f"FEE-DRAG SIZING MODEL — panic cohort, market-action only")
    print(f"{n} closes, avg stake {avg_stake:.4f} SOL, "
          f"fee/trade ~{FEE_PER_TRADE:.5f} SOL (fixed)")
    print("=" * 64)
    print(f"{'scale':>5} {'stake':>7} {'impact':>7} {'net SOL':>9} "
          f"{'%/trade':>8} {'fee% stake':>10} {'worst':>8}")
    for scale in (1, 2, 3):
        stake = avg_stake * scale
        for impact in (0.0, 0.01, 0.02):
            tot = 0.0
            worst = 0.0
            for r, s in rets:
                pnl = r * s * scale - impact * s * scale
                # fee drag: book pnl already nets sell-side fee at 1x;
                # approximate incremental fixed fee vs 1x book
                pnl -= FEE_PER_TRADE * (scale - 1) * 0.5
                tot += pnl
                worst = min(worst, pnl)
            staked = avg_stake * scale * n
            print(f"{scale:>4}x {stake:7.4f} {impact*100:6.1f}% "
                  f"{tot:+9.5f} {100*tot/staked:+7.2f}% "
                  f"{100*FEE_PER_TRADE/stake:9.2f}% {worst:+8.5f}")
    print()
    print(f"Sizing rule: 5% of balance, cap {CAP_CURRENT} SOL.")
    print(f"  2x on current wallet 2.53 => 0.253 SOL/trade — EXCEEDS cap; "
          f"verdict must raise cap to ~0.30 or sizing stays 1x.")
    print(f"  3x => 0.379 — needs cap ~0.40 and deeper pools; "
          f"1-2% extra impact already eats 25-50% of edge.")
    print("=" * 64)


if __name__ == "__main__":
    main()
