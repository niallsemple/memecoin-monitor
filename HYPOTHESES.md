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

## Research-branch hypotheses (from docs/DARWIN_OBSERVATORY.md)

| ID | Hypothesis | Status |
|----|-----------|--------|
| H7 | Rug probability is learnable from first-5-minutes trading data (arXiv 2608.20271: GBM on 6.4M tokens). abort3_if_red is our 1-feature proof; a full classifier may cut rug rate below 1.1% breakeven | NEW — validates H2 direction |
| H8 | Mechanism labels (Mayhem/Agent/CTO/cashback) partition the training set into different market species; mixing them creates false signal | **AUDIT DONE 2026-09-05: 0/36 traded mints were Mayhem (2B supply)**; live `mech` label on eval rows from §334 |
| H9 | Realisable MFE (insert own tx into curve reserves, recompute path) vs tape-price MFE | NEW — note: live PIs already measured (0.1–1.4%); historical replays remain tape-price |
| H10 | Attention/visibility state (Pump Movers/New rank transitions) precedes volume acceleration — closer to cause | NEW — needs Pump API data source |
| H11 | Economic-entity PnL (creator fees 0.30%, MEV rebates, cashback) reorders which actors are "smart money" vs swap-PnL | NEW — winner_wallets registry is swap-PnL only |
| H12 | Value-of-Information ladder: measure incremental OOS net EV per info layer (price → flow → wallets → entity graph → mechanism → visibility → latency → social) | NEW — organizing experiment for research budget |
| H13 | First-passage formulation P(+20% before −8%) beats raw return prediction as target | NEW — abort3 is already a first-passage discriminator |
| H14 | Structural discontinuities (graduation, fee-tier crossing, Mayhem termination, agent buybacks) are easier edges than smooth patterns | **TESTED §393: graduation discontinuity is real but NEGATIVE for buyers (median 0.20x at +60m, 66% husks). Post-grad momentum buying RETIRED; only ultra-high curve-activity cohort approaches breakeven. Short-side edge not expressible on memecoins** |

## Infra audit note (2026-09-05)
- Jito ShredStream shut down TODAY (Sept 5, 2026) per Jito docs — our feeds are Helius WSS + pump portal WSS, not ShredStream. No action, but transport audit logged.
- Observation-vs-chain-time: ledger already carries both `t`/`ts`; a full forensic tape (preconf→decision→landing ns timestamps) is the research-branch data layer.
