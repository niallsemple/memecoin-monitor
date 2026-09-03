# Fast-Entry Size-Scaling Case (0.05 → 0.10 SOL)

Status: CONDITION FAILED — 9Arnb9hN rugged at 55 min (§270). Birth-entry record now 2 green / 1 rug.
Scaling stays OFF at 0.05 SOL. Revisit only after: (a) P_BIRTH_CAP_MIN 30-min cap proves it
converts rugs to small greens across 3+ more birth entries, AND (b) owner approval.

## Evidence: birth-window entries to date

| Mint | Entry | Size | Exit | PnL (SOL) | Peak | Trough (MAE) | Notes |
|---|---|---|---|---|---|---|---|
| E2PGusyR | birth +66s | 0.05 | abort15 | +0.00391 | 1.040 | 0.996 | Never underwater |
| 2oumvUmv | birth +64s | 0.05 | abort15 | +0.00256 | 1.025 | 0.997 | DRAINER_NETWORK_ALERT fired; still closed green |
| 9Arnb9hN | birth +66s | 0.05 | OPEN | — | 1.198 | 0.980 | Past abort30 window, above water |

Record: 2/2 closed green, zero rugs, zero positions below 0.98 at any point.

## Gate selectivity this session

- 7 bundled launches evaluated and skipped at birth (57–62% outsider band)
- 3 entries taken (all non-bundled, clean deployer scorecards)
- Plateau path also blocking: sfDnG9Qw skipped at 60.94% bundled

## Post-promotion live streak (gates blocking, all paths)

- 10 consecutive green closes, net +0.0935 SOL
- Era counterfactual with gates applied: +0.0742 SOL (+3.0% ROI on 2.481 staked) vs −0.2640 actual pre-gate

## Scaling arithmetic

- Had entries been 0.10 SOL: closed PnL +0.0129 vs +0.0065 actual (+2x, obviously)
- No exit decision would have changed: every abort15 fired on time-based rules with price ABOVE water; doubling size does not alter trigger logic (mult-based, not SOL-based)
- Risk: worst observed birth-entry MAE is 0.98 → worst-case doubled loss on this sample ≈ 0.002 SOL; true tail risk is a non-bundled rug (5ogC archetype) → full stake loss, 0.10 vs 0.05
- Wallet ~2.3 SOL → 0.10 stake = ~4.3% of wallet per entry, 2 concurrent max

## Decision rule proposed

Scale to 0.10 SOL fixed for fast_birth entries only (plateau path keeps dynamic sizing) once:
1. 9Arnb9hN closes green (3/3), AND
2. Zero birth-entry rugs on record, AND
3. Owner explicitly approves

## Open risks to state honestly when presenting

- Sample is tiny (n=3). Streaks of 3 happen by chance in this market.
- 5ogC archetype (non-bundled rug, 0% bundle) is still uncatchable — a 0.10 birth-entry into that archetype loses double.
- Graduated-pool entries can fail open on the bundle gate (birth beyond 3000-sig window) — U6XZ7TGQ46 precedent.
