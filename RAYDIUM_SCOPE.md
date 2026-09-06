# RAYDIUM SCOPE — Direct CPMM Integration (drafted 2026-09-06)

## Why
Today we trade two venues directly (pump.fun curve, PumpSwap AMM) and reach
everything else only through Jupiter's aggregator. Jupiter gives best-price
execution but can NEVER see a price gap — it internalizes it. A direct
Raydium CPMM path unlocks:
1. **Second execution venue** for graduated tokens (redundancy vs Jupiter
   outages / quoting failures — we've been bitten by Custom 6024).
2. **Two-venue arbitrage detection** (PumpSwap vs Raydium on the same
   token) — read-only first, execution only after measured evidence.

## Verified facts (web research 2026-09-06)
- CPMM program ID: two conflicting values found in sources —
  `CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C` (bloXroute docs, cited
  twice) vs `CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHS4K9uP6eh` (low-quality SEO
  page). **MUST verify on-chain before any live use** (getAccountInfo on a
  known CPMM pool, check owner). Never trust docs alone for program IDs.
- Swap instruction (Anchor `swap_base_input`): 14 accounts — payer(signer),
  authority PDA, amm_config, pool_state, input ATA, output ATA,
  token_0_vault, token_1_vault, token_program_0, token_program_1, mint_0,
  mint_1, observation_state.
- Reserves are NOT in pool state — read the two vault token account
  balances (getTokenAccountBalance / parsed getMultipleAccounts).
- Fee: `trade_fee_rate` from amm_config (per-million). Standard quote:
  `out = in_eff * reserve_out / (reserve_in + in_eff)` where
  `in_eff = in * (1_000_000 - fee) / 1_000_000`. Typical tiers 0.25%–4%.
- Token-2022 mints may carry transfer fees — check mint extensions before
  sizing sells (same class of bug as our §223 balance overstatement).

## Build plan (fits existing live_trader.py plumbing)
1. **`raydium_cpmm.py` module** (root-module, live-loads like liq_health):
   - `POOL_PROG` constant (verified on-chain first)
   - `find_pool(mint)` — Helius getProgramAccounts w/ memcmp on mint
     offsets, cached to `raydium_pools.json` (gPA is expensive; cache forever,
     pools are immutable)
   - `pool_state(mint)` -> reserves via vault balances + fee from config
   - `quote_sell(mint, tokens_raw)` / `quote_buy(mint, sol)` — pure math
2. **Execution** — raw v0 tx builder reusing the existing compile/sign
   block (live_trader.py ~L557, `_sign_versioned_tx`). wSOL wrap/unwrap
   ixs around the swap. `min_out` at 85% of quote (matches curve_sell).
3. **Dry-run first** — `live_enabled()` gate identical to curve/pool
   paths; log quotes vs Jupiter quotes for the same mint/size to validate
   accuracy before any real submit.
4. **Arb scanner (phase 2, separate file)** — for graduated tokens on both
   venues: compute executable buy->sell round trips net of ALL fees
   (0.25% CPMM + 0.25% PumpSwap + priority fee + ATA rent). Log
   `arb_candidates.jsonl` when net gap > 0.5%. Read-only until owner
   promotion, same discipline as H16 shadow.

## Costs / risks
- Helius quota: pool discovery is the heavy call; caching keeps it ~1
  call per NEW mint only. Fits the 10M/month tier.
- Compute: CPMM swap ~50k CU — fine with existing priority-fee block.
- Failure modes: wrong program ID (mitigated by on-chain verification),
  Token-2022 transfer-tax mints (checked before sizing), stale reserves
  (always re-read vaults in the same block as quote).

## Acceptance test
- Quote parity: for 5 graduated tokens, |raydium quote - jupiter quote|
  < 1% at 0.05 SOL size.
- One dry-run swap builds + simulates clean (simulateTransaction).
- Arb scanner produces a week's log before any execution is proposed.
