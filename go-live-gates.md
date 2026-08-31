# Go-Live Gates — v3 STRICT & v6 CLUSTER
**Date:** 2026-08-29 · **Status:** DRAFT — neither strategy qualifies today
**Purpose:** the checklist a strategy must pass before any real stake is allowed, plus the two case studies that forced each rule.

---

## 1. Case study: `CTPoyCwk` — apeonfone ($fone)
Audit: **PASS** — contract clean, rugcheck score 1, LP 88.4% locked. Detected 2026-08-27 00:08Z at mc $378K / liq $52K.

| # | Strategy | Entry | Exit | PnL |
|---|---|---|---|---|
| 1 | v2/v3 | 00:18Z @ $1.02M mc (+10 min) | Trail-stopped 0.76x, 40 min later | **−£5.0 / −£5.2** |
| 2 | v2/v3 | 01:09Z @ $1.44M mc (+61 min) | Laddered 2x → 5x → 10x, trail-stopped at **12.11x** (peak mc $36.6M), ~46h hold | **+£113.0 / +£118.5** |
| 3 | v2/v3 | 2026-08-28 23:11Z @ **$17.4M mc** (+2,823 min — 47h old) | Still open; peak $30.3M, stage 0, zero profit taken | TBD, +74% peak unrealized |

**Lessons:**
- The laddered exit (25% at 2x / 5x / 10x, trail the rest) is what converted a runner into +£113. Without it, trade #2 is another round-trip.
- Same-token re-entry at 47h old and 12x higher mcap than first entry breaks every rule the system was built on. It is currently the only open exposure in v3. This trade existing at all is a bug in the re-entry logic, not a feature.

## 2. Case study: `5mFZZzyU` — Chill Ape ($CHILLAPE)
Audit: **PASS** — contract clean, rugcheck score 1, LP 100% locked. Detected 2026-08-29 08:16Z at mc $86K / liq $23K.

| # | Strategy | Entry | Exit | PnL |
|---|---|---|---|---|
| 1 | v2 | 08:22Z @ $117K (+6 min) | Sold 25% at 2x (09:50); rest trail-stopped at **0.19x** (14:18Z) | **−£4.3** |
| 1 | v3 | same | same | **−£7.2** |
| 2 | v4 MOM | 08:28Z @ $130K (1.51x detect) | TP 100% at 2x (10:10Z) | **+£16.1** |
| 3 | v4 MOM | 10:18Z @ $263K (3.05x detect) | Time-stop 1.47x after 121 min | **+£7.5** |
| 4 | v4 MOM | 12:20Z @ $380K (4.40x detect) | Trail-stopped at **0.06x** — near-total loss (14:18Z) | **−£16.6** |

**Lessons:**
- Peak was $428K (3.7x from v2 entry) — and v2/v3 still **lost money** on the token. The trailing stop gives back everything on pump-and-die shapes. Banking only 25% at 2x is not enough when the median peak-to-final is the REPORT.md −54% CAUTION pattern.
- v4's momentum scalps #2 and #3 show the profitable shape: enter early on strength, hard TP, time-stop. Trade #4 shows the boundary — re-entering at 4.4x detection price = buying the top of the distribution. **No re-entry above ~2.5x detection mcap, ever.**

---

## 3. Go-live gates — v3 STRICT (nearest to ready)
All must hold simultaneously, measured by the daily forward-test review:

| Gate | Threshold | Today |
|---|---|---|
| Sample size | ≥ 100 closed paper trades | 29 ❌ |
| Rolling realized PnL | ≥ 0 over trailing 7 days | −£41.6 ❌ |
| Max drawdown from bank_start | ≤ 10% | −7.1% ✅ |
| Profit factor | ≥ 1.3 | TBD (needs compute) |
| Re-entry rule | Coded: no entry on tokens > 6h old or > 2.5x detection mcap | Violated by open CTPoyCwk trade ❌ |
| Exit rule upgrade | Bank ≥ 50% by 2x (not 25%); hard time-stop 24h | Not implemented ❌ |
| Execution proof | 20 consecutive paper entries where live quote ≤ 2% worse than paper fill assumption | Not measured ❌ |
| Ops | £25 max position, £100 max total exposure, daily-loss kill-switch at −£30, manual confirm on every trade for first 20 live trades | — |

**Stake when passed:** £200 total, withdrawn back to zero on first rule breach.

## 4. Go-live gates — v6 CLUSTER (research stage)
| Gate | Threshold | Today |
|---|---|---|
| Labelled differentiator sample | ≥ 20 runners AND ≥ 20 husks after graduation | 2 vs 3, 169 unlabelled ❌ |
| Signal has ever fired | ≥ 1 paper trade | 0 trades, all `no_cluster_hit` ❌ |
| Post-fire validation | ≥ 30 fired signals, profit factor ≥ 1.5 | ❌ |
| Cluster signature | seed=85 SOL wallet cluster confirmed predictive on out-of-sample launches (not just backfit) | ❌ |
| Ops | Same £25/£100/kill-switch constraints as v3 | — |

Do not size v6 up until the 48h runner/husk differentiator finishes its labelling pass — the MFG curve data says these coins reliably die (~−95%), so v6's first live use may be as a **do-not-trade filter** on other strategies rather than an entry signal.

---

## 5. Universal rules (any strategy, any stake)
1. Audit PASS only — no CAUTION, no unavailable-audit, no non-Solana chains.
2. Entry window: token age ≤ 60 min at first entry. No re-entries > 6h old or > 2.5x detection mcap.
3. Exits: 50% off by 2x, trail remainder, hard 24h time-stop. The data's whole point: holding to the end is near-total loss (`BNPi6iiB` +1334% → −90%).
4. One token = one position across all strategies; aggregate exposure counts against the £100 cap.
5. Every real trade journaled to `mfg_trades.jsonl` with paper-vs-live slippage recorded — slippage > 5% on 3 trades = halt and review.

---

## 7. AMENDMENT (2026-09-01 review) — s60 breadth-entry strategy

Supersedes v3 STRICT as the go-live candidate. v3/paper_v3.json is LEGACY (pre-manufactured-launch research); the legacy alerter path cannot qualify without manual_signoff.json, which remains owner-only.

The amended strategy (spec: STRATEGY_SPEC.md; evidence: REPORT.md §59–§79l):
entry = net≥60 SOL AND ≥20 buys AND flow≥2.0, next-trade fill; exits = abort15 1.08× / abort30 1.15× / freeroll 75% @1.5× / trail 50% of peak / timestop 120m.

Amended measurable gates (scored by gate_check_s60.py against mfg_paper_trades_s60.jsonl, entries ≥ amendment_ts — the re-zero):
1. ≥30 fresh committed closes post-amendment (freerolled opens count at +12.5% floor, §79b)
2. expectancy strictly > 0
3. ≤1 full-loss (≤−50%) bleeder in the window

Manual gate: manual_signoff.json {"owner_approved": true} — created ONLY by explicit owner decision. qualified = measurable_ok AND owner_approved.
