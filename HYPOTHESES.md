# DARWIN Hypothesis Registry (Phase 12 meta-learning)

Status ladder: NEW → TESTING → PROMISING → SURVIVED OOS → FORWARD TEST → LIVE CANDIDATE → LIVE ·· FAILED ·· RETIRED

| ID | Hypothesis | Mechanism | n | In-sample | OOS / forward | Exec-adjusted | Status |
|----|-----------|-----------|---|-----------|---------------|---------------|--------|
| H1 | Birth-window entries gated by deployer prior + bundle outsider% + §300 selective-winner override catch coins with genuine demand | Winners' early buys signal organic flow | 32 | +0.031 pre-wipeout era | 3 wipeouts in 32 (9.4% rug rate) → −0.262 book | Fees ≈0.0015/tx, buy PI 0.11–1.36% | **LIVE but −EV without H2** |
| H2 | **abort3_if_red**: red at minute 3 → exit immediately | Insiders suppress price while staging drains; genuine demand lifts price within 3 min | 32 replay + 3 shadow | +0.008 vs −0.262 actual | Shadow 3/3 (1 CUT→rugged −100%, 2 KEEP→green +0.5%/+1.7%) | Fee-neutral (same exit count) | **FORWARD TEST (shadow) → LIVE CANDIDATE, awaiting owner promotion** |
| H3 | Flat aborts at 5/6/7/8min fix rug risk | Early exit dodges drains | 32 replay | −0.002 to +0.004 gross | — | Net-negative after fees; forfeits 85% of winner upside | **FAILED (§326)** |
| H4 | Winner-wallet presence alone discriminates rugs from winners | Smart money avoids rugs | 32 | Both rugs had winner wallets present | — | — | **FAILED as standalone; retained as entry gate only with H2 as backstop** |
| H5 | s60nm5fr hook (graduated-pool entries) finds edge after graduation | Post-graduation survivors have different rug profile | 0 live fills | — | 3 live attempts, all blocked by §262 (bundled 60–61%) | — | **TESTING (no fills yet)** |
| H6 | deployer_pct / insider_overhang as gating inputs | High insider share predicts rugs | — | ⚠️ constant 79.31 on all rows — **sensor broken** | — | — | **DATA BUG — fix before trusting §262/insider gates** |

## Framework adoption notes (docs/DARWIN_TRAINING_LAB.md)
- Blind replay = shadow mode (already live, H2 evidence accumulating automatically)
- Outcome labels = peak_mult (MFE) + trough_mult (MAE) per §263; extend with time-to-+X% when tape budget allows
- Execution reality = per-trade PI logging + wallet-vs-ledger fee audits (done, fees not corrosive)
- Regime analysis (Phase 10) = not yet instrumented — candidate next experiment
- Isolation rule: research-branch discoveries stay shadow/paper until they survive unseen-data forward testing — H2 is the first candidate through this pipeline

## Current verdict: PROMISING (H2) — system overall in FORWARD TESTING
