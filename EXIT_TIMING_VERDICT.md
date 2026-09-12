# Exit-Timing Verdict — 2026-09-12 23:05 UTC

Question: can earlier/better exits turn the depth-gated LP strategy positive?

Dataset: 44 trades (32 live real-friction + 12 paper post-fix), 8,284 bin
snapshots at ~64s cadence.

## Findings

1. **Early exit at d=2 bins (active bin drops 2 from entry, before price
   reaches our range → no conversion, no IL, friction-only −0.0008) cuts
   losses 92%**: −0.0779 → −0.0059 over 44 trades. Essentially breakeven.

2. **Liquidity-veto refinement fails.** Dips-that-recover show active-bin
   liquidity collapse (mean liq ratio 0.073 = vacuum snap-back); real strikes
   keep liquidity (0.684 = genuine sell pressure). But 4 of 14 strikes also
   show vacuum-like dips (−0.0148 kept), so vetoing the exit on low-liquidity
   dips nets *worse* (−0.0133) than plain d=2.

3. **Oracle ceiling: +0.0051 (+0.00012/trade).** Even PERFECT strike
   avoidance — exit every strike at friction, keep every win — barely clears
   zero. Win sum +0.0312 over 30 non-strike trades ≈ +0.00055 avg vs 0.0008
   friction. **Exit timing cannot make this strategy positive. The binding
   constraint is fee capture per trade, not strike avoidance.**

## Consequences

- Wire d=2 early exit into engines anyway: converts bleed → ~breakeven,
  buying time for free while the entry side is fixed.
- Positive ROI must come from the entry side: higher fee capture per minute
  in range. Levers: (a) pool selectivity by fee velocity at entry (regime
  log now accumulating exactly this), (b) position sizing relative to pool
  depth, (c) longer in-range survival (wider ranges trade fee density for
  survival — needs its own replay), (d) fewer, better-timed entries
  (post-vacuum timing already helps: elev gates).

Runners: `replay_early_exit.py`, `dip_signature.py` (both committed).
