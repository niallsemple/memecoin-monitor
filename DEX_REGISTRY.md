# DEX REGISTRY — Solana venues, program IDs verified ON-CHAIN 2026-09-06
Source seed: Alchemy Solana DEX directory (94 listed) + cross-checked against
screenerbot.io / vybenetwork docs / nolimitnodes. Every ID below was
confirmed with getAccountInfo (executable=true) — no doc-only IDs.

## INTEGRATED (live in our stack)
| Venue | Program | Model | Status |
|---|---|---|---|
| pump.fun bonding curve | 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P | virtual reserves | curve_buy/curve_sell LIVE |
| PumpSwap AMM | pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA | vault reserves CPM | discovery live, exec via Jupiter |
| Raydium CPMM | CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C | vault reserves CPM | §402 quotes live, parity passed |
| Jupiter aggregator | lite-api.jup.ag | router | pool path LIVE |

## TIER 1 — build next (constant-product, same math family as CPMM)
| Venue | Program | Why |
|---|---|---|
| Raydium AMM v4 | 675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8 | VERIFIED. Legacy pools incl. EARLY pump.fun grads (pre-PumpSwap era) — this is where the older dual-listed universe lives. Quote = vault balances; swaps need OpenBook market accounts. |
| Meteora DAMM v1 | Eo7WjKq67rjJQSZxS6z3YkapzY3eMj6Xy8X5EQVn5UaB | VERIFIED. Constant-product dynamic pools; memecoin pairs exist here. |
| Meteora DAMM v2 | cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG | VERIFIED. Newer CP pools (sqrt_price field but CP math). Post-DBC graduations land here. |

## TIER 2 — concentrated liquidity (need tick arrays; defer)
| Venue | Program | Note |
|---|---|---|
| Raydium CLMM | CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK | VERIFIED. sqrt_price Q64.64 quoting; established pairs, deep liq. |
| Orca Whirlpool | whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc | VERIFIED. Same CLMM class. |
| Meteora DLMM | LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo | VERIFIED. Bin-based; big memecoin venue for established runners. |

## BIRTH VENUES — relevant to "see coins earlier" (monitor candidates)
| Venue | Program | Note |
|---|---|---|
| Meteora DBC | dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN | VERIFIED. Dynamic bonding-curve launchpad; grads flow to DAMM v2. |
| Raydium LaunchLab | LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj | VERIFIED. Bonding-curve launchpad; grads flow to CPMM. |

## SKIP
- Phoenix CLOB (PhoeNiXZ8ByJGLkxNfZRnkUfjvmuYqLR89jjFHGqdXY, VERIFIED) —
  order book; no memecoin flow worth the build cost now.
- Orca legacy v1 (9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP, VERIFIED) —
  dead venue, superseded by Whirlpool.
- Sanctum (5ocnV1qiCgaQR8Jb8xWnVbApfaygJ8tNoZfgPwsgx9kx, VERIFIED) — LST
  swaps only, irrelevant to memecoins.
- The remaining ~80 Alchemy-listed "Solana DEXs" are perps, bridges,
  aggregators, or dead/duplicate front-ends — none add executable spot
  liquidity for our pairs.

## Arb-scanner implication
Dual-listed universe for pump.fun grads: PumpSwap × (Raydium CPMM ∪ AMM v4).
Fresh grads are PumpSwap-only; older survivors pick up Raydium pools.
arb_scanner.py already covers CPMM; AMM v4 quote support is the next build.
