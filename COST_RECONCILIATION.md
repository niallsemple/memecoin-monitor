# COST TRUTH — reconciliation of the 67× gap (2026-09-13)

ChatGPT flagged: size sweep implies ~0.00003 SOL all-in cost/trade; earlier
live-economic model said ~0.002 SOL round trip. Both are real — they are
different eras.

## The old 0.002 (wallet-measured, PRE-patch)

From cost_decomp.py exact native-balance reconciliation of real trades:

| Component                        | Wallet-verified value        |
|----------------------------------|------------------------------|
| entry+exit base tx fees          | 0.000015 (probe #3: 2 lean txs) |
| Jupiter sweep priority fees      | 0.0002 FLAT per dust sell; bloated trade burned 0.00084 across 4 sells |
| rent leak (orphan ATA)           | 0.001509 (probe #3, recovered manually 09-13) |
| **worst observed lifecycle**     | **~0.0024** (bloated exit + leaked rent) |

So 0.002 was REAL. It was also mostly self-inflicted machinery waste,
not market structure.

## The new 0.00003 (MODEL, post-patch, NOT yet wallet-verified)

Patches committed 09-13:
1. `_jupiter_submit`: flat 0.0002 priority fee → value-scaled
   (0.5% of outAmount, floor 5k lamports, cap 100k)
2. `sweep_to_sol`: dust threshold 0.0005 → 0.003 (dust burned, not sold)
3. `sweep_to_sol`: double-pass ATA close after 20s finality
   (fixes the 0.001509 orphan-rent leak class)

Model assumes: 2 lean LP txs (0.000015) + ~zero sweep cost + full rent
reclaim. **This is an engineering estimate. No live trade has run since
the patches. It is not wallet truth yet.**

## What this means for the size curve

Every row of the size sweep used cost = 0.00003 flat.

- If patches hold:  0.02–0.04 plateau stays mildly positive.
- If true cost is still ~0.002: ALL rows shift down ~0.002 and the
  entire positive curve is illusory (e.g. 0.02 row: +0.000109 → −0.00186).

## Bootstrap stability (2000 resamples of the 30 reflow windows)

win rates: 0.005→7.5%  0.01→8.6%  0.02→13.4%  0.03→14.0%  0.04→10.6%
           0.05→12.9%  0.075→12.4%  0.10→20.6%

NO stable point optimum. Defensible statement only:

> Profitable-capacity PLATEAU appears around 0.02–0.05 SOL on current
> window mix; marginal value turns negative ~0.04–0.05; all point
> estimates within noise of each other (and of 0.1).

## Gate for live promotion (per external review, accepted)

1. Next live probe runs at CURRENT pilot size (0.1 SOL, unchanged) with
   cost_decomp run immediately post-exit.
2. If wallet-measured all-in cost ≤ 0.0001 SOL/trade → patches verified,
   0.00003 model ratified, size ladder results become usable.
3. Only then: test 0.02–0.04 live out-of-sample, paired with full shadow
   ladder + hold-time matrix on every trade.
4. Event-capacity vs capital-efficiency optima computed separately once
   ≥10 verified-cost trades exist.
