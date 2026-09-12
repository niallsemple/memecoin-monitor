# Gate-Combination Expectancy Verdict — 2026-09-12 22:52 UTC

Dataset: 32 live trades (real wallet friction; 1 reconciled artifact excluded —
GBR 16:56 UTC "−0.1421" was a mid-settlement wallet read after an expired exit
tx; proceeds were swept back, per `real_pnl_corrected`) + 12 paper trades
post fee-cap fix (20:03 UTC). Regime log sparse (10 rows), informational only.

## Result

| config | n | wins | net (SOL) | expectancy/trade |
|---|---|---|---|---|
| depth≥1500 & elev≥10000 | 7 | 3 | +0.0047 | **+0.00067** |
| depth≥1500 & elev≥100 | 13 | 5 | +0.0038 | +0.00029 |
| depth≥1500 pools | 25 | 10 | −0.0124 | −0.00050 |
| live only (all) | 32 | 11 | −0.0387 | −0.00121 |
| ALL (no gate) | 44 | 14 | −0.0779 | −0.00177 |
| NOT depth≥1500 | 19 | 4 | −0.0654 | −0.00344 |

No hour-of-day bucket clears +0.002/trade (best: 13:00 UTC at +0.0013, n=4).
Regime flow at entry: only 3 matched samples, all losses — no signal either way.

## Verdict

**No gate configuration demonstrates positive expectancy after friction at any
statistically meaningful sample size.** The two nominally positive configs
(n=7 and n=13) have expectancy (+0.0003–0.0007) *below* per-trade friction
(~0.0008 tx+rent) — i.e., indistinguishable from zero, and a single scratch
loss erases 7–15 trades of their edge.

Consistent with REGIME_RULEBOOK.md: nothing observable at entry (elevation,
flow, pool identity, hour, drift) separates wins from tripwire strikes. The
losses are structural — price migrates through our bin within ~2 min on
strikes, before fees accumulate; wins are the times it doesn't.

## Implication

Live resume with current gates = expected slow bleed (~−0.0012/trade × trade
rate). The only configurations that might work need a *different* edge source
(better strike avoidance or higher fee capture per minute in-range), not a
re-tuning of entry gates on this dataset.

Runner: `python3 gate_expectancy.py` (auto-excludes reconciled artifacts,
paper restricted to post fee-cap fix rows).
