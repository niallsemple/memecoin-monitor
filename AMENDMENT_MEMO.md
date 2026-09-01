# Gate Amendment Memo — E25 Entry Thresholds (DRAFT skeleton, for Sep 1 review)

**Status:** DRAFT — decision deferred until s60 forward shadow matures.
**Prepared:** 2026-08-31. **Review date:** 2026-09-01 (or when s60 committed n ≥ 20, whichever later).
**Hard rule:** no real-money trading without explicit owner signoff, regardless of this memo's outcome.

---

## 1. Proposal

Amend the E25 paper-trading gate entry trigger from loose (net ≥ 25 SOL, ≥ 10 buys, flow ≥ 2.0) to **strict breadth** (net ≥ 60 SOL AND ≥ 20 buys), exits unchanged (h108: abort15 <1.08×, abort30 <1.15×, freeroll 75% @1.5×, trail 50% of peak, timestop 120m).

Fallback candidate if s60 falters: **confirmed-entry W10** (fill at loose trigger, require net60/nb20 within 10 min, else exit at mark) — §77d.

## 2. Evidence (as of drafting — refresh numbers at review)

| Strategy | Committed n | Committed exp | Losses | Source |
|---|---|---|---|---|
| Loose gate (h108 exits) | 21 | −10.6% | 25% incl. full rugs | live gate file |
| **Strict entry s60** | 14 | **+8.4%** | **0 post-cutoff** | live shadow (forward since §77) |
| Confirmed-entry W10 | 21 | +4.1% | — | offline §77d |
| Exit-only best | 21 | −3.1% | — | §75 grid (45 cells) |

In-sample grid (§76): the +9% region held across 8 neighboring cells (flow 2.0/3.0 × both exit configs) — not a single-cell artifact.

## 3. Mechanism

Breadth of participation is what rug operators cannot fake cheaply. Manufactured campaigns use one-shot funder wallets and concentrated churn (§71: 14/14 fresh creators, 8/8 distinct funders); they cannot produce 60 SOL net across 20+ distinct buys. Strict breadth screens them out: **zero rugs post-cutoff under s60 vs 25% losers under loose.**

Known weakness: strict entry fills LATE (§77c — oFxvzBiT runner became a +6.6% scratch vs +13.3% loose). Aggregate expectancy still favors strict; single-race losses are the price.

## 4. Risk model (honest calibration, §77e + §79b)

- Expect win-rate regression from 100% → 70–85%.
- Tail: ~1 bleeder per ~20 trades at −50% class (fCERmUZg precedent, voided-window caveat).
- **Runner realization (§79b): freerolled runners resolve at the +12.5% FLOOR, not MTM — post-peak collapses are rug-speed and the trailing remainder sells near zero.** Model runner value as +12.5%, never as peak/MTM. 3JSy9Uvh: peak 1.76×, MTM +56%, realized +12.6%.
- Expectancy rests on asymmetry: many +3–8% scratches + +12.5% runner floors − rare bleeders. NOT on never losing, NOT on runner MTM.
- Wave-locked regime risk (§62/§73): edge concentrates in pump waves; droughts of 24–36h occur. Position sizing must assume strings of scratches.

## 5. Decision criteria at review

Amend ONLY IF all hold:
1. s60 committed_exp > 0 sustained with forward n ≥ 20 committed (currently 14).
2. At least one NEW post-deployment runner (≥1.5×) captured by strict entry (not just legacy positions).
3. Runner-scratch divergences (§77c pattern) remain rare: strict-missed runners ≤ 1 in 5 qualifying campaigns.
4. Frozen h108 gate still accrues normally (no instrumentation break).

**STATUS (2026-08-31 09:24 local, one day early):**
1. **MET** — 22 committed, +7.91%, zero post-cutoff losses.
2. **MET** — 3JSy9Uvh freerolled at 1.54×, first post-deployment strict-captured runner (§78f).
3. HOLDING — 1 divergence (oFxvzBiT, §77c).
4. HOLDING — engine parity §74d, all runs clean.

If (1) fails but confirmed-entry offline stays positive → evaluate fallback. If both fail → keep h108 gate accrual to 30 and re-review; if h108 committed_exp then > 0, no amendment needed.

## 6. After amendment (if approved)

- Gate re-zeros on the amended scorer: needs 30 committed closes with exp > 0 forward.
- Then: readiness review (manual signoff) — position sizing, max daily loss, kill-switch, wallet ops. Never automated.

---

## 7. POST-AMENDMENT GATE — PASSED (2026-09-01 23:20 local, §134)

Memo §6 required the amended scorer (s60nm5fr) to re-zero and accrue
30 committed forward closes at exp > 0. Final tally: **98 committed
closes, +1.507% committed expectancy, 90.8% win rate — PASSED at
3.3x sample.** All retired configs remain negative as shadows. The
readiness review (owner signoff, kill-switch, sizing) was completed
before live activation; live validation stands at 2/2 winners,
+0.01463 SOL on 0.2615 deployed (+5.6%). Amendment chain COMPLETE.
