# STRATEGY SPEC — s60 Breadth Momentum (pump.fun manufactured launches)
Status: DRAFT for Sep 1, 2026 amendment review · Paper-trading only · Real money requires explicit owner signoff
Evidence base: REPORT.md §59–§79c · Forward tape: mfg_paper_trades_s60.jsonl (post-cutoff 1788060000)

## 1. Thesis
Rugs on pump.fun are manufactured with concentrated one-shot funder wallets; they can fake
price and volume but cannot cheaply fake *breadth* (many distinct buyers). Entry selection on
cumulative breadth separates organic-ish campaigns from manufactured ones. The edge is in the
ENTRY FILTER, not the exit logic (§76: exit grid flat within noise; §77: entry grid ~16pp spread).

## 2. Entry rules (all must hold)
- Universe: new pump.fun launches flagged as manufactured-pattern candidates on the tracker tape.
- Cumulative net buy volume ≥ 60 SOL AND cumulative distinct buys ≥ 20 (the "s60" gate).
- Buy/sell flow ratio ≥ 2.0 at signal time.
- Fill at next trade after signal (no limit games).

## 3. Exit rules (h108 ladder, evaluated on every mark)
- abort15: if price < 1.08× entry at 15 min → exit (scratch).
- abort30: if price < 1.15× entry at 30 min → exit.
- freeroll: at 1.5× entry → sell 75% of position (recovers stake + locks profit); ride remaining 25%.
- trail: remaining 25% exits at 50% of peak multiple (peak-to-trail drawdown).
- timestop: 120 min after entry → mark-to-market exit of whatever remains.

## 4. Realized-outcome model (§79b/c — twice confirmed live)
- Freerolled runners realize at the **+12.5% floor**, NEVER at MTM. Post-peak decay is rug-speed
  (3JSy: 1.76× peak → +12.6%; gKNK: 1.91× peak → +12.9%). Any projection above floor is fiction.
- Expected distribution: many +3–8% green scratches + occasional +12.5% floor realizations
  − rare **−100% bleeders** (rug-through-gate takes the entire unfreerolled position;
  first observed live: E6gQ, 2026-08-31, §79d — 1.39× peak, no freeroll, dust in 2 trades).
  Expectancy is bleeder-dominated: each −100% event costs ~3.7pp/trade at n≈27; the edge
  lives or dies on rug-through-gate frequency (1/27 = 3.7% observed vs ~63% base rate).
- Known accepted leak: slow-breadth campaigns (Duz5, oFxvzBiT pattern) get caught late and
  scratch instead of freerolling. Fallback if regime shifts: confirmed-entry W10 (+4.1% full
  universe, §77d) — enter at loose pricing, require s60 breadth within 10 min.

## 5. Sizing (paper; real-money sizing set at readiness review)
- Flat 1 unit per signal. Max concurrent opens: uncapped in paper (observe collision rate first).

## 6. Kill criteria (any one → halt and re-review)
1. s60 committed expectancy ≤ 0 over any rolling 20 committed trades.
2. Two or more full-loss (−50%) bleeders within any 30-trade window.
3. Entry cadence collapse: < 5 committed entries over 7 days (regime dead).
4. Structural change: pump.fun program upgrade, fee change, or tracker data failure > 24h.

## 7. Validation gates (current position)
- [x] Backtest entry grid: strict breadth beats loose by ~16pp (§76–77)
- [x] Engine parity: live tracker == offline regenerator, 34/34 rows (§74d)
- [x] Forward shadow: n=25 committed, +7.90%, zero losses (as of 2026-08-31 11:24)
- [x] Amendment criteria 1–2 MET; 3–4 holding (AMENDMENT_MEMO.md §5)
- [ ] Sep 1 review: review_check.py re-derives all scorers from raw tape → amend gate
- [ ] RE-ZERO: 30 fresh committed closes with exp > 0 post-amendment
- [ ] Real-money readiness review — MANUAL OWNER SIGNOFF REQUIRED
