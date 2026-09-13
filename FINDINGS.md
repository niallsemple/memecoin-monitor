
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
