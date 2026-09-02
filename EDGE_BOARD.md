# SOLANA EDGE BOARD

Owner brief: `docs/edge_research_brief.md` (2026-09-02). Objective extension:
map every repeatable source of economic edge on Solana, then try to kill each one.
Prioritise mechanisms where the economic reason for the edge can be stated FIRST.
Real friction floor: Pump.fun 1.25% fee + slippage + priority fee + Jito tip +
failed-tx cost — ignore any gross edge under ~1%.

Status pipeline: DISCOVERY → TESTING → SURVIVOR → FORWARD TEST →
LIVE CANDIDATE → VERIFIED EDGE → KILLED

| # | Hypothesis | Mechanism | Status | Our assets / notes |
|---|-----------|-----------|--------|--------------------|
| 1 | s60nm5fr memecoin momentum (CURRENT LIVE) | Structural: early net-buyflow breadth on fresh graduates | **LIVE** (34 closes, 91.2% green, panic cohort +3.63%/trade) | tracker + live_trader; verdict at 40 closes |
| 2 | s60nm5mbfr combined gate | Same + dust-buy & funded-reject filters | FORWARD TEST | shadow deployed §171, live-stack mirror §173 |
| 3 | Creator/funding-graph rejection | Info: funded-wallet trees pre-rug | **LIVE** as funded_reject filter (§98a/§100/§105) | mfg_funding.jsonl, CHAIN_WATCH, self-blacklist |
| 4 | Dust-buy fake breadth | Info: sybil grind-rug signature | FORWARD TEST (mb shadow +1.41%) | med≥0.25 filter, fitted on B9tN |
| 5 | Pump.fun survival/graduation model | Structural: deterministic curve → predictable events | TESTING (baserate.py, lifecycle.py exist) | 966 tokens tracked/run, 372 births/run |
| 6 | Smart-wallet discovery + lead/lag | Info: repeatable-wallet edge | DISCOVERY (wallet_intel.py, wallet_firstbuyers.py exist) | needs realized-PnL leaderboard build |
| 7 | Wallet clusters (on-chain consensus) | Info: N independent smart wallets converge | DISCOVERY (cluster_*.py exist) | needs §6 first |
| 8 | Pump exhaustion (fade late-stage) | Behavioural: new money stops replacing exits | DISCOVERY | pool-trade tape already collected (50k/run) |
| 9 | Atomic cross-DEX arbitrage | Microstructure: same token, two prices | DISCOVERY | needs pool-state reconstruction + Jito bundle econ; 50ms tick = execution problem |
| 10 | Liquidation cascade continuation/exhaustion | Forced flow: liquidations aren't optional | DISCOVERY | needs perp data source (Drift/Hyperliquid?) |
| 11 | Graduation alpha (pre/post migration) | Structural: liquidity migration repricing | DISCOVERY | tracker sees migrations=13/run already |
| 12 | Early-holder topology (true independent holders) | Info: fake decentralisation | DISCOVERY (holders.py exists) | funding-graph join needed |
| 13 | Bundled-launch detection | Info: coordinated same-slot supply control | DISCOVERY (bundle_screener.py exists) | |
| 14 | Executable-liquidity vs mcap illusion | Microstructure: real exit depth | DISCOVERY | Jupiter quotes give this cheaply |
| 15 | LP ROI regimes (fee yield > IL + adverse selection) | Yield | DISCOVERY | needs pool fee/IL data |
| 16 | Priority-fee / Jito-tip optimisation | Execution: min fee to land | DISCOVERY | relevant once #9 or latency edges survive |
| 17 | Execution-delay sensitivity mapping | Execution: how fast must we be? | DISCOVERY | applies delay ladder to any candidate |
| 18 | Cross-asset lead/lag (BTC→SOL→memes) | Behavioural rotation | DISCOVERY | xchain_*.py exist (BSC work paused) |
| 19 | Pump velocity/acceleration features | Behavioural: acceleration > momentum | DISCOVERY | derivable from existing tape |
| 20 | Trade-size information (skill × conviction) | Info | DISCOVERY | needs §6 leaderboard |

## First five experiments (from brief, ordered)
1. Smart-wallet + cluster lead/lag (#6+#7)
2. Pump.fun survival/graduation (#5+#11)
3. Pump exhaustion (#8)
4. Atomic cross-DEX arb + Jito economics (#9+#16+#17)
5. Liquidation cascades (#10)

Kill criteria per brief: no look-ahead data, all costs included, walk-forward OOS,
latency ladder where relevant, reject tiny-winner-count or unrealistic-fill results,
find the cheapest disproving experiment first.
