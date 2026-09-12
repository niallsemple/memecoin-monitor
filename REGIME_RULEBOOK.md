# HFNA Regime Rulebook — draft 2026-09-12 22:30

Built from 31 wins / 29 strikes / 63 scratches (live + paper, 09-11 → 09-12).

## What does NOT predict outcomes (tested, rejected)
- **Elevation band** — wins avg 34k×, strikes avg 56k×, scratches 20k×. No separation.
- **Pre-entry prot-fee flow** — strikes actually had HIGHER avg flow (2.84 SOL/hr) than wins (2.01). Fat flow attracts entries that then get run over.
- **Pre-entry bin drift direction** — drift<0 avg −0.0009, drift≥0 avg −0.0013. Nothing.
- **Pool identity alone** — GBR produced both the best wins and the mission-killing strikes.

## What DOES hold
1. **Depth ≥1500 SOL is necessary** (live): sub-gate pools went 0-for-everything tonight; gated pools at least produced all 5 wins. But depth alone is not sufficient — gated expectancy tonight was still negative (−0.0103 over 7 post-gate trades).
2. **Every strike is a tripwire** (17/17 paper, all live): price falls through the range before fees accumulate. The loss is decided in the first ~2 minutes AFTER entry, not by anything visible AT entry.
3. **Wins = fee capture during hold > markout at exit.** GBR's +0.018 paper wins were tripwire exits that had already banked fat fees. The fight is hold-period dynamics, not entry timing.
4. **Regime is the meta-filter.** Morning (fat flow, 60k–150k elev GBR): +0.0084-class wins. Evening (thin): everything scratches or strikes. Current regime detector: none — this is the gap.

## Implications for next iteration
- Stop searching for entry-side filters on this dataset — exhausted.
- The lever is EXIT-side speed and REGIME gating:
  - live 15s on-chain tripwire already minimal; paper shows markout dominates.
  - build a regime score: rolling capture30 across watchlist; only arm live when
    trailing 60-min capture density > threshold that preceded morning wins.
- Friction is ~0.0008 SOL/trade (tx + rent timing) — at 0.1 SOL size, expectancy
  must clear +0.8% per trade just to break even. Consider 0.2 SOL size ONLY if a
  regime gate restores positive expectancy (halves relative friction).

## Known data-quality notes
- Paper rows before 20:01 09-12 can show inflated fees (counter-jump artifact,
  e.g. 9yXn +0.302, nBXy +0.141). Cap fix committed; treat pre-fix fat paper
  wins >0.01 as suspect.
- Live real_pnl is wallet-truth; inter-trade rent recovery (+0.0011 x2) lands one
  cycle late and is real money.

## Update 22:35 — regime score backtest (regime.py)
Trailing 60-min prot-fee flow across all snapshotted pools does NOT cleanly
separate wins from strikes at n~100: 9Ndi win at score 0.18, GBR strike at
score 47.2. Fee flow is bursty at 30-min granularity. regime.py now LOGS the
score every poll (regime_log.jsonl) so a larger sample can be tested, but it
is NOT wired as an arming gate — data does not support it yet.
Only the depth gate (>=1500 SOL) has survived validation.
