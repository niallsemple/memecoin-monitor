# Memo #37 evaluation — "High-Fee No-Arbitrage Window" (HFNA)

Core thesis: hunt **high fee + price already correct + low active liquidity** — the gap
between the protocol's volatility memory and current adverse-selection risk.
Measure net $ per capital-second, not APR.

## What we verified against our stack

| # | Idea | Status against our infra |
|---|------|--------------------------|
| 1 | Adaptive-fee aftershock (Orca) | REAL: adaptive_fee instructions confirmed in deployed Orca source (our audit). Meteora DLMM has same structure (volatility accumulator decay). Testable via fee-rate snapshots post-spike |
| 2 | DAMM v2 scheduled fee cliffs | TESTABLE NOW: we collect damm_v2_fee_snapshots.jsonl — scan for pools with time-scheduled fee configs |
| 3 | Raydium CPMM pre-open deposits | Documented real behaviour. High-risk arm; would need launch screening (we have farm_denylist machinery). Paper-testable |
| 4 | DLMM fee-bearing limit orders (50% split) | Real. Capital-efficient only if we want the directional fill anyway |
| 5 | OnlyY fee mode (fees in quote/SOL) | HIGH VALUE FOR US: directly serves our SOL-only exit rule — fees never arrive as token-X. Scan pool configs for collect_fee_mode |
| 6 | Tail-bin shock absorber | Partially what wide arm does; single-sided far-bin version untested |
| 7 | Liquidity vacuum harvesting | MEASURED (vacuum_lab): 136 events/2.6h, depth to 21%, refill 140s median. Real and frequent |
| 8 | Reward-density sniping | Needs reward emission data per pool; Meteora API has it. Medium build |
| 9 | Cross-AMM LP-yield arb | Natural extension of ranker across venues; needs Raydium/Orca fee tracking |
| 10 | Hot grid (persistent position infra) | Meteora positions are fixed-range (no re-range); Orca reset_position_range allows it. Rent cost per pre-made position ~0.057 SOL |

## Priority (cost-to-test order)
1. vacuum_lab refinement (have data) — add bin-drift-flat gate measurement
2. OnlyY pool scan (few RPC calls on tracked pools)
3. DAMM v2 fee-scheduler scan (have snapshots)
4. Adaptive-fee decay curve measurement (Meteora vol accumulator readable on-chain)

## Test results (2026-09-12)

**Idea 7 (vacuum harvesting): CONFIRMED measurable, abundant.** vacuum_lab + hfna_scan:
136-140 vacuums/2.6h, 96% settle into HFNA windows, median window 12.6min, ~51 windows/hr
across 11 pools. Fee leg (vol accumulator) now captured per snapshot; scoring next.

**Idea 2 (DAMM v2 scheduled fee cliffs): FALSIFIED on 24,554 snapshots / 12,565 pools.**
298 cliff events exist, but they occur on dead launchpad bonding curves decaying from
~45%->35% fees — no router sends flow at those rates (vol30 ~0 before AND after).
Cliffs landing at routable levels (<=5%): only 4 ever, on dust TVL ($2 pool), no LP
opportunity. The memo's "volume 10x after cliff" premise does not appear in this data.
Cost: zero. Lane closed unless tested on non-launchpad DAMM v2 pools with real flow.

**Idea 5 (OnlyY fee mode on DLMM): NOT AVAILABLE on current pools.** The deployed
LbPair layout (verified live on KNOTS pool + saved IDL) has no collect_fee_mode field —
it's a newer-program feature. Our SOL-only exit rule stays handled by guardian sweeps.
Could re-check if/when Meteora migrates pools to the new layout or via DAMM v2.

**Idea 7 follow-up: fee leg instrumented.** bin snapshots now carry vol_accum/vol_ref/
var_fee_ctl/base_factor per pool. KNOTS currently runs vol_accum ~2x reference (elevated).
