# LIVE CALIBRATION PROBE RUNBOOK — reflow-style, 0.1 SOL, one trade

Status: ARMED BUT NOT APPROVED. Requires explicit owner go. Live trading is
halted (hfna_live_state.json halted=true); this probe does NOT clear that —
it is a single manually-executed trade outside the halted engine.

## Purpose
Resolve the paper-fidelity question: do paper fee captures (prot_fee delta
model) match on-chain claimed fees for the same window? Paper dead fills
are suspected to be partly claim-reset artifacts. One live trade answers it.

## Preconditions (ALL must hold at trigger time)
1. Owner has explicitly said go for THIS probe.
2. `STOP_LIVE_TRADING` file absent.
3. Wallet balance >= 1.0 SOL (probe uses 0.1; keep rent+fees buffer).
   Check: `node lp_exec/meteora_lp.bundle.cjs balance`
4. Target pool passes reflow gates live:
   - tx tape: swaps_5m >= 75 (fresh row < 150s old in txflow.jsonl)
   - vacuum: liq_active <= 60% of ~300s ago
   - settle: drift <= 5 bins over adaptive window
   - capture30 >= 4x FIXED_COST; tax_bps <= 50; not denylisted
   - preferred pools: 9Ndi (best payer) or GBR (deepest) — take whichever
     triggers first; do not force a specific pool.

## Execute
1. Record pre-state:
   `node lp_exec/meteora_lp.bundle.cjs balance > probe_pre_balance.txt`
   Note active bin from latest bin_snapshots.jsonl row for the pool.
2. Enter (3 bins below active, mirrors paper Y-only range):
   `node lp_exec/meteora_lp.bundle.cjs addbins <POOL> 0.1 3 probe1`
   Save stdout/tx signature to probe1_entry.txt.
3. Monitor every poll cycle (normal poll loop). Paper reflow arm runs the
   same window simultaneously — its state IS the comparison baseline.
4. Exit triggers (whichever first):
   - liquidity refilled (liq_active > 1.5x trough), or
   - fee decay (vol ratio < 1.2), or
   - tripwire: active bin < low - 1 (take the markout, do not chase), or
   - 30 min timeout.
5. Exit + claim:
   `node lp_exec/meteora_lp.bundle.cjs claim <POOL>` (claim BEFORE exit so
   fees are collected; then) `node lp_exec/meteora_lp.bundle.cjs exit <POOL>`
6. Sweep: verify wallet holds SOL only (except known unclosable Token-2022
   dust ATA). Any stray token -> swap to SOL via the same bundle's exit path
   or Jupiter before reporting done.
7. Record post-state: `balance` again; compute actual P&L =
   post - pre + 0.0 (all fees included by balance delta).

## Compare (the actual experiment)
- paper reflow trade for same pool+window: fees_paper, net_paper
- live: claimed fees from claim tx + balance delta
- Verdict A: |fees_live - fees_paper| < 30% -> paper model is faithful;
  reflow paper expectancy (+0.0005/tr class) is a real signal. Scale debate opens.
- Verdict B: fees_live >> fees_paper on a paper "dead fill" -> claim-reset
  artifact confirmed; paper UNDERSTATES; re-run expectancy with corrected
  accounting before any live sizing.
- Verdict C: fees_live ~ 0 while tape showed flow -> placement leak is real
  on-chain too; fixed ranges are dead, repo/reflow follow is mandatory.

## Abort conditions
- Any tx failure twice in a row -> stop, report, no retry loop.
- Wallet balance < 0.5 SOL unexpectedly -> stop everything, report.
- Price gaps >10 bins below range at entry -> do not enter; wait next window.

## After the probe
- Wallet must end SOL-only. Verify with `balance` and token accounts list.
- Commit probe artifacts (entry/exit tx, balances, comparison) to git.
- Report: paper vs live delta, verdict A/B/C, recommendation.
