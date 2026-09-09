# DARWIN Scaling Ladder — PRE-REGISTERED 2026-09-09 (§398)

Locked before the 10-trade newborn sample completes. No threshold may be
loosened after a rung's data exists; tightening is always allowed. Every
rung change is an owner decision informed by the pre-registered numbers —
nothing auto-scales.

## Newborn momentum cell (PumpSwap, currently 0.10 SOL/trade)

| Rung | Size | Unlock condition (all must hold) | Kill criterion (any) |
|------|------|----------------------------------|----------------------|
| R0 (now) | 0.10 SOL | — live, sample trades 3–10 pending | §397 STOP at n=10 |
| R1 | 0.20 SOL | n=10 §397 SCALE verdict; sell slippage ≤2% realized on rung-0 exits (measured +0.02% today) | any 2 consecutive full losses, OR rung net ≤ −0.40 SOL |
| R2 | 0.40 SOL | 10 more trades at R1 with net > 0 AND rug rate ≤ 40% | rung net ≤ −0.80 SOL, OR realized sell slippage > 3% on any exit (size outgrowing pool depth) |
| R3 | 1.0% of wallet per trade | 20+ trades at R2 with PF ≥ 1.3 | PF < 1.0 over trailing 20 trades |

Rung reviews are computed by review_live.py extension per rung (same
pre-registered structure as §397). Max concurrent newborn positions: 1
(current behavior; do not parallelize before R2).

## LP arms (Meteora DLMM, wide_arm_v2)

| Rung | Per-arm size | Unlock condition | Kill criterion |
|------|--------------|------------------|----------------|
| L0 (armed) | ≤1.0 SOL (12% wallet cap) | pool passes two-tier watchlist gates (§393/§394) + T-2022 audit (§395) | guardian floor/TVL/blacklist exits (live) |
| L1 | up to 2.5 SOL | first L0 arm completes 3 days with realized net ≥ 50% of projected | realized net < 0 after 3d incl. exit costs |
| L2 | up to 5.0 SOL | two consecutive profitable L0/L1 arms AND forward yield-decay measured on ≥5 tracked pools | any tier-A pool floor breach with loss > 5% of arm |

## Cross-system rules

- Total capital at risk (open positions + LP arms) never exceeds 50% of wallet.
- Every scale-up adds its rung review to REPORT.md before the first trade at
  the new size.
- A regime break (farm flow ends) does NOT change rungs — it only un-stalls
  sample accumulation at the current rung.
- If both systems are live simultaneously, the newborn cell has priority for
  deployable balance (it is the edge under test; LP is the yield park).
