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

## 4. Risk model (honest calibration, §77e)

- Expect win-rate regression from 100% → 70–85%.
- Tail: ~1 bleeder per ~20 trades at −50% class (fCERmUZg precedent, voided-window caveat).
- Expectancy rests on asymmetry: many +3–14% scratches + occasional 2–3× runners − rare bleeders. NOT on never losing.
- Wave-locked regime risk (§62/§73): edge concentrates in pump waves; droughts of 24–36h occur. Position sizing must assume strings of scratches.

## 5. Decision criteria at review

Amend ONLY IF all hold:
1. s60 committed_exp > 0 sustained with forward n ≥ 20 committed (currently 14).
2. At least one NEW post-deployment runner (≥1.5×) captured by strict entry (not just legacy positions).
3. Runner-scratch divergences (§77c pattern) remain rare: strict-missed runners ≤ 1 in 5 qualifying campaigns.
4. Frozen h108 gate still accrues normally (no instrumentation break).

If (1) fails but confirmed-entry offline stays positive → evaluate fallback. If both fail → keep h108 gate accrual to 30 and re-review; if h108 committed_exp then > 0, no amendment needed.

## 6. After amendment (if approved)

- Gate re-zeros on the amended scorer: needs 30 committed closes with exp > 0 forward.
- Then: readiness review (manual signoff) — position sizing, max daily loss, kill-switch, wallet ops. Never automated.
