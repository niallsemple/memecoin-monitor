
## 2026-09-13 capacity branch falsified (deep SOL-USDC)
Ran capacity_pnl.py on 5rCf1DM8 ($5.1M TVL) and HTvjzsfX ($360k) with live snapshot data.
Result: IL drag >> fee capture at EVERY size (0.1 -> 500 SOL), both pools, 1h and 6h windows.
- 5rCf1DM8 1h: pool fees 1.42 SOL/h, SOL +0.48% -> at 50 SOL: +0.0014 fees vs -0.120 IL = -0.119 net
- HTvjzsfX 6h: at 50 SOL: -0.189 net
Fee/TVL velocity (~0.003%/h on position at 0.1% share) cannot outrun any SOL price drift.
Scaling up does NOT fix the 0.05-scale problem: IL scales linearly, fixed costs were never the dominant term.
Condition for viability: fee velocity/TVL must exceed price drift per unit time — a regime detector
should watch this ratio. Branch CLOSED pending regime change.

## 2026-09-13 regime-edge backtest (49h snapshot history)
regime_edge_backtest.py replays the detector's ratio over history and scores
hypothetical positions (share capped at 5% of active bin after finding a
liq_active artifact — collector briefly reports tiny liq on bin flips; raw
outlier was +0.68 on one 3-min window, discarded).
Result at 0.05 SOL: 36 favorable windows, +0.0319 SOL combined.
  EMBER-SOL +0.0218 (6 windows), EMBER-USDC +0.0113 (7) — all others ~0 or -.
At 1.0 SOL: +0.329 / 49h (scales ~linearly).
KEY INSIGHT: paying windows are ratio~999 = fee bursts while price is FLAT
(1-5 min holds). Live gate v2 preferred drift>=0.1% — we were entering on
IL, not on harvest. Entry rule should prefer flat-price fee bursts.
NEXT: forward-validate with a paper ledger on live data before any SOL.

## 2026-09-13 flat-harvest parameter sensitivity (grid)
EDGE_MIN x SUSTAIN grid (1.0-5.0 x 1-3), same 49h: ALL 15 combos net positive
(+0.006 to +0.039 SOL at 0.05). Not overfit to 1.5/3.
Pattern: SUSTAIN=1 -> most windows (118-132) but least profit (fixed-cost bleed
on marginal entries); SUSTAIN 2-3 sweet spot. Paper ledger currently enters on
first detection (SUSTAIN=1-equivalent) — expect more trades, lower per-trade
yield than backtest headline.
Caveat: all combos share one 49h regime sample; forward validation decides.

## 2026-09-13 FLAT-HARVEST FALSIFIED by excursion guard
Original ratio used NET price drift over 1h for il_rate. Adding excursion
guard (il_rate uses max deviation from window start, not net drift):
favorable windows collapse 36 -> 0 across all pools over 49h. Every "paying"
window was round-trip chop: price oscillated, net drift ~0, ratio read 999,
but a real position would have eaten IL. The +0.032/49h backtest edge was an
artifact of the flatness definition, now removed from regime_edge.py,
regime_paper.py and regime_edge_backtest.py (all three consistent).
Paper ledger reset; continues under strict rule. LP_MULT=9 confirmed
structural (Meteora 10% protocol fee), not the weak link.
Status: ALL LP-skim branches falsified in this regime. Detector stays live —
if a window ever qualifies under excursion-strict rules it is genuinely flat.

## 2026-09-13 momentum-cell qualification rate + replay
Entry gates (age<=0.5h, liq>=$25k, vol_5m>=1x liq, buys>sells) qualify 0.17
mints/h over 131h of snapshots -> n>=30 dry entries needs ~7.5 days.
Replaying exit rules on the 22 historical qualifiers: 73% win, +8.9%/trade.
CAVEATS: assumes clean fills at rule prices; 30s-5min snapshot cadence cannot
see atomic rugs (live cell record: n=2, -42%/trade, one atomic drain blew
through the -40% stop). Replay vs live gap matches the E25 pattern
(paper +3.3% -> live -5.3%). Verdict: replay justifies continued DRY
evidence-gathering only; no live re-arm without n>=30 dry + slippage proof.
Cell loop running (feed + dry watcher, 60s).

## 2026-09-13 CAMPAIGN SCOREBOARD — 3 weeks, all arms, final accounting

LIVE MONEY (wallet funded 2026-09-01, all systems):
| Arm | Live record | Verdict |
|---|---|---|
| fast_birth | 53 buys, -0.412 SOL (-10.3%/unit) | RETIRED §459 |
| s60nm5fr momentum (E25) | 65 buys, -0.405 SOL (-5.3%/unit) | RETIRED §459 — paper +3.3% did NOT survive fills |
| e2 bridge | 17 buys, ~-0.20 SOL, 17/17 panic exits | RETIRED §459 |
| pumpswap_momentum_cell | 2 buys, -0.084 SOL (1 atomic rug) | ONLY armed system; evidence-first; dry sample rebuilding |
| LP-skim 0.05 probes | 17 probes, ~-0.0034 SOL, expectancy ~-0.0002 | FALSIFIED |
| LP wide ranges | 0/3 | FALSIFIED |
| LP deep-pool scaling | IL >> fees at 0.1-500 SOL | FALSIFIED (capacity_pnl, live data) |
| LP flat-harvest timing | 36 backtest windows -> 0 under excursion guard | FALSIFIED (net-drift artifact) |

PAPER-ONLY lanes: v2-v6 books all negative (best v5 -3.9%); arb exotic
frontier THIN (§486); liquidation arm negative cycle cost (§489).

STRUCTURAL LESSON: every paper edge (E25 +3.3%, cell replay +8.9%, LP
backtests) evaporates on live contact. The gap is fills: entry slippage on
thin pairs, atomic rugs between snapshots, IL during any price drift.
Detection quality is not the bottleneck — execution economics are.

CURRENT ZERO-COST WATCHERS (all verified writing 2026-09-13 22:16):
cell dry watcher + reserve drain tripwire (rug-honest exits, n->30 in ~7.5d),
regime-edge tripwire (excursion-strict), dual-book LP paper ledger,
router walk-forward, birth feed (1,233 births/24h tracked).
Wallet SOL-only ~7.30 SOL. Live arms self-gated off by their own records.

## 2026-09-13 23:20 — CAMPAIGN SHUT DOWN by owner
All SOL withdrawn (7.201505 SOL -> owner address, confirmed). STOP_LIVE_TRADING
set. All processes killed; 12 campaign Automations disabled (curve collector,
paper loops, wallet watchdog, LP guardian, audit monitor, xchain scan, Raydium
scan, go-live alerter, Meteora scanner, forward-test review, MFG check, EVM flow
watcher); night-shift launchd data plane (6 jobs) booted out. Repo public with
README. Research record complete. Rebuild path: this file + REPORT.md.
