# memecoin-monitor

**A three-week, real-money research campaign hunting for a positive-ROI trading edge on Solana memecoin markets — with the full evidence trail, live-trade ledgers, and the honest answer we found.**

Everything here was measured with real SOL on mainnet, not vibes. ~140 live buys, 17 LP probes, 1,400+ forward paper trades, 8 strategy arms, every falsification recorded.

## The question

Can a small, self-built stack (no HFT infra, public RPCs + one Helius key, ~2–7 SOL stake) find and capture repeatable positive ROI in Solana memecoin markets — momentum, LP fees, arbitrage, liquidations, or market-structure edges?

## The answer (so far)

**No arm survived contact with real money in the Sep-2026 regime.** The campaign scoreboard:

| Arm | Live record | Verdict |
|---|---|---|
| `fast_birth` sniping | 53 buys, −10.3%/unit | RETIRED |
| `s60nm5fr` momentum (E25) | 65 buys, −5.3%/unit | RETIRED — paper said +3.3%/trade over 1,387 closes |
| `e2` graduation bridge | 17 buys, 17/17 panic exits | RETIRED |
| PumpSwap momentum cell | 2 buys, −0.084 SOL (1 atomic rug) | Evidence-first rebuild in progress (dry) |
| LP fee-skimming (Meteora DLMM) | 17 probes, ≈ −0.0002 SOL/probe | FALSIFIED |
| LP wide ranges | 0/3 | FALSIFIED |
| LP deep-pool scaling (SOL-USDC) | IL ≫ fees at 0.1–500 SOL | FALSIFIED |
| LP flat-harvest timing | 36 backtest windows → 0 under excursion guard | FALSIFIED (net-drift artifact) |
| Arbitrage / liquidations | thin frontier, negative cycle cost | FALSIFIED (see REPORT.md §481–490) |

## The structural lesson

Every paper edge evaporated on live contact, and the gap was never detection quality — it was **execution economics**:

- **Slippage on thin pairs** turns +3% paper expectancy into −5% live
- **Atomic rugs** drain pools between snapshots; stop-losses drawn on 30s–5min data don't exist on-chain
- **IL outruns fees** by 10–100× whenever price drifts at all; scaling up doesn't fix it because IL scales linearly too
- **Backtest artifacts hide everywhere** — our best-looking LP result (+0.032 SOL/49h) was entirely round-trip price chop misread as "flat" until an excursion guard killed it

Detection is not the bottleneck. Fills are.

## What's in here

- `REPORT.md` — the full lab notebook: 490+ numbered sections, every experiment, every verdict, every dead end
- `FINDINGS.md` — the condensed falsification trail and campaign scoreboard
- `live_trader.py` — battle-tested executor: Jupiter path, local Ed25519 signing (wallet secret never leaves the machine), dynamic priority fees, farm/deployer/bundle blocking, one-trade-per-mint, SOL-only enforcement
- `lp_surf_live.py` + `regime_edge.py` + `regime_paper.py` — the LP-skimming controller, the fee-vs-IL regime detector, and its forward paper ledger
- `pumpswap_live.py` + `pool_reserve_poller.py` — momentum cell with atomic-rug drain tripwire
- `feed_keeper.py`, `bin_collector.py`, `birth_watch.py` — data plane: births, bin snapshots, reserve vaults, tape
- `sweep_to_sol.py` — wallet hygiene: sells/burns residual tokens, closes ATAs, enforces SOL-only

## Current state

All live arms are gated off by their own evidence (a system re-arms only with a fresh positive dry record at n≥30 **and** explicit owner sign-off). Zero-cost watchers keep running: dry momentum cell, regime tripwire, paper LP ledger, birth feed.

## Safety notes

- `live_wallet.json` and `helius_key.txt` are gitignored and have never been committed
- Every live system checks a `STOP_LIVE_TRADING` kill-switch file each cycle
- Wallet policy: end every operation SOL-only; dust is burned, ATAs closed

## License / use

Research code, shared as evidence. Not investment advice; nothing here made money. If you find a way to make it make money, the ledger format is ready for your entry.
