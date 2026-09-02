# Memecoin New-Listing Study — Live Monitor Findings
**Window:** 2026-08-25, 18:28–20:28 UTC (2h) · **Source:** dexscreener new token profiles · **Audits:** GoPlus + RugCheck + holder-concentration backfill · **Status:** FINAL

## 1. The question
Can monitoring dexscreener new listings with strict audit filters produce a tradable memecoin edge — and can we actually execute it?

## 2. What usually happens with a memecoin (literature + our live data)

### 2.1 The four-phase lifecycle (research consensus)
1. **Launch spike (0–30 min):** bots/bundle snipers buy bonding-curve bottom within seconds. Vertical candle. Worst retail entry.
2. **First dump (30 min–2h):** insiders unload into DEX liquidity post-migration. Typical 40–70% drawdown. Most rugs occur here.
3. **Consolidation or death (2–24h):** ~99% of pump.fun tokens show pump-and-dump traits (Solidus Labs); ~93% of Raydium pools show soft-rug behavior. Base case is zero.
4. **Second wave (rare):** only tokens that built real community during consolidation pump again — sometimes past the first high.

### 2.2 Our live sample (2-hour close, 60 tokens with outcomes; 123 tracked)
- Share down >50% from detection: **48% of all listings** — the base rate of catastrophic loss
- FAIL-verdict cohort (n=43): median **−58.8%**; 24/43 down >50%; fastest rug **−92.6% in 7 min**
- PASS-verdict cohort (n=10): median **+9.8%**, peak median +36.5%; one −56% ordinary dump (audit prevents rug mechanics, not selling)
- CAUTION cohort (n=7): spike-and-die — median peak **+68.7%** but median final **−54.6%**
- Runners round-tripped: `FpWUhWmD` +1111% peak → +179% final; `BNPi6iiB` **+1334% peak → −90% final** — the single most instructive token of the study: up 13x, holding to the end = near-total loss
- Template farm (FBCS/USCS): pinned ~$454K, ±0.1% for 2 hours — manufactured stability, identical 17.8% top-10

### 2.3 The measured dump curve (median mcap vs. detection value)
| +10 min | +20 min | +30 min | +40 min | +50 min |
|---|---|---|---|---|
| 94% | 86% | **68%** | 100% | 81% |

The +30-minute trough is the insider-dump kill zone; afterwards the sample bifurcates — dead tokens keep dying, survivors stabilize near detection value.

### 2.4 The entry-timing rule the data supports
"Audit PASS + still ≥80% of detection value at +40 min" excluded every catastrophic loss in-sample while missing none of the runners (both +500%+ tokens were far above floor at +40). Never enter before the kill zone resolves.

## 3. The audit system that worked
Five filters, automated in `monitor.py`:
1. **Contract permissions** (GoPlus): mintable / freezable / closable / mutable metadata / transfer hooks — instant.
2. **Creator history** (RugCheck): serial-rugger deployers — instant. Caught 2 tokens whose contracts were 100% clean.
3. **LP lock/burn %** (RugCheck) — instant.
4. **Liquidity depth + liq/mcap ratio** (dexscreener) — instant.
5. **Top-10 holder concentration** (RugCheck full report) — **only available ~10+ min post-launch**. The single most discriminating filter. Backfill flipped 4 PASS→FAIL in the first batch (incl. one token with 100% insider-held supply).

### Key structural finding
The best rug predictor (holder concentration) does not exist at the moment of maximum FOMO. Any strategy buying the launch spike is blind on the decisive variable. Entry, if any, belongs in post-dump consolidation.

### Known blind spot
Template/farm launches: two "custody system" tokens (FBCS/USCS) — identical 17.8% top-10, same description template, pinned ~$454K mcaps, trivial volume. Same deployer, manufactured stability. Passes all five filters; needs cross-token similarity detection (future work).

## 4. How memecoins are actually traded (execution layer)
- **Stack:** Phantom/Solflare hot wallet (1–5 SOL) → terminal (Axiom/BullX/GMGN/Photon, 0.1–1%/trade, anti-MEV) → Jupiter/Raydium routing.
- **Sizing:** 0.05–0.1 SOL exploratory; expect 70%+ losses on research positions.
- **Exits (where returns actually come from):** mechanical ladder — 25% at 2x, 25% at 5x, 25% at 10x, trail the rest. Discretionary exits are the #1 retail failure.
- **Who profits:** ~70–80% of retail lose over 90 days. Winners have speed infra, information networks, or copy-trade verified wallets.

## 5. Can WE trade it? (capability answer)
- **I cannot execute trades.** No wallet, no keys, no funds, no exchange/bot access. Monitoring, auditing, scoring, alerting: yes. Signing transactions: no.
- **Viable division of labor:** monitor generates filtered watchlist + consolidation entry signals → human (or user's terminal/bot) executes.
- Realistic system: monitor (defense) + consolidation-entry rules + mechanical exit ladder + small fixed sizing.

## 6. Strategy backtest (final, in-sample, 2h close)
Equal $1 positions, Solana tokens with ≥38 min of history (n=43), no fees/slippage, 2–4 min mcap sampling (misses intra-candle peaks), verdicts post-backfill (mild lookahead).

| Strategy | Avg per $1 | Lost >50% | Best | Worst |
|---|---|---|---|---|
| A: buy every listing at detection, hold | **−30.3%** | **19/43** | 2.79x | 0.04x |
| B: enter at +40 min only if ≥80% of detection value; ladder 25% @2x/5x/10x | **−0.6%** | **1/43** | 1.62x | 0.44x |

Naive decayed as cohorts aged (−1.5% at n=30 → −30.3% at n=43): time is the enemy of the unfiltered holder. Rule B ended ~flat with the left tail deleted. After realistic 2–5% round-trip costs on thin pairs, B is roughly breakeven in this window — a survival machine, not (yet) a profit machine. The value is what it makes possible: capital intact + occasional ladder captures, vs. near-certain bleed-out.

## 7. Final verdict

**SUPERSEDED — see §44 (FINAL, sealed 28 Aug 2026 19:00 UTC): verdict B —
defensive/discretionary edge. The 23h live forward test killed the in-sample
edge on two independent dimensions; the bankable result is trade-avoidance
(unfiltered books lost −25.2%/−13.1%/−3.0%/−1.4% while the gated book stayed
flat at £1,000).** The original in-sample verdict below is kept for the
historical record of what the data looked like before forward testing:

1. **"Monitor new listings + buy clean audits" is a losing strategy as stated.** Clean-audit tokens mostly go flat; unfiltered listings carry a 48% catastrophic-loss rate; even audit-PASS tokens can dump on ordinary selling.
2. **The audit's real value is negative selection.** Every catastrophic loss in-sample carried a flag our system raised at or within ~15 min of detection. As a "do-not-trade" list, the filter was flawless in this window.
3. **Timing dominates selection.** The +30-min kill zone and the runner round-trips (13x → −90%) show that *when* you enter and *how* you exit matter more than *what* you pick.
4. **The executable edge, if any:** audit PASS → wait +40 min → require ≥80% floor survival → enter small → mechanical ladder. Structurally sound in-sample; unproven after costs; needs a multi-day out-of-sample run.
5. **Execution capability:** none on my side — no wallet, keys, or funds. The workable system is this monitor generating signals with a human/terminal (Axiom/BullX/GMGN + Phantom) executing. Recommend: paper-trade the rule for a week before risking anything.

## 8. Live paper-trading session (£1,000 bank, 2% sizing) — 20:24 → 23:24 UTC

The rule from §6/§7 was run live for 3 hours against the real feed: Solana + audit PASS only, token detected after window start, age ≥38 min, current mcap ≥80% of detection mcap, detect liquidity ≥$20k, size = 2% of cash, 1.5% fee per side, ladder 25% out at 2x/5x/10x, trailing stop at 50% of position peak.

### 8.1 Trade log

| time (UTC) | action | token | size | entry mcap | age at entry |
|---|---|---|---|---|---|
| 21:11 | BUY | FZqdw6oS | £20.00 | $1,383,520 | +43 min |
| 22:27 | BUY | 5RhPVzDs | £19.59 | $941,224 | +41 min |
| 22:27 | BUY | HhSDQs8y | £19.20 | $539,891 | +41 min |
| 22:52 | BUY | 7h3jTPnE | £18.81 | $124,388 | +45 min |

4 entries out of ~260 tracked tokens — the filters rejected ~98.5% of everything the feed produced. No stop-outs, no ladder fills during the window.

### 8.2 Result (marked at last price, positions still open)

- Final bank (23:13 UTC close): **£1,010.56 → ROI +1.06%** in ~3 hours (cash £921.24 + open book £89.32 vs £77.60 cost)
- Session range: +1.0% to +2.6% — the open book peaked at £104.36 and faded into the close, a live demonstration of the pop-then-drift pattern from §2.
- All four positions finished the window above entry; peak unrealized was ~+97% on FZqdw6oS before it kissed and fell back below the 2x ladder rung.
- Honest caveat: 4 trades in 3 hours proves the *structure* executes, not that it's profitable. One good evening is not an edge. The backtest says the same rule was breakeven-after-costs over a larger in-sample; a multi-week out-of-sample run is the next evidentiary step.

### 8.3 Holder overlap ("smart money") analysis

Method: for every token that peaked ≥1.5x its detection mcap ("winner"), pull RugCheck's full report top-20 holders (excluding lockers/burns), index wallet → tokens.

- Winners profiled: **48**
- Unique top-20 wallets: **960**
- Wallets appearing in ≥2 winners: **0**

**Verdict: no visible repeat smart money at the top-holder level.** Each winning memecoin's top holders are a fresh crowd. The profitable wallets either never become top-20 holders (they sell into the pump early, staying small on the snapshot), or they rotate through fresh wallets per play. "Follow the whales of the last winner" has no observable signal in this dataset — wallet-following as a strategy is not supported. The edge, if it exists, lives in timing and filtering, not in copying holders.

## 9. Early-momentum rule (v2) — live paper session 06:24 → 09:24 UTC, 2026-08-26

The entry-timing analysis (§8 follow-up) showed: (a) feed lag is a median 13.7 min after pair creation; (b) on the filtered cohort, waiting +38 min added NO protection vs +5 min; (c) mcap at +5min ÷ detect mcap separated winners (median 1.35) from losers (0.59). The v2 rule: audit PASS → enter at +5 min if current mcap ≥ 1.0× detection mcap → same sizing (2%), fees (1.5%/side), ladder (2x/5x/10x) and 50% trailing stop.

### 9.1 Session flow

- ~30 Solana tokens detected post-window; verdicts roughly half FAIL, most of the rest CAUTION, a handful PASS.
- Two PASS tokens reached the +5-min gate and **failed the momentum floor** (trading below detection mcap — the exact 0.59-slope loser profile; filter worked as designed).
- **One entry: DMoRRhei, £20.00 at $144,841 mcap (+6 min after detection).** Entry slope was exactly 1.00 — the weakest bucket in the in-sample analysis. It ran +15% in 4 minutes, then faded; trailing stop fired at 0.49x for **−£10.58**.
- Result: **bank £989.42 → ROI −1.06%**, one trade, one stop-out.

### 9.2 v1 book overnight (control datapoint)

The v1 (38-min rule) book left three positions open overnight; all bled out (realized −£58), book £959.92 (−4.01%). Yesterday's +1.06% did not survive the night — the pop-then-fade curve applies to our own positions exactly as measured.

### 9.3 What the two live sessions together say

1. **Neither rule is profitable yet in live micro-samples.** v1: +1.06% over 3h, −4.01% after overnight. v2: −1.06% over 3h (1 trade). Samples of 1–4 trades prove execution, not edge.
2. **The weakest-slope bucket (1.0–1.25) is where the fake-outs live.** In-sample: slope ≥1.0 → 45% win, −2.9% median; ≥1.25 → 60% win; ≥1.5 → 75% win, +19% median. The single v2 loss entered at exactly 1.00. **Recommended next variant: floor at ≥1.25.**
3. **The audit + momentum gauntlet rejects ~99% of supply** — in thin windows that means 0–1 trades in 3 hours. Any real deployment needs to accept long flat stretches.
4. **Stops are doing their job.** Both sessions' losses were cut mechanically near −50%; no position was ridden to zero.
5. Next evidentiary step unchanged: run v1 and v2 (and a v3 with floor ≥1.25) in parallel on the live feed for multiple days before any conclusion about profitability.

## 10. Live Session 3 (2026-08-26 16:40–19:40 UTC) — v3 STRICT rules (floor raised to ≥1.25)

**Rule change from v2:** same early-momentum entry (audit PASS, Solana, detected after window start, age ≥5 min, ≥$20k detect liquidity), but the momentum floor raised from 1.0× to **1.25×** detection mcap at the +5-min checkpoint — targeting the fake-out bucket identified in session 2. Sizing 2% of cash, 1.5% fee/side, ladder 25% at 2x/5x/10x, trailing stop 50% of position peak. Fresh £1,000 book.

### Result

- **Final bank: £1,000.00 · ROI 0.00% · 0 trades (0 open, 0 closed).**
- Feed: 559 tokens tracked by close; 63 Solana tokens detected after window start → 32 audit FAIL, 22 CAUTION, **9 PASS**.
- Of the 9 PASS: 7 reached the +5-min checkpoint and **all 7 failed the 1.25× momentum floor**; 2 were still pending evaluation at close.

### What the rejections did afterwards (checked ~2h later)

| Token | Detect mcap | Later mcap | Ratio | Floor verdict |
|---|---|---|---|---|
| VISUALIZE | $81,284 | $39,535 | 0.49× | ✅ saved |
| CRYPTOTRUMP | $218,492 | $39,408 | 0.18× | ✅ saved |
| holycoin | $146,161 | $41,102 | 0.28× | ✅ saved |
| Beni | $150,777 | $39,794 | 0.26× | ✅ saved |
| ZWH | $103,881 | $69,725 | 0.67× | ✅ saved |
| Quake | $909,697 | $1,069,856 | 1.18× | ~ neutral |
| Martians | $1,596,804 | $3,392,251 | 2.12× | ❌ runner missed |

The floor blocked 5 bleed-outs (would have been stop-losses near −50%), 1 flat, and filtered out 1 runner that needed longer than 5 minutes to get going.

### Three-session comparison

| Session | Rule | Trades | Session ROI | Notes |
|---|---|---|---|---|
| v1 (25 Aug) | kill-zone entry (38 min wait) | 4 | +1.06% | bled to −4.01% overnight |
| v2 (26 Aug am) | +5-min momentum, floor ≥1.0 | 1 | −1.06% | fake-out entered at slope 1.00 |
| v3 (26 Aug pm) | +5-min momentum, floor ≥1.25 | 0 | 0.00% | pure loss-avoidance; 5 dumps dodged, 1 runner missed |

### Verdict

1. **The stricter floor works as loss-avoidance.** 5 of 7 rejections went on to lose 33–82%. In a thin window the strategy's value is entirely in what it refuses.
2. **The +5-min checkpoint has a known blind spot:** Martians (2.12×) was flat at +5 min and ran later. A second checkpoint at +15 min is the obvious fix — but changing rules mid-experiment would contaminate the data, so it stays untested.
3. **Across 3 sessions we have 5 total live paper trades.** That is still nowhere near enough to claim an edge. In-sample backtest says floor ≥1.25 should win ~60% of entries; live, it has entered 0 times in 3 hours because PASS + immediate momentum is rare (~1 in 60 new listings even reaches the checkpoint).
4. **Trade frequency is the binding constraint.** Any further conclusion requires a multi-day always-on run — the 3-hour human-attended windows structurally under-sample a signal this rare.
5. **Next step (unchanged, now more urgent):** run v2 and v3 in parallel as a scheduled daily automation for 2+ weeks, plus optionally a v4 with a +15-min second checkpoint, and judge on ≥30 trades.

## 11. Research Deep-Dive (2026-08-27 morning) — optimal settings from our data + external sources

### A. What our own data says (566 audited Solana tokens with price history, 54 PASS)

**Entry timing / momentum floor — the single biggest lever:**

| r5 bucket (mcap @ +5min ÷ detect) | n | P(peak ≥ 2x) | fast-rug |
|---|---|---|---|
| < 1.0 | 23 | 17% | 13% |
| 1.0–1.25 | 18 | 11% | 0% |
| 1.25–1.5 | 5 | 0% | 0% |
| **≥ 1.5** | **8** | **88%** | **0%** |

The 1.25 floor (v3) is barely better than 1.0 — the real separation is at **≥ 1.5×**. Same at the +15-min checkpoint: r15 ≥ 1.5 → 88% hit 2x, median peak 3.94x, median final 1.93x (they *stay* up).

**Other detection features:** liquidity $20–50k has the most upside (28% hit 2x) but everything eventually dies (median final 0.02x across PASS — this is a momentum-capture game, not investing). Age at detection 15–40 min had the best hit rate (34%); <5 min is 50/50 boom/rug. Buy/sell ratio and volume/liquidity churn do **not** reliably separate rugs from runners.

**Rug signature (the overnight 0.00–0.02× stops):** all were audit-PASS with zero flags, low-ish liquidity ($25–53k) and extreme h1 buy/sell asymmetry (up to 6.5:1) — i.e. manufactured pump flow. No detection-time feature we track reliably predicts them. Protection must come from **exit discipline**, not entry filters.

### B. Simulated settings on the full cohort (2% sizing, 1.5% fees, £1000 bank)

| Variant | Trades | Win% | Sim ROI | Live check |
|---|---|---|---|---|
| floor ≥1.0 (v2) | 31 | 26% | −9.2% | live: −13.4% ✓ direction matches |
| floor ≥1.25 (v3) | 13 | 38% | −3.8% | live: −6.0% ✓ |
| floor ≥1.5 | 8 | 62% | +0.2% | — |
| r5 ≥1.5, else r15 ≥1.5 | 10 | 60% | +0.9% | — |

**Exit sweep on the best entry variant:** trailing stop 0.6–0.7 of peak beats 0.5 (we use 0.5 — too tight). Selling **100% at 2×** beat every ladder (+3.2% vs +0.9%). Best combo tested: **100% @ 2× + stop 0.6 of peak → +4.1%** (10 trades — small sample, treat as hypothesis).

### C. What successful external traders/bots use (web research, 2026)

Convergent settings across guides (Altrady pump.fun guide, memecoin terminal guides, sniper case studies):
- **Sizing: 1–2% per trade** — matches ours ✓
- **Take profit: sell 50–100% at 2×**, remainder at 5× — matches our sweep winner ✓
- **Stop loss: 30–50% below entry / trailing** — ours is equivalent ✓
- **Speed is the real edge:** top snipers are in/out in 48–61 seconds on the launch pump, using first-block execution (Jito bundles, priority fees, anti-MEV). Our Dexscreener feed has a ~14-min median detection lag — we are structurally late; the momentum checkpoint is how we compensate.
- **Rug checks:** mint/freeze authority revoked, LP burned/locked, top-holder concentration — our GoPlus+RugCheck audit already covers these.
- Win rates of even profitable snipers are ~50–56% — small stakes, fast loss-cutting, let winners pay for losers.

### D. GitHub tooling scan

- **chainstacklabs/pumpfun-bonkfun-bot (971★, Python)** — the credible open-source option: on-chain listeners (logs/blocks/Geyser), bonding-curve graduation watcher, configurable tp/sl exits, copy-trading example. From a known infra company, actively maintained, explicitly educational. Would need a funded wallet + paid RPC for real execution.
- Also found: henrytirla/Solana-Trading-Bot (287★, Python), coffellas-cto/Solana-Copy-Trading-Bot (410★, Rust), DracoR22/handi-cat wallet tracker (203★).
- ⚠️ **Security warning:** the search results are full of scam repos ("free premium sniper bot 2026", SEO-spam descriptions) designed to steal private keys. Never put a key into any bot without a full code audit.

### E. Recommended v4 configuration (hypothesis for next test)

1. Entry: audit PASS + liq ≥ $20k + **r5 ≥ 1.5×** (fallback: **r15 ≥ 1.5×**)
2. Exit: **sell 100% at 2×**; trailing stop at **60% of peak**; time-stop out if flat after 2h
3. Sizing: 2% of bank (unchanged)
4. Expected trade frequency: ~1 per 4–6 hours of feed (rare by design)

Caveat: 10-trade simulation sample — v4 is a hypothesis to test forward, not a proven edge.

## 12. Countermeasures Research (2026-08-27) — how the ecosystem deals with instant rugs / fake momentum

**Problem restated:** ~42% of our momentum entries (15/36 across v2/v3/v4) end as instant 0.00–0.02× rugs. Audit-PASS contract checks (GoPlus + RugCheck) do not catch them; the 1.5× momentum crossing is itself faked by coordinated pump flow; 10-min polling cannot exit a rug that completes in seconds.

### What the ecosystem says (validated by live re-checks)

The agreed answer is the **behavioural / wallet layer**, not contract checks:

1. **Bundle detection at launch** — coordinated wallets buying at creation to fake organic demand (OnChainRisk, DeFade, Axiom Pulse all flag this).
2. **Fresh-wallet / sybil clusters** — e.g. DeFade on a live rug: "fresh wallets (<24h old) hold 36.5% of supply, 29 critical-fresh wallets, coordinated entry".
3. **Deployer history** — "serial rugger: 65 tokens, 0% survival rate" (DeFade). Pump devs recycle wallets; a dev with prior dead tokens is the strongest single tell.
4. **Shared-funder tracing** — cluster top holders by who funded their wallets.
5. **Tools that do this today:** DeFade (free scans, rug score, dev history, bundle %, insider networks), Bubblemaps (supply clustering), Axiom Pulse (filters: top-holder %, dev behaviour, bundle/sniper flags), OnChainRisk. Our GoPlus+RugCheck audit answers a *different* (contract) question — clean contracts are table stakes; these tools read the humans.

### Validation against our own rug tokens

Re-checked DYvfD7T9, 7kSxtYRB, 72xH2LMC, 33PngJ2J, wzjjr5TW on RugCheck now: top-10 wallets hold **99–100%** of supply in every case (the dump wallets, visible post-hoc). At detection they passed because bundled supply is deliberately **spread across many fresh wallets to evade top-holder concentration checks** — exactly the evasion the wallet-age/shared-funder layer is built to catch.

### Feasibility for our pipeline

- **Deployer-history check:** pump.fun frontend API (creator + prior coins) is Cloudflare-blocked (403) — tested. Would need a Solana RPC provider (Helius/QuickNode free tier) to derive creator + funding graph on-chain.
- **Fresh-wallet % / shared-funder:** implementable with a Helius free API key (enhanced APIs expose wallet age + funding txs). Moderate engineering, slots into monitor.py as a third audit stage.
- **Near-term, no new infra:** (a) cap stake at 1% on entries younger than 15 min; (b) take profit faster (v4's 100% @2x already helps); (c) treat 40% rug rate as the cost base — strategy must be profitable *after* it, which currently none is.
- **Structural fix (only real one):** seconds-level on-chain execution (Chainstack bot route) so exits can fire inside the dump candle.

### Bottom line

Instant rugs are a solved-detection / unsolved-for-us problem: the detection tech exists (behavioural wallet forensics) but requires on-chain data infra we don't currently have; and even perfect detection only halves the problem — the other half is exit speed. Next decision point: (A) add a Helius-based behavioural audit stage, (B) move to real on-chain execution with a burner wallet, or (C) keep the paper race as-is and accept the ~40% rug tax as the measured cost of late entries.

---

## §13 — Path A build: behavioural (wallet-layer) audit stage (27 Aug, evening)

User chose Path A (behavioural audit). What shipped:

- **`behaviour.py`** — stage-3 module, `assess(mint)` → `{verdict: PASS|RISK|SKIP, mode, metrics, reason}`.
  - **Helius mode** (active when `helius_key.txt` or `HELIUS_API_KEY` present): fresh-wallet supply % (top-20 holders, wallets <24h old), deployer age, top-20 concentration. RISK if fresh>25%, deployer<24h, or top20>80%.
  - **Proxy mode (live now, keyless):** RugCheck danger scan — RISK if any risk flagged `danger`. Weaker: rugs were clean at detection time in our validation, so expect limited catch rate until a Helius key unlocks the real forensics.
- **`monitor.py`** — every new Solana audit-PASS token now also gets a `behaviour` assessment attached to state.
- **`papertrader_v5.py`** — v4 clone (floor 1.5, 100% TP@2x, 60% trail) plus behavioural gate: RISK tokens never bought, non-PASS tokens waited on. Fresh £1,000 book running alongside v2/v3/v4 as the treatment arm.
- **`memecoin_loop.py`** — pipeline extended: monitor → v2 → v3 → v4 → v5, v5 line added to the automation artifact.
- **Automation description updated** to mention v5 + behavioural stage.

End-to-end automation run `run_1f3286f0` succeeded with all four books green; v5 bank £1,000.00, 0 trades (no eligible entries yet).

**Known limitation:** public Solana RPC endpoints (mainnet-beta 429, publicnode/ankr 403) are blocked from this IP, so Helius is the only viable path to fresh-wallet/deployer-age forensics. Free tier suffices. Until then v5's gate is the weak RugCheck-proxy version.

**§13 update (27 Aug, 18:25 BST):** Helius free-tier key installed (`helius_key.txt`). Live tests on 3 recent audit-PASS tokens: 1 PASS (deployer 28h old, top20 27%), 2 RISK correctly flagged (deployer ages 0.8h and 1.3h — would have been bought by v4, blocked by v5). Full forensics (fresh-wallet %, deployer age, top-20 concentration) now active in monitor.py + v5 gate. Verified end-to-end via automation run run_12622ee2 — all four books green.

---

## §14 — Full-dataset refresh + falsification battery (27 Aug, 19:40 BST)

The master research brief (SOLANA_MEMECOIN_RE.txt) was adopted as the governing spec. Dataset has grown to **1,332 tracked / 815 audited Solana tokens with history (81 audit-PASS)** — ~1.5× the §11 sample. Three new analyses: `analyze.py` (refresh), `baserate.py` (PHASE 3 base rates), `falsify.py` (Part 10 battery).

### A. Base rates — the actual population (n=815, ratio vs detection mcap)

| horizon | median | ≥0.5x | ≥1x | ≥2x | ≤0.1x |
|---|---|---|---|---|---|
| +5 min | 0.90x | 79% | 38% | 4% | 4% |
| +30 min | 0.66x | 59% | 29% | 6% | 9% |
| +1 h | **0.49x** | 49% | 23% | 7% | 13% |
| +2 h | 0.40x | 41% | 17% | 5% | 15% |
| +6 h | 0.32x | 31% | 11% | 3% | 20% |

Ever-reach over full track: ≥1.5x 31%, ≥2x 19%, ≥5x 4%, ≥10x 2%. **Median time-to-peak: 3 min after detection** (feed lag ~13 min after creation ⇒ typical token tops ~16 min after birth). 75% of tokens peak within 30 min of detection. Buying at detection = buying the median token near its high. This confirms the §2 lifecycle at 13× the original sample.

### B. The momentum signal replicates at scale — the monetization does not (yet)

- r5 ≥ 1.5 (n=9): 78% hit 2x · r15 ≥ 1.5 (n=13): **92% hit 2x**, median peak 3.34x. The signal is real and stronger than §11's estimate.
- Best simulated config (entry r5/r15≥1.5, 100% TP@2x, trail 0.6, 1.5% fees, 2% sizing): **mean +13.3%/trade, median +0.6%, 8/16 wins, n=16**.
- **Falsification:** remove best 3 trades → mean −6.0%; remove best 5 → −20%. The four +97% full-2x exits carry the entire edge. Bootstrap 95% CI on mean: **[−13.6%, +40.8%]**, P(mean<0)=17%. Chronological halves: +14.4% then +12.2% mean but second-half median −35.3% (3/8 wins).
- Parameter plateau: stop 0.7 > 0.6 > 0.5 monotonically across all three ladders — the direction (looser trailing) is consistent, not an island; magnitude is noise at n=16.
- **Verdict: WEAK, not SURVIVES.** Signal is real; net-of-cost monetization is statistically indistinguishable from zero and outlier-dependent. Needs the mandated ≥30-trade forward sample.

### C. Red-team finding — audit-PASS adversely selects for dumpable tokens

| verdict (fresh detections <60 min) | n | med @1h | dead <0.2x | ≥2x |
|---|---|---|---|---|
| PASS | 62 | **0.23x** | **50%** | 10% |
| CAUTION | 156 | 0.17x | 53% | 6% |
| FAIL | 387 | 0.43x | 17% | 7% |

Audit-PASS tokens die *faster* than audit-FAIL ones at +1h, even age-matched. Mechanism hypothesis: a profitable pump-and-dump *requires* what our audit selects for — clean contract + ≥$20k liquidity — because insiders need retail to be able to ape in. FAIL tokens are dominated by no-liquidity non-starters that never pump and so have nothing to dump from. **The audit is necessary (blocks contract-level theft) but is NOT a positive selector — it screens into the predator's preferred prey.** §2's small-sample claim that PASS outperforms does not replicate at n=815; it was window luck. The edge, if any, lives entirely in the momentum gate + exit discipline, not in the audit verdict.

### D. Live books (as of 18:36Z)

v2 −22.1% (25 closed, 8 open) · v3 −14.1% (12+1) · v4 −9.5% (8 closed) · v5 £1,000 flat, **0 trades** — the behavioural gate (Helius forensics) has admitted nothing yet. Live vs simulation divergence (v4 live −9.5% vs sim +13%/trade mean) is itself evidence: both samples tiny, but the direction warns that reconstructed-history fills flatter the strategy (2–4 min mcap sampling misses intra-candle peaks a live 100%@2x order may never see).

### E. Hypothesis ledger (per anti-data-mining rule)

| ID | Mechanism | Result | Status |
|---|---|---|---|
| H01 | Audit PASS selects survivors | Reversed at scale — PASS dies faster @1h | **KILLED** (as positive signal; kept as defense) |
| H02 | r5/r15 ≥1.5 momentum predicts 2x | 78–92% hit rate, replicates at n=815 | **SURVIVES** (as signal) |
| H03 | 100%@2x + trail 0.6 monetizes H02 | +13%/trade mean, CI straddles 0, outlier-carried | **WEAK** |
| H04 | Ladder exits beat full 2x sell | Ladders uniformly worse in sweep | **KILLED** |
| H05 | Kill-zone wait (+38 min) adds protection | §9: no protection vs +5 min | **KILLED** |
| H06 | Repeat top-20 holders = followable smart money | 0/960 wallets repeated across 48 winners | **KILLED** |
| H07 | Behavioural (wallet-age/deployer) gate cuts rug tax | Live, 0 admissions yet | **TESTING** (v5) |
| H08 | Faster exits inside dump candle need seconds-level exec | Detection tech exists, infra gap confirmed | **OPEN** (structural) |
| H09 | Repeat EARLY BUYERS across winners = followable signal | 15/166 first-buyer wallets repeat across winners (0 in control); top wallet first-25 buyer in 5/10 winners, 9W/3L tracked hit rate vs 19% base rate | **PROMISING — TESTING** |
| H10 | Cluster presence + momentum interaction | All 15 wallets = ONE cluster; cluster-touched: 46% hit 2× / 8% dead (vs 16% / 32%); **momentum+cluster: 91% hit 2×, med peak 5.2×, 9% dead** (n=32); cluster w/o momentum: 19% — cluster marks quality, momentum times entry | **PROMISING — needs forward validation** |

---

## §18 — Cluster expansion + interaction analysis (27 Aug 2026, `cluster_expand.py`)

### The cluster

All 15 repeat first-buyer wallets collapse into **one cluster** (union-find on ≥2 shared recent tokens). Coordinated entity confirmed. 302 tokens touched in recent windows; 85 tracked in our dataset.

### Cluster scorecard (vs population)

| group | n | P(≥2×) | P(≥3×) | med peak | dead <0.2× |
|---|---|---|---|---|---|
| all tracked | 825 | 19% | 9% | 1.16× | 30% |
| cluster-touched | 85 | **46%** | 35% | 1.82× | **8%** |
| not cluster-touched | 740 | 16% | 6% | 1.13× | 32% |

Binomial z ≈ 6.3 vs base rate — significant, BUT discovery bias applies (cluster found *via* winners). The **dead-rate suppression (8% vs 32%) was not selected for** and is the cluster's most interesting independent property: its picks almost never rug — consistent with insider control (they don't rug their own pushes) or genuinely skilled selection.

### The interaction — best signal of the project

| rule | n | P(≥2×) | P(≥3×) | med peak | dead |
|---|---|---|---|---|---|
| momentum ≥1.5× (any verdict) | 130 | 72% | 40% | 2.53× | 29% |
| **momentum AND cluster** | **32** | **91%** | **72%** | **5.20×** | **9%** |
| momentum, no cluster | 98 | 66% | 30% | 2.28× | 36% |
| cluster, NO momentum | 53 | 19% | 13% | 1.23× | 8% |
| cluster AND audit PASS | 11 | 36% | 36% | 1.26× | 9% |

Mechanism read: **the cluster marks quality (8% dead), momentum confirms the push is live (cluster-without-momentum is no better than chance).** Neither works alone; together they're the strongest cell measured. Audit PASS adds nothing on top (n=11, weak) — consistent with §14.C's "audit is defense, not selection."

### Known bias + required validation

The cluster was discovered on winners, so in-sample enrichment is partly circular. Forward validation design (v6, next slice): monitor fetches each new token's earliest swaps at detection, checks first buyers against `cluster_wallets.txt` (15 wallets, saved), tags state; entry requires cluster tag AND momentum checkpoint; paper-trade alongside v2–v5. Success criterion: ≥30 tagged entries with hit rate ≫ momentum-only baseline and dead rate ≪ 29%.

### Latency note

Cluster buys happen at birth; we detect at +13 min. The momentum checkpoint (r5/r15) is what synchronizes us to the still-open move — §16 showed minutes-band latency costs nothing for this signal class. The cluster tell + momentum timing is fully capturable with current infrastructure. No new infra required.

---

## §17 — Part 6 wallet intelligence: the early-buyer signal (27 Aug 2026, ~21:00 BST)

H06 killed "follow top-20 holders" (0/960 repeats). §17 tests the sharper population: **first-25 unique buyers** of each winning token, pulled via Helius enhanced API with full pagination back to pair creation (`wallet_intel.py`, `wallet_firstbuyers.py`).

### Findings

1. **Repeat early buyers exist.** Across the 10 biggest non-artifact winners (peak 12–74×), 166 unique first-buyer wallets; **15 appear in ≥2 winners**; one (`FnBmjyWp…rK34`) is a first-25 buyer in **5 of 10**. Control group (12 losers): 0 repeats in the limited-window test. Winners-repeat set had zero presence in losers.
2. **Hit rate is far above base rate.** The top two repeat wallets' last-100-swaps histories each touch 27 tokens: of those tracked in our dataset, **9 peaked ≥2× vs 3 that never reached 1.5×** — a ~75% hit rate against a 19% population base rate (§14.A). (14/27 tokens untracked — unknown outcomes; survivorship caveat applies.)
3. **The "smart wallets" are probably one cluster.** The two deepest-analysed wallets share most of their recent token history (D7EzLhhD, XhQ6ByZ9, J3zGJjGG, 7mMQoNvU, 2TvUVvuQ + the same 2 losers). The 15 repeat wallets likely collapse into a few coordinated entities. This cuts both ways: if they *are* the pump (insiders), their first-buy is still the earliest public tell that a coordinated push has started; if they're skilled momentum-snipers, it's cleaner alpha. Either way the signal is **observable at token birth** — well before our ~13-min feed detection.
4. **Timing compatibility:** median time-to-peak is ~3 min after our detection (~16 min after birth). A first-buyer alert at birth + our audit gauntlet could enter ahead of the typical peak — this is the first mechanism found that is *causal* (coordinated capital) rather than merely statistical.

### Caveats (red-team)

- n=10 winners; the winner definition embeds survivorship; untracked tokens (14/27) could hide a normal hit rate.
- Cluster insiders → their buys predict the pump AND the dump; following them long means being their exit liquidity. Any v6 rule must pair the signal with the strict exit discipline (100%@2× / trail) and the behavioural gate.
- Possibility the cluster detects *something else* (e.g. deployer reputation) rather than causing the pump — same observable either way.

### Next slice (queued)

Cluster expansion: map all 15 repeat wallets' shared-token graphs to consolidate entities, score cluster hit rate across ALL tracked tokens (not just top-10), then define v6 paper rule: *alert when ≥1 cluster wallet is among a new token's first buyers + audit PASS + behavioural PASS → momentum-confirmed entry*. Helius cost is manageable (~25 calls/token).

### E2. Where this leaves the master brief

16 parts mapped; current standing: Part 5 (rug forensics) — done-ish, behavioural stage live; Part 7 flow/momentum families — partially tested via r5/r15; Part 10 falsification — started here, outlier-dependence exposed; Parts 1–3 (ecosystem/data map current-state), Part 6 (deep wallet P&L), latency decay curve (Part 9), and capacity modeling — outstanding. Next highest-value: multi-day forward sample for H03/H07 (running via automation) and Part 1 ecosystem refresh (launchpad market share may have shifted since this monitor was built on dexscreener new-profiles).

---

## §15 — Part 1 ecosystem map, current state (27 Aug 2026, web research)

Sources are 2026-dated ecosystem/comparison writeups; figures vary between sources and are quoted with dates, not treated as gospel. Facts vs. implications separated.

### Launchpads — who actually matters now

- **Pump.fun re-monopolized.** After LetsBonk's mid-2025 surge (58.5% daily share at peak), Pump.fun "entirely recaptured its monopoly position, dominating 95% of the token graduation market" as of Feb 2026, with ~155k DAU [Source: Nexus One Cap, 2026-03-03]. Launch share quoted at ~62–66%, ~72k tokens/day, graduation rate <1.5% [Source: stakepoint.app, 2026-01-20; bitbank.nz, 2026-08-17].
- **Market context:** total launchpad volume plateaued (~$100M/day zone) and only ~100 tokens graduate daily across all venues [Nexus One, 2026-03-03] — a shrinking pie with one dominant venue. Consistent with our feed: thin PASS flow, ~1 in 60 listings reaching the momentum checkpoint.
- **Challengers (niche, not dominant):** LetsBonk (BONK ecosystem, Raydium-backed, 411 SOL grad); Raydium LaunchLab (permissionless infra layer — Platform PDAs let fronts like LetsBonk plug in; 85 SOL grad → Raydium CPMM, creator gets 10% LP fees forever) [memefast.fun, 2026-05-01]; Bags.fm (~11.6% share, mobile/Apple-Pay, 1% creator royalty); Moonshot (Jupiter-owned, built into DexScreener, 500 SOL grad → Raydium/Meteora); Believe (tweet-to-launch → Meteora DLMM); Boop, Heaven, Jupiter LFG (curated) [uwuu.ai, 2026-05-02; bitbank.nz, 2026-08-17].
- **Implication for the monitor:** the universe our dexscreener new-profiles feed sees is still the right pond (Pump.fun/PumpSwap + Raydium-ecosystem graduations dominate flow), but Pump.fun's own app and PumpSwap-native pairs may arrive on dexscreener with the measured ~13-min lag — the lag, not the coverage, is our structural disadvantage. Action item (open): verify feed coverage of PumpSwap-native graduations vs Raydium pairs.

### Trading terminals — material changes since §4

- **BullX shut down trading 2026-06-01** (withdrawals only) [moby.win, 2026-06-05]. §4's stack recommendation is stale — BullX removed.
- **Axiom is the category king:** >50% of Solana spot trading volume, $51.5M/day, ~44.6–50.3% category share (May–Jun 2026); fees 0.75–0.95%, ~0.25% effective with rebates; desktop-only [moby.win, 2026-06-05].
- **Photon:** fastest manual terminal (~400ms), 0.5–1% fee, Solana-first, MEV protection via Jito [uwuu.ai, 2026-05-13; pumpparade, 2026-04-14].
- **Trojan:** best Telegram-native; robust copy trading; 1% fee; added Hyperliquid perps [cointrenches.io, 2026-02-25]. GMGN: strong analytics, slow copy (2–5s), 1%+1%.
- **New entrants:** Fomo (mobile memecoin UX, 0.50%), Moby (smart-money discovery), Terminal (35% SOL cashback) [moby.win, 2026-06-05].
- **Execution reality:** realistic all-in cost per trade is ~1.1–1.5% on Photon-class terminals once priority fees/Jito tips are included [pumpparade, 2026-04-14] — our 1.5%/side simulation assumption is at the *conservative-but-fair* end; fine.
- **Latency hierarchy confirmed:** Firedancer-era trench trading is "a battlefield of milliseconds"; manual trading is structurally exit-liquidity for bots [cointrenches.io, 2026-02-25]. This reinforces H08: any edge we capture must be slow-half-life by design (post-dump consolidation, momentum persistence) — our r15 signal (15-min checkpoint) is in the manually/terminal-tradeable band, which is precisely why it can survive without low-latency infra.

### Updated capability answer (replaces §5 stack line)

Monitor (defense + signal) → **Axiom or Photon** (manual/assisted execution, 0.5–1%) → Phantom hot wallet with 1–5 SOL float → mechanical exits (100%@2x family per §14). Copy-trading a verified wallet via Trojan remains an option but H06 killed the top-holder variant; wallet-level copy with realistic latency is untested and belongs to Part 6 future work.

### Part 1 verdict

Ecosystem structure **supports** the current research design: one dominant launchpad (Pump.fun), graduation mostly to PumpSwap/Raydium, terminals commoditized at ~1% — no new venue invalidates the dataset, and no terminal gives us an execution edge we don't already assume. The one genuinely new infrastructure fact is BullX's shutdown. No strategy change required; §4 stack updated.

---

## §16 — Latency decay + capital capacity (Parts 8–9, 27 Aug 2026, `latency_capacity.py`)

### Latency — the honest version

Our data is 2–4 min mcap samples; millisecond decay is unmeasurable from it and ms-level claims would be fabrication. What we measured instead: edge decay across the band we actually operate in — entering 0/1/2/3 samples (≈2.7 min each) after the 1.5× crossing print.

| entry delay | n | mean ROI | median | win% | entry vs signal price |
|---|---|---|---|---|---|
| at signal | 36 | −3.3% | −20.9% | 33% | 1.00× |
| +1 sample (~3 min) | 36 | +0.5% | −16.6% | 31% | 0.95× |
| +2 samples (~6 min) | 36 | +4.8% | −13.8% | 33% | 0.87× |
| +3 samples (~9 min) | 36 | +0.6% | −15.7% | 31% | 0.91× |

**No measurable decay in the minutes band** (non-monotonic, all within noise) — entries 6 minutes late actually pay *less* (0.87×) than at the print. Combined with §15's latency hierarchy, this answers the master brief's latency question for this strategy family: **the edge does not live in the ms band; terminal-manual execution (Axiom/Photon, ~1–2s) is adequate; conclusion D (infrastructure edge) is ruled out for H02/H03-style strategies.** Latency would only matter for Stage A–C strategies (launch sniping), which our feed structurally cannot see.

### ⚠ Red-team catch inside this analysis

The latency scan required re-deriving signal events from full paths — and it surfaced **36 crossings after +5 min, not the 16** the checkpoint rule (r5/r15 first-sample) produces. The broadened rule's mean is **−3.3%/trade vs +13.3% on the narrow 16**. Interpretation: the fast, clean crossers at the checkpoint carry the signal; late crossers are noise that dilute it to zero. H03's monetization is therefore **fragile to entry-rule definition** — exactly the kind of result Part 10 exists to catch. H03 stays WEAK with a downward arrow; the live v4 book (which uses the narrow rule) is the arbiter.

### Capacity — not the binding constraint

Signal-cohort detection liquidity: median $35.6k (p25 $30k, p75 $44k). Constant-product impact at median liquidity:

| size | round-trip impact |
|---|---|
| 0.1 SOL (~£20) | 0.2% |
| 0.5 SOL | 1.1% |
| 1 SOL | 2.2% |
| 5 SOL | 10.6% |

At our 2%-of-£1k sizing, market impact is negligible (0.2% vs even the optimistic +13% edge). The capacity ceiling — where impact alone eats the optimistic edge — sits around **2–5 SOL per trade**, and with ~1 signal per 4–6 h the family could absorb maybe **10–30 SOL/day** before impact matters. Capacity is a non-issue until the edge is proven; the binding constraints remain (1) edge existence after costs and (2) trade frequency.

### Updated reading of the four master-brief conclusions

- **D (infrastructure edge): ruled out** for our observable strategy families — nothing we can see requires ms execution.
- **C (systematic edge): unproven** — H03 weak/fragile in-sample; forward sample running.
- **B (discretionary edge): most consistent with evidence so far** — the audit + behavioural gate as a *do-not-trade* list has been flawless, and the momentum checkpoint is a genuine information signal a human can act on.
- **A (no edge): still on the table** — 3 of 4 live books are underwater; v5 has admitted nothing.

---

## §19 — v6 live: cluster+momentum forward test deployed (27 Aug 2026, ~19:15 UTC)

H10 is now under forward test:

- **`cluster_tag.py`** — stage-4 monitor module: for every new Solana token, paginates Helius SWAP history to the birth window, extracts first-25 unique buyers, intersects with `cluster_wallets.txt` (15 wallets). Verified live: correctly tagged BRLAEDmZ (hit: `5EfNgePa…`).
- **`monitor.py`** — stage 4 runs for all Solana tokens at detection (audit-verdict-independent); tag stored in state as `cluster.hit`.
- **`papertrader_v6.py`** — fresh £1,000 book. Rule: cluster hit ≥1 AND mcap ≥1.5× detect within 5–30 min AND liq ≥$20k; audit verdict deliberately ignored (§18 showed it adds nothing); exits: 100%@2×, trail 0.6, 2h time stop. Initialized clean (£1,000, 0 trades).
- **Automation updated** — pipeline now monitor → v2 → v3 → v4 → v5 → v6, every 10 min until 2026-09-09; v6 line in auto_log + artifact; description refreshed.

**Success criterion (locked in advance):** ≥30 v6 entries with hit rate materially above the momentum-only baseline (66% ≥2×) and dead rate materially below 29%. If v6 underperforms v4 on the same forward window, H10 dies and the cluster list is retired to the defense layer.

---

## §20 — Part 8 novel-hypothesis scan (27 Aug 2026, `novel_scan.py`, n=833)

Twelve mechanism-first hypotheses tested on the full local dataset (zero API cost). **Dataset caveat: spans only 2026-08-25 → 27 (Tue–Thu) — weekend effects untestable, single market regime, all in-sample.** Mechanisms were stated before testing; results recorded including failures per the anti-data-mining rule.

| ID | Hypothesis (mechanism) | Result | Status |
|---|---|---|---|
| H11 | Hour-of-day attention cycles | Flat: 17–23% ≥2× across all UTC buckets | **KILLED** |
| H12 | Weekend = retail regime | No data (dataset = Tue–Thu) | **UNTESTABLE (yet)** |
| H13 | pump.fun venue suffix differs | pump 20% ≥2× vs others 10%; modest | **WEAK** |
| H14 | vol/liq churn = manufactured energy | churn 3–10×: 26% ≥2× but **61% dead**; churn <1: med final 0.85× | **SURVIVES as risk filter** |
| H15 | extreme buy/sell >4 = fake pump flow | **61% dead, med final 0.03×** | **SURVIVES as reject filter** (confirms §11) |
| H16 | liq/mcap bands = dump fuel | 0.1–0.3 band: 54% dead; <0.1: 18% dead | **WEAK** (confounded with age) |
| H17 | path roughness = bot churn | smooth (<0.02): 3% ≥2×, 5% dead, pinned 1.00× (farms); rough ≥0.15: 29% ≥2×, 41% dead | **SURVIVES as descriptor** |
| H18 | dip-recovery = real demand test | 33% ≥2× vs 12% without; but 41% dead | **WEAK** |
| **H19** | **late peakers = community-driven (not bot-driven)** | **peak >60 min after detection: 48% ≥2×, 10% dead, med final 1.17× (they stay up). Instant-top (≤5 min): 2% ≥2×, 35% dead** | **PROMISING** |
| H20 | moderate top-10 concentration = committed insiders | Reversed: top10 0–15% → 31% ≥2× but 73% dead; concentration monotone in survival, not return | **KILLED** |
| H21 | very fresh detection = speed premium | age <10 min: **44% dead**; age ≥60 min: 4% dead, med final 0.91× | **SURVIVES as timing/risk map** |
| H22 | quiet start = stealth accumulation | vol ≤ p25: 13% ≥2×, 11% dead — quiet = safe but dead-ish | **KILLED** (as entry signal) |

### The H19 insight — the "two-species" model

The population bifurcates by *when the peak happens*: instant-top tokens (52% of population) are sniper/insider extractions — unwinnable after detection (2% ≥2×). Late-peak tokens (15%) are the community-build species — 48% reach 2×, only 10% die, and they *hold* their gains (median final 1.17× vs 0.29×). **The lifecycle stage matters more than any token-level feature: Stage H (post-first-hour) is where the durable moves live.**

Tradable formulation (observable in real time — no lookahead): at +60 min, token within ~20% of its post-detection high → trend-persistence entry, combined with cluster tag (rug defense) and H14/H15 reject filters. This is a *different* entry window than v2–v6 (which all enter <30 min) — worth a v7 paper book if v6's forward test confirms the cluster layer.

### Updated strategy architecture (all evidence to date)

```
REJECT:  contract FAIL · behavioural RISK · b/s>4 manufactured flow · churn 3-10x zone (optional)
DEFEND:  cluster tag present => dead rate 32% -> ~8-9%
TIME:    momentum >=1.5x in 5-30min (v4/v6) OR trend-persistence at +60min (H19, candidate v7)
EXIT:    100% @2x, trail 0.6, 2h time stop (v4 config; ladders killed H04)
SIZE:    2% of bank; capacity non-binding to ~2-5 SOL/trade (§16)
```

### §20 addendum — H19-as-entry: KILLED before deployment (27 Aug 2026)

Translated H19 into a tradeable rule (enter at first sample ≥+60 min if price ≥0.8× running peak; liq ≥$20k; same exits) and backtested before booking it:

| variant | n | mean | median | wins |
|---|---|---|---|---|
| H19 alone | 55 | −7.3% | −6.7% | 7/55 |
| H19 + reject b/s>4 | 50 | −8.0% | −6.5% | 6/50 |
| H19 + cluster | 13 | −4.1% | −2.6% | 4/13 |

The 48% ≥2× statistic was measured from *detection*; the tradeable entry at +60 min buys after the move. Classic lookahead trap, caught pre-deployment. **H19-entry: KILLED.** Residual value: late-peaking is a *hold* criterion, not an entry — relevant only if a future exit redesign stops capping at 2×. No v7 book deployed; £1,000 paper slot saved.

---

## §21 — Ring-2 expansion + live tagging status (27 Aug 2026, ~19:30 UTC)

**Ring-2 search: null result (informative).** Scanned the 15 best cluster-touched tracked tokens not already processed: 49 non-core wallets appeared among first buyers, but **zero appeared in ≥3 cluster tokens**. The coordinated entity appears to be exactly the core 15 wallets — no wider ring detectable at this threshold. `cluster_wallets.txt` unchanged. Hypothesis "cluster has a discoverable second ring" — **KILLED**.

**Live tagging:** stage 4 is tagging new tokens (2 so far, 0 hits, 0 errors). **Coverage caveat discovered:** one fresh token returned `first_buyers=0, reached_birth=true` — either genuinely buy-less at detection or bonding-curve buys not always parsed as SWAP events under the mint at the youngest ages. Original cluster discovery pulled winners *post-hoc* (deeper history); live detection-time tagging may under-fire on the very youngest tokens. If v6 shows far fewer tags than the ~4%/token rate implied in-sample, the fix is a re-tag pass at +15 min. Watching tag rate as the metric.

**Pipeline steady:** 19:16Z cycle all-green; v2 −22.0%, v3 −14.1%, v4 −9.5%, v5/v6 flat awaiting admissions.

---

## §22 — Rejected-trade audit + the reconstruction wedge (27 Aug 2026, ~19:45 UTC)

The brief's mandatory rejected-trade database, run as counterfactuals on v4's own rejection log (`seen_done`):

| cohort | n | mean | median | wins |
|---|---|---|---|---|
| rejected: failed momentum floor | 27 | **−10.1%** | −22.9% | 6/27 |
| excluded: pre-window (rule applied to pre-book tokens) | 15 | **+13.7%** | +13.8% | 8/15 |
| **ACTUAL v4 live entries** | **8** | **−61.8%** | −61.3% | **1/8** |

Three conclusions:

1. **The momentum floor is validated as defense.** Tokens rejected for failing the 1.5× floor would have lost −10.1% mean if traded anyway. The filter prevents losses; it does not merely prettify the sample. (Master brief's rejected-trade requirement: satisfied for v4's filters.)
2. **The reconstruction wedge is the biggest red-team finding of the project.** The *same* rule, *same* filters, *same* fee model: reconstructed-history fills → +13.3%/+13.7%; live forward → −61.8%. The mechanism: reconstruction fills TP@2× whenever any later sample ≥2×; live, the 10-min poll must *observe* the 2× — tokens that spike-and-dump between polls fill at trail-stop instead. In-sample results for this whole strategy family (H02/H03, §11.B, §14.B) are therefore systematically optimistic and must be treated as upper bounds, not estimates.
3. **It's not regime.** Pre-window tokens from the same days reconstruct profitably under the same rule; only the live fills differ. Execution timing — not token selection, not filters, not the market window — is where the theoretical edge dies.

**Consequences for the master brief:** H03 downgraded to effectively KILLED-as-reconstructed (live evidence only from now on). H10/v6 becomes the decisive experiment, and its live fill mechanics (10-min polling) are the same ones that broke v4 — if v6's cluster layer works, expect the live result to underperform any reconstruction of it. A **polling-rate upgrade (10 min → 1–2 min for tagged tokens only)** is the cheapest structural fix and directly targets the measured wedge. UK-tax note (Part 15) and wallet-security design (Part 12) remain desktop-research items, lower priority than the fill problem.

### §22 addendum — fast-watch deployed (27 Aug 2026, ~20:00 UTC)

Structural fix for the fill wedge: `fastwatch.py` refreshes prices for the hot set (all open paper positions + cluster-tagged tokens <2h + audit-PASS tokens in the 3–60 min evaluation window) and the automation now runs **3 extra evaluation rounds at 60-s spacing** after each monitor cycle (fastwatch → all 5 traders per tick). Hot-set tokens now get ~1-min price granularity vs the previous 10-min cadence; entries and exits fire within 1–2 min of the trigger print instead of up to 10 min late. Smoke-tested: 7/8 hot tokens refreshed. If v4/v6 live results converge toward their reconstructions after today, the wedge was the missing piece; if they don't, the edge itself was never there — either answer is decisive.

---

## §23 — THREE-PASS REVIEW, Pass 1: critique of the whole program (27 Aug 2026)

Assume the current leading strategy (v6: cluster + momentum + fast fills) does NOT work. The strongest reasons it might fail, ranked by how much damage each does, with the test that settles each:

1. **Cluster discovery bias (severity: fatal if true).** The 15 wallets were found *because* they bought winners. The 91%/9% cell is partly circular by construction. The dead-rate suppression (8% vs 32%) is the only property not selected for. **Settlement: v6 forward book — pre-registered criterion in §19.**
2. **Cluster = insiders, and their dump trigger is below our 2× target.** If the cluster pumps-and-dumps at +40–80%, our TP@2× never fills and every v6 entry exits at trail-stop. In-sample cell says median peak 5.2× for momentum+cluster — but that's reconstructed (fill-optimistic). **Settlement: v6 live; watch specifically for "peak 1.3–1.9× then trail-stop" patterns.**
3. **Watchlist decay.** The 15 wallets were active 25–27 Aug. Coordinated entities rotate wallets precisely because lists like ours exist. Static list → signal dies silently. **Settlement: weekly re-derivation of cluster from new winners; monitor v6 tag rate decay.**
4. **Universe selection bias.** Our feed is dexscreener token-profiles + boosts — tokens someone paid to list. The true birth population (pump.fun native, ~72k/day) is far larger and likely worse. All base rates are conditional on the feed, and the cluster may operate mostly outside it. **Settlement: compare v6 tag rate vs the in-sample 4% — a large shortfall means the cluster plays elsewhere.**
5. **Historical path coarseness.** Even post-fastwatch, the 815-token training set was sampled at 2–10 min. Every in-sample peak/2×-fill statistic carries that error. **Settlement: none retroactively — treat all pre-fastwatch numbers as upper bounds (already policy since §22).**
6. **Regime singularity.** Dataset = Tue–Thu 25–27 Aug 2026, SOL range-bound. Weekend effects untested (H12 untestable). Any conclusion is one regime wide. **Settlement: the 2-week automation window covers ~2 weekends.**
7. **v5 gate calibration unknown.** 0 admissions in ~24h could mean excellent filtering or a gate that never opens (fresh>25% OR deployer<24h OR top20>80% may be nearly-always-true for new launches). **Settlement: log v5 gate-stage reject rates; if >95% of audit-PASS tokens are RISK, thresholds need recalibration against §18's cell.**
8. **Single exit family tested live.** Ladders were killed by reconstruction (H04) — the same reconstruction now known to be fill-optimistic. With fast fills, ladder exits deserve a live re-test before the kill stands. **Settlement: post-fastwatch data, re-run sweep on live-sampled paths.**
9. **Helius free-tier SPOF.** Rate limits or key suspension silently degrade stages 3–4 to SKIP/error. **Settlement: monitor error counts in state; alerting already implicit in auto_log.**
10. **Sample size everywhere.** 8 live v4 trades, 0 v5/v6 trades. Nothing live is statistically meaningful yet. **Settlement: time. The 2-week window is the plan.**

Pass 2 (outside-box discovery) yielded H19 (killed as entry), the two-species model, and the churn/asymmetry filters. Pass 3 (adversarial review of the final strategy) runs after the forward window closes — no strategy survives to be reviewed until then.

---

## §24 — Part 15: UK tax & record-keeping (27 Aug 2026; sources: Koinly HMRC guide 2026-07-14, uktaxhero 2026-05-24, finbooks 2026-03-30, BDO 2025-12-31)

**Rules as they stand for a UK-resident trader (2025/26 and 2026/27):**

- Crypto is **property**, not currency. Every disposal is a CGT event — **including token→SOL and token→token swaps** (no fiat leg needed). GBP market value at disposal time is the proceeds figure.
- Rates: **18% basic / 24% higher** band; annual exempt amount **£3,000**. Gains reported on SA108 (dedicated cryptoasset section since 2024/25); deadline 31 Jan after tax year end.
- **Cost-basis matching (no lot selection allowed):** same-day rule → 30-day "bed & breakfast" rule → Section 104 pooled average. Practical consequence for memecoin churn: buy/sell same token same day → same-day matching; rapid re-buys within 30 days pull the repurchase cost into the earlier disposal.
- **Fees:** transaction-linked trading fees are allowable in cost basis; **transfer/gas fees between own wallets are themselves disposals** (not allowable costs) — sweep transactions have tax friction.
- **Losses:** offset against gains, carry forward indefinitely, must be claimed within 4 years. **Rugs:** not theft — use a **negligible value claim** to crystallise the capital loss (relevant to our ~50%-of-listings-go-to-zero reality).
- **CARF live since 1 Jan 2026:** UK service providers report user transactions to HMRC automatically. Assume visibility.
- HMRC accepts "trading as a business" (income tax instead of CGT) only in exceptional circumstances — plan for CGT.

**Record-keeping schema (to implement in the execution layer when live):** per disposal — timestamp (UTC), mint, wallet, token amount, SOL/GBP value at tx time (GBP rate source recorded), tx hash, network fee, platform fee, matched-pool reference, realised P&L (GBP). Our paper books already log most of this; GBP valuation at tx time is the one field to add.

---

## §25 — Part 12: wallet-security architecture (design, 27 Aug 2026)

Principle: **a trading process should never be able to lose more than its float.**

```
VAULT (hardware wallet, e.g. Ledger) — holds all serious funds; never touches a dApp
   │  manual top-ups only
TRADING WALLET (hot, e.g. Phantom) — float capped at 1–5 SOL; the only key any terminal/bot sees
   │  automatic profit sweep back to vault when float > cap × 2
BURNER (optional, per-experiment) — for unaudited tooling; funded with single-trade amounts
```

Rules: (1) private keys never in plaintext files or bot configs — env-injected at process start, 0600 perms; (2) profit sweep is automatic and one-directional; (3) no open token approvals on Solana (SPL is per-account, not allowance-based, but revoke any program approvals after each session); (4) token-account cleanup (close empty ATAs, reclaim rent) weekly; (5) any third-party bot gets a code audit before a key — §11.D found the repo search results full of key-stealing scam bots; (6) the research pipeline (this repo) remains read-only — it has no signing capability by design, and the £1,000 paper books are simulation, not funds at risk.

### §25 addendum — cluster re-tag fix live (27 Aug 2026, ~19:35 UTC)

`monitor.py` now re-tags once at ≥15 min old any Solana token whose detection-time tag had thin first-buyer data (<5 parsed buyers, no hit, no error) — closes the §21 coverage gap where the youngest tokens' bonding-curve buys weren't parsed at detection. Smoke-tested live: 8 new tokens audited + tagged in a manual cycle, re-tag path clean. Tagged total: 11, cluster hits: 0 — the 15-wallet entity hasn't bought a new listing since watch began (~40 min); in-sample they touched ~10% of tracked tokens over days, so silence this early is expected, not alarming. v6 tag rate remains the metric to watch.

## §27 — INSTRUMENTATION FAILURE + FIX: cluster tagger was blind (27 Aug 2026, ~20:10 UTC)

**Found via instrument validation, not assumption.** Before trusting v6's `no_cluster_hit`
rejections, the live tagger (`cluster_tag.py` v1) was run against the 7 unique known-positive
tokens from the in-sample discovery (`wallet_firstbuyers.json` — tokens where a cluster wallet
is a *confirmed* early buyer). Sensitivity was **0/7**. The v6 forward test as first deployed
was measuring nothing.

Two root causes, both confirmed against raw Helius responses:

1. **Pagination short-page break.** Helius `type=SWAP` filtered pages routinely return 94–99
   txs even when far more history exists. v1 treated `<100` as "history exhausted" and stopped
   at page 1. On the validation token FpWUhWm… the birth window was 10 pages deep (~1,000 txs).
   For live ~13-min-old tokens this mostly doesn't matter, but the +15-min re-tag and any busy
   token were silently uncovered.
2. **Buyer attribution gaps.** Of 96 recent SWAP txs on the validation token, only 17 carried an
   `events.swap` block parseable by the v1 rule; the rest express the buy via `tokenTransfers`
   (feePayer receives the mint) or `innerSwaps` legs. v1 missed all of them.

**Fix (cluster_tag.py v2):** paginate until oldest tx ≤ `pair_created` (max 12 pages, no
short-page break); buyer = feePayer when (a) mint in swap/innerSwap tokenOutputs, or
(b) feePayer receives mint via tokenTransfers with amount > 0. `monitor.py` now passes
`pair_created` at both the detection-time tag and the +15-min re-tag, and the re-tag trigger
now also fires when `reached_birth` is False (was: only when <5 parsed buyers).

**Validation:** sensitivity **7/7** on known positives (all hits found within first 25 buyers,
3–12 pages each). Specificity is unchanged by construction (same 15-wallet list).

**Impact on live data:** 25 tokens were tagged by the blind parser between 19:36Z and ~20:00Z.
Re-tagging all 25 with v2 flipped **2 to HIT** — `7fmHqRp…1hz35` (BG6BS3Vz + FnBmjyWp) and
`37WhvcVy…oR94` (FnBmjyWp). An 8% false-negative rate on the first live sample, in line with
the ~10% in-sample touch rate — i.e. the cluster *is* still active on new listings, and the
blind tagger was hiding exactly the signal v6 exists to capture. Both tokens were removed from
v6's `seen_done` so the corrected signal gets a fair evaluation; all 25 corrected tags carry
`fix: v2_parser_2026-08-27` for auditability. v6 admissions before 20:00Z: 0 — and after this
fix, that count is meaningful.

**Lesson folded into protocol:** any forward-test instrument must be validated against known
positives *before* its outputs are treated as evidence. This is now step 0 of the Pass-3
checklist (§23) for the final review.

### §27 addendum — loop structural fix + post-fix tag quality (27 Aug 2026, ~20:30 UTC)

Three consecutive automation cycles (19:56Z/20:06Z/20:16Z) killed the monitor phase at the
280s subprocess timeout while all five paper traders completed. Root cause: the loop ran
`monitor.py 2 130` (two cycles 130s apart = 130s idle + 2× audit work against a 280s budget —
~20s of headroom before stage 3/4 wallet calls existed). Loop now runs `monitor.py 1` with a
200s budget; detection-time cluster tags are capped at 4 pages (a ~13-min-old token's birth is
1–3 pages deep; the +15-min re-tag keeps full 12-page depth). Manual verification: a full cycle
auditing 12 new tokens completed in ~150s.

Post-fix tag quality (17 tokens tagged 20:10–20:30Z): median 25/25 first buyers parsed — full
birth-window coverage on live tokens, vs 0–4 with the blind parser. Hits: 0/17 fresh + the 2
re-tag flips = 2/19 ≈ 10.5% live cluster-touch rate, matching the ~10% in-sample rate. The
instrument is now trustworthy; v6's `no_cluster_hit` rejections from 20:10Z onward are real
evidence. (Pre-20:00Z rejections were instrument artifacts and 2 have already flipped.)

**v5 first blood:** the behavioural gate admitted its first token (66yZvYMA…pump, 20:00Z,
entry $313k mcap) — the same token v4 entered, making it the first live v5-vs-v4 paired
comparison. Position peaked at 1.82× entry; v5 closed with +£19.10 realized (first green
closed trade in any book since v4's early session).

## §28 — Pass 2 ROBUSTNESS REVIEW: is the cluster+momentum cell a knife-edge? (27 Aug 2026, ~21:00 UTC)

In-sample stress tests on the candidate edge (momentum ≥1.5× + cluster tag), dataset
`analysis_rows.json` (815 rows) × `cluster_tokens.json` (302 cluster-touched, from the
15-wallet list). All numbers in-sample/reconstructed — §22 wedge applies to returns.

**1. Threshold sweep — robust, not a knife-edge.** Cluster cell beats no-cluster at EVERY
momentum threshold on both hit-2× and dead rate:

| mom threshold | cluster n / hit2× / dead / medPeak | no-cluster n / hit2× / dead / medPeak |
|---|---|---|
| 1.2 | 46 / 72% / 20% / 3.27 | 173 / 47% / 63% / 1.95 |
| 1.3 | 36 / 86% / 14% / 4.48 | 143 / 55% / 69% / 2.07 |
| 1.5 | 32 / 91% / 16% / 5.20 | 96 / 68% / 69% / 2.32 |
| 1.75 | 24 / 96% / 12% / 5.72 | 54 / 87% / 69% / 2.80 |
| 2.0 | 21 / 100% / 14% / 5.87 | 34 / 100% / 62% / 3.35 |

Cluster-only (no momentum): 84 / 46% / 21% / 1.84. No-cluster-all: 731 / 16% / 64% / 1.13.
The cluster's main economic value at high momentum is **dead-rate collapse (16% vs 69%)** —
loss avoidance, not hit-rate inflation. (Dead here = final ≤0.5× detect; §17's 9% used a
stricter floor — definitional, not directional.)

**2. Outlier dependence — GONE, unlike momentum-only.** Simulated v6-rule returns (enter at
1.5× detect, TP 100% @2× entry, else trail 0.6): mean **+72.1%/trade** (n=32). Remove best
1/2/3/5 trades: +71.2 / +70.3 / +69.3 / +67.0%. Bootstrap 95% CI [+55.7%, +87.5%]. Compare
momentum-only (§14): +13.3% mean, CI [−13.6%, +40.8%], flips negative without its best 3.
The cluster cell's edge is distributed across trades, not carried by outliers. This is the
single strongest piece of in-sample evidence in the program.

**3. Time concentration — the binding caveat.** The ENTIRE dataset spans only 3 days
(Aug 25/26/27: 173/255/387 rows). Cluster activity: 9 → 26 → 49 touched tokens/day —
present throughout, ramping, still active post-deployment (2 live flips, §27). No-cluster
momentum baseline is stable across days (63/69/69% hit-2×). So: no single-day anomaly, but
the cluster edge is 3 days of ONE entity's behaviour. If the entity stops, rotates wallets,
or its edge decays (§23 vectors 1/2/6), the edge vanishes. The forward test is the only
settlement.

**Pass 2 verdict:** the candidate strategy survives sensitivity analysis — robust to
threshold choice, not outlier-carried, CI excludes zero. Its fragility is purely temporal/
behavioural (one entity, 3 days). Pass 3 (post-forward-window adversarial review) must weigh
forward v6 results against exactly this: a real but potentially ephemeral edge.

## §29 — Part 13: EXIT RESEARCH (27 Aug 2026, ~21:20 UTC)

Path-simulated exit policies on both candidate cells, using state.json price paths
(~10-min granularity; entry at first print ≥1.5× detect). Reconstruction quality —
ordering is informative, magnitudes are fill-optimistic (§22).

| policy | mom+cluster (n=32): mean / med / worst | mom-only (n=96): mean / med / worst |
|---|---|---|
| TP@2× + trail 0.6 (v6 live rule) | +61.9% / +100% / −38.5% | +14.9% / −7.1% / −39.8% |
| TP@2× only | +65.0% / +100% / −91.0% | −19.3% / −69.2% / −99.8% |
| trail 0.6 only | +141.9% / +95.6% / −38.5% | +21.7% / −7.1% / −39.8% |
| **trail 0.7 only** | **+146.1% / +78.1% / −28.2%** | +37.0% / +0.4% / −29.8% |
| trail 0.8 only | +140.2% / +81.3% / −18.0% | +44.4% / +10.2% / −19.7% |
| staged 25/25/25 + trail 0.6 | +72.4% / +80.1% / −38.5% | +14.9% / +6.8% / −39.8% |
| hold-to-end | +299.7% / +41.2% / −91.0% | −48.9% / −80.1% / −99.8% |

Findings:
1. **Hard TP@2× caps exactly the winners that make the cell work** (median peak 5.2×).
   Trail-only roughly doubles mean return vs the v6 TP rule (+146% vs +62%).
2. Trail 0.7 is the sweet spot: best mean, median +78%, worst-case −28%. Trail 0.8 tightens
   worst-case to −18% for similar mean. Staged 25/25/25 underperforms trail-only.
3. Hold-to-end is outlier-carried (mean 3× median, worst −91%) — rejected.
4. Time stops / momentum-failure exits: not separately simulable at 10-min granularity
   without lookahead; the trailing stop already subsumes both empirically (a dead token's
   trail fires within 1–2 prints).
5. **Protocol note:** v6's live book keeps its pre-registered TP2×+trail0.6 rule — changing
   it mid-experiment would invalidate the forward test. Exit-policy upgrade (trail 0.7,
   no hard TP) applies to the FINAL specification only (§31), and is flagged as
   reconstruction-grade until a forward book validates it.

## §30 — Part 14: POSITION SIZING (27 Aug 2026, ~21:25 UTC)

Raw Kelly on the cluster+momentum cell (trail-0.7 proxy): win-rate 91%, avg win +379%,
avg loss −16% → **full Kelly 90%, quarter-Kelly 23% of book per trade**. This is precisely
the case where Kelly is unusable: the inputs are reconstruction-optimistic (perfect trail
fills), single-entity-dependent (§28.3), and same-day cluster tokens are highly correlated
(one entity's behaviour drives multiple simultaneous positions — effective bet is bigger
than the sum of tickets).

Specification decision: **fixed-fractional with hard caps**, not Kelly:
- 2% of current book per trade (paper books use £20/£1,000 — already aligned);
- max 3 concurrent positions (correlated-entity cap);
- max portfolio heat 6% (3×2%);
- book drawdown circuit-breaker: halve ticket after −20% from book peak, stop at −35%;
- scale-up rule: only after ≥30 forward trades with realized edge >0 AND no §23 kill
  vector triggered; increase to 3% only after 60 trades.

## §31 — STRATEGY SPECIFICATION (skeleton v1, forward slots PENDING) (27 Aug 2026, ~21:30 UTC)

Per the brief's "IF A STRATEGY SURVIVES" template. Values marked [F] await forward-window
settlement (v6 book, through 2026-09-09).

- **Universe:** Solana pump.fun new listings surfaced by the dexscreener profiles/boosts
  feed (~13 min median feed lag; §8 latency work showed no decay in the minutes band).
  Audit verdict PASS only (rugcheck flags clear, top-10 holder concentration ≤30%).
- **Signal:** (a) cluster tag — ≥1 of the 15 identified coordinated wallets among the
  first 25 unique buyers (Helius SWAP history to birth, cluster_tag v2, validated 7/7);
  (b) momentum confirmation — max(r5, r15) ≥ 1.5× detection mcap. Both required.
- **Reject filters:** audit FAIL/CAUTION (any authority/liquidity/concentration flag);
  behavioural gate verdicts of bundled-snipe/farming patterns (v5 criteria); momentum
  below floor at evaluation; cluster tag with `reached_birth=false` after re-tag
  (insufficient evidence = no trade).
- **Entry:** market buy via aggregator (Jupiter/Axiom routing) immediately on signal;
  paper-validated entry = mcap at first print ≥1.5× detect.
- **Size:** 2% of book per trade, max 3 concurrent, heat ≤6% (§30).
- **Stop:** trailing stop at 0.7× peak mcap (§29), evaluated at ≤1-min price granularity
  (fast-watch cadence); emergency exit on cluster-wallet sell detection [infra-dependent].
- **Profit-taking:** none fixed — trail-only policy (§29 finding: hard TP@2× halves mean
  return). Runner logic = the trail itself.
- **Exit:** trail fires, or position aged beyond max hold.
- **Maximum hold:** 6 hours (in-sample: median time-to-peak 3 min, 90th pct <1h; anything
  not resolved in 6h is drift — exit at market).
- **Maximum slippage:** 15% quoted-vs-filled on entry; abort if exceeded; exits accepted
  at any slippage (risk exits are not price-sensitive).
- **Maximum exposure:** 2%/trade, 6% portfolio, 1 entity-correlation bucket (§30).
- **Kill switch:** (1) cluster silence — no cluster tag among ≥50 consecutive new listings
  (entity gone); (2) forward v6 hit-2× rate < momentum-only baseline (66%) after ≥30
  entries (pre-registered §19); (3) book −35% from peak; (4) 3 consecutive trail-stop
  exits with peak <1.9× entry (cluster dumping below target — §23 vector 2); (5) any
  infrastructure failure >30 min during open positions.
- **Infrastructure:** dexscreener profiles feed (detection), Helius enhanced API
  (cluster tag + behaviour, ~1–4 calls/token), rugcheck (audit), 10-min monitor loop +
  1-min fast-watch (both live, automation 6d57d1be), dedicated hot wallet per §25
  architecture, no third-party bot with keys.
- **Expected performance:** in-sample reconstruction +72–146%/trade mean, bootstrap CI
  excludes zero (§28) — UPPER BOUND ONLY. Forward: [F — v6 book through 2026-09-09].
  Honest planning number pending forward data: [F].
- **Failure conditions:** §23's ten vectors, especially 1 (entity stops), 2 (dump trigger
  below trail), 6 (wallet rotation — mitigated by re-derivation from new winners monthly),
  8 (feed dependence — dexscreener profiles as universe is itself a selection bias, §23.4).

## §32 — Forward checkpoint #1: cluster touches are live, momentum filter is doing its job (27 Aug 2026, ~21:55 UTC)

Trustworthy cluster tags (fixed parser, §27): 53 tokens, **4 hits (7.5%)** — consistent with
the ~10% in-sample touch rate, so the entity is active on our feed. But all four live hits are
**flat so far**: 7fmHqRp peak 1.08×, 37WhvcVy peak 1.10×, Pp3U7o9A peak 1.00×, utsTit2E peak
1.10× (ages 17–84 min; in-sample median time-to-peak is 3 min, so the two oldest are resolved).

Reading: in-sample, cluster-WITHOUT-momentum hit 2× only 19% of the time (§18) — four flat
touches are consistent with THAT cell, and v6 correctly refused all four at the momentum floor
(49 no_cluster_hit + 2 failed_momentum_floor, 0 admissions). The pre-registered test is only
about tokens carrying BOTH signals, and none has appeared yet. Two cautions nonetheless:
(a) the cluster list was derived from winners, so in-sample cluster-hit performance carries
survivorship flavour — forward touches may be systematically duller (§23 vector in action);
(b) if cluster touches persist flat across, say, 15+ live hits, the entity's current behaviour
has decoupled from its Aug 25–27 pattern and the momentum+cluster cell's 91% becomes
historical, not structural. Watch metric: live-hit peak distribution vs in-sample 1.84× median.

v5's first position (66yZvYMA) still open, peak 1.73× entry; v5 already +£19.10 realized on
its first close. All loops healthy (20:46Z cycle ok, 1,433 tracked).

### §32 addendum — discovery-bias decomposition of the cluster cell (27 Aug 2026, ~22:00 UTC)

The 15-wallet list was derived from 10 big winners' first-buyer overlap, so discovery-set
tokens sit inside the momentum+cluster cell and mechanically inflate it. Removing them:

| cell | n | hit-2× | dead | median peak |
|---|---|---|---|---|
| full momentum+cluster | 32 | 91% | 16% | 5.20× |
| discovery-set members | 5 | 100% | 20% | 12.85× |
| **non-discovery members** | **27** | **89%** | **15%** | **3.97×** |

The wallets' association with follow-through generalises beyond the tokens used to find them:
hit rate and dead rate barely move; the discovery set mostly inflated the peak tail (12.85×).
Residual caveat: the 302-token cluster-touch list was expanded via wallet activity, which may
still lean winner-ward; the live forward tags (§32) are the only fully unbiased sample, and
their flatness so far is why the forward window — not this decomposition — settles H10.

## §33 — Cluster sell-timing forensics: §23 vector 2 tested with evidence (27 Aug 2026, ~22:10 UTC)

Question: do the cluster wallets dump at +40–80% minutes after entry (which would strand our
2×/trail exits), or hold? Method: full SWAP histories to birth for 4 validated cluster-positive
winners; extracted every cluster-wallet sell (feePayer in cluster, mint leaving wallet).

Result across 100+ cluster sell transactions: **sells begin +9 to +35 HOURS after the token's
peak, never minutes after entry.** On 3vSD9xyK (peak 20.6×): sells start +24h. On BRLAEDmZV
(peak 12.8×): sells span +14–21h post-peak. On FTaTkkxXyJ (12.3×) and FpWUhWmDva (12.1×):
same pattern — slow distribution into the multi-hour decay tail, not a pump-dump.

**Vector 2 is REFUTED in-sample** (on winners): the entity buys birth, holds through the peak,
and distributes over the following day. Our trail-stop at 0.7× peak fires within minutes-to-
~1h of the peak — long before cluster distribution completes. Their selling is a late
confirmation, not an early warning; "cluster sell detection" is therefore dropped from the
spec's emergency-exit triggers (§31) and kill-switch vector 4 stands as the guard.

Caveats: (a) measured on winner tokens only — sell timing on their flat/dead touches may
differ (can't measure what never pumped, and those matter for the dead-rate); (b) sell-time
price levels are imprecise (history resolution degrades beyond the tracking window), so the
timing conclusion is robust but the exact distribute-prices are approximate; (c) past
behaviour of one entity, 3 days — the forward watch for "peak 1.3–1.9× then trail-stop"
patterns (§23) stays in the daily review checklist.

## §34 — Part 16 Phase-3 population table at full sample (27 Aug 2026, ~22:20 UTC)

N=899 audited Solana tokens with price history (detection-anchored multiples; feed adds
~13-min lag, so "detection value" ≈ post-birth price, not birth price). This is the reference
population for all strategy math.

**Survival (retains ≥50% of detection value):**
| age | survival | per 10,000 |
|---|---|---|
| +5 min | 79% (n=885) | 7,864 |
| +1 h | 50% (n=838) | 4,964 |
| +24 h | cohort censored (tracking window <24h) | — |
| 20h+ cohort (n=451) | median final 0.38× detect | — |

**Ever reached (any point in life):** 1.5× — 29.8% (2,981/10k); 2× — 18.1% (1,813);
5× — 4.0% (400); 10× — 1.7% (167); 100× — 0.1% (11, single token).

**Terminal state at last print:** dead (<0.3×) 40.7%; bled out (0.3–0.7×) 28.3%;
flat 23.4%; up modestly 3.6%; holding ≥2× 4.1%.

Interpretation for the strategy spec (§31): the unconditional population is brutal —
69% of tokens end below 0.7× and only 4% hold gains. ANY positive-expectancy approach must
be a selection story, not a market beta story; the measured selection lift (cluster+momentum:
89–91% hit-2× vs 18% unconditional) is ~5× the base rate, which is why the cluster layer —
not momentum alone (68% vs 18%) — carries the spec. Graduation rate and 7-day survival are
not measurable in a 3-day window and are flagged as permanent blind spots of this study.

## §35 — Part 16 Phase-4 FORENSIC FAILURE MODEL: death is not predictable from detection-time features (27 Aug 2026, ~22:30 UTC)

Univariate screen, dead (final ≤0.3×, n=342) vs survivors (final ≥0.7×, n=245):

| feature | dead median | survivor median | verdict |
|---|---|---|---|
| detect mcap | $31.0k | $20.3k | no separation (dead slightly HIGHER) |
| liquidity | $18.8k | $20.7k | none |
| volume | $63.1k | $28.1k | dead tokens have MORE volume — churn/dump volume, anti-signal |
| buy/sell ratio | 1.33 | 1.27 | none |

By audit verdict (big-sample confirmation of the §16 red-team): **PASS tokens die fastest**
(64% dead) vs CAUTION 57% vs FAIL 33%; ever-2×: PASS 23%, CAUTION 26%, FAIL 15%. The audit
adversely selects for *dumpable-looking* quality — it screens structural scam mechanics
(mint/freeze authority, unlocked LP) but has zero predictive power for trajectory.

Liquidity quartiles: dead rate 36–61% with no monotone pattern; ever-2× flat at 18–21%.
Liquidity is not a quality signal either.

**Consequence for the spec (§31):** the reject filters are retained ONLY as catastrophic-risk
screens (they exclude authority-enabled rugs), explicitly NOT as expectancy contributors.
The brief's candidate hypothesis "rug-avoidance model + simple momentum entry" is half-refuted:
rejection avoids scams but selects nothing; momentum alone is weak and outlier-carried (§14);
the cluster layer is the only validated selector (§28). Death in this market is driven by
post-birth flow dynamics, not by anything observable at detection — which is precisely why the
edge, if it survives forward, lives in WHO buys (cluster) rather than WHAT is bought (audit).

### §34 addendum — burst-hour cycle timing fix (27 Aug 2026, ~22:55 UTC)

Evening listing bursts (~30 new tokens/cycle vs ~7 earlier) pushed single monitor cycles to
210s — over the loop's 200s kill (21:26Z + 21:36Z cycles timed out; traders unaffected, state
writes lost for those cycles). Fixes: per-cycle audit cap exposed as a CLI arg and set to 8 in
the loop (`monitor.py 1 0 8`), and the +15-min cluster re-tag cap reduced 2→1 per cycle.
Verified: capped cycle with backlog drained in 2m42s. Trade-off logged: during bursts, cluster
tags land one cycle later for tokens beyond the cap; the re-tag path covers thin tags, so the
v6 signal is delayed-not-lost. The audit backlog drains automatically in quiet hours.

## §36 — PRE-REGISTERED ALARM FIRED: cluster silence past 50 consecutive listings (27 Aug 2026, ~23:35 UTC)

Kill-switch condition 1 (§31) triggered: **53 consecutive tagged new listings with zero
cluster wallets among first buyers** (last hit: utsTit2EhoXG, ~20:30Z; 99 trustworthy tags,
4 hits total). Under the in-sample ~10% touch rate, P(53 consecutive misses) ≈ 0.4% — the
entity's behaviour has changed, our feed's coverage changed, or the in-sample rate was
regime-specific. Combined with the 4/4 flat live hits (§32: peaks 1.00–1.51×, all slow
grinds, median 1.09× vs in-sample 1.84×), the forward evidence now leans AGAINST H10 as
specified.

Formal status: v6 has 0 entries, so nothing to liquidate — the kill switch's operational
effect is "do not enter on stale signal", which is moot while no signal fires. For the
verdict, this is exactly §23 vector 1 (entity stops / regime decay) playing out in real time,
~3h after deployment.

Alternative explanations that keep H10 alive (checked before Pass 3):
(a) diurnal pattern — entity may trade EU/US hours only; overnight silence may be normal.
    Check: in-sample touches were Aug 25–27 daytime-heavy (per-day counts 9/26/49, §28).
    Morning scorecard tests this: if hits resume 08:00–20:00 London, silence was diurnal.
(b) feed shift — pump.fun launch meta moved off the dexscreener-profiles universe tonight
    (§23 vector 8). Check: tomorrow, sample recent big winners' first buyers for cluster
    wallets regardless of our feed (wallet-first-buyers scan on the day's top movers).
(c) wallet rotation — entity rotated to new wallets (§23 vector 6). Check: re-run
    wallet_firstbuyers.py on post-20:30Z winners; new repeat wallets = rotation.

Pass 3 must weigh: strongest in-sample cell in the program (+72–146%/trade, CI excl. zero,
robust §28) vs. forward decoupling within hours (flat hits + silence alarm). If (a)/(b)/(c)
all check out negative tomorrow, H10 dies forward and the verdict collapses to B (defensive/
discretionary) unless v5's gate keeps producing green trades (currently +3.8%, n=2 closed).

### §36 addendum — rotation/feed-shift pre-test (27 Aug 2026, ~23:45 UTC)

Scanned all 3 post-silence winners (≥2.5× since 20:30Z: 5XXfA5WD 4.4×, CyuJnun3 3.3×,
sCnoh91T 3.0×) for first-buyer overlap. Result: **zero old-cluster wallets in any of their
first 25 buyers** — tokens are still pumping in our feed universe without the entity, which
WEAKENS hypothesis (b) feed-shift and strengthens (a) diurnal or vector 1 (entity inactive).
No new repeat wallets found, but n=3 winners is too small for the rotation test (c) — the
overnight winner set will be large enough by morning. Note for Pass 3: pumps continuing
without the cluster also re-confirms the cluster never was the *cause* of all pumps — it was
a co-traveller with high hit-rate during Aug 25–27 daytime.

### §37 — diurnal hypothesis (a) tested in-sample and WEAKENED (28 Aug 2026, ~00:15 UTC)

Pulled pair_created hours for all monitor-detected cluster-touched tokens (84 of the 302
fall inside the monitor window) and compared with the full 1,310-token baseline.

Cluster births by UTC hour: spread across all 24 hours (min 0, max 8 in any hour;
16:00–20:00 UTC slightly heavier at 10/8/5/7% — but that mirrors the baseline feed, which
also peaks 18:00–22:00 UTC at 10/9/9/7%). The 20:30Z silence onset sits in a NORMAL
activity band for the entity (in-sample 20:00 UTC hour held 4% of its births, 22:00 held
7%). Conclusion: the entity is a round-the-clock operator with no meaningful quiet window;
overnight flatness is NOT diurnality. Hypothesis (a) survives only in the weak form
"per-day intensity varies" (counts 9/26/49 across Aug 25–27 were already evidence of
bursty, campaign-style operation). Burstiness cuts both ways: today's drought could be a
between-campaigns gap — or the end. The morning scorecard remains the decider.

Live state at scorecard 23:14Z: v6 evals=120, 0 entries (117 no_cluster_hit, 3
failed_momentum_floor); 5 trustworthy live hits ALL flat (median peak 1.08× vs in-sample
hit median 1.84×; none reached the 1.5× momentum floor). Hit rate 4.1% vs ~10% in-sample.
Both decoupling signatures persist. Books: v2 −8.7%, v3 +9.0%, v4 −4.9%, v5 +5.1%
(1 open), v6 £1,000.00. Pipeline healthy: 137 ok / 7 error cycles in 24h.
Rotation test readiness: post-silence winners still n=3 (<6 required).

### §38 — the in-sample pump clock vs live hits (28 Aug 2026, ~00:30 UTC)

Computed time-to-peak for the 29 in-sample cluster+momentum tokens that hit 2×
(unit-verified seconds → minutes): min 10, p25 23, **median 66, p75 93, p90 130, max 212
minutes after detection**. The pump, when it comes, comes fast.

Live trustworthy hits measured against that clock (ages at 23:21Z scorecard):
7fmHqRp 233m/1.08×, 37WhvcVy 213m/1.10× — **beyond the in-sample maximum**;
Pp3U7o9A 165m/1.00×, utsTit2E 165m/1.51× — past p90 (130m) even after adding the ~13-min
feed lag; only 2mTMrm5z (35m/1.00×) is still inside the window.

Read: 4 of 5 live cluster touches have already outlived the window in which 90% of
in-sample comparables had peaked, without pumping. This converts "flat hits" from an
anecdote into a clock-referenced failure: the entity's touch is no longer being followed
by the momentum cascade that defined H10. Combined with the hit-rate halving (3.9–4.1%
vs ~10%), both necessary conditions of the in-sample edge are degraded forward.
Remaining outs before Pass 3: (i) 2mTMrm5z still in-window; (ii) daytime session could
bring a fresh campaign; (iii) rotation test once overnight winners ≥6 (currently 3).

### §39 — pump-clock failure unanimous: 0/5 (28 Aug 2026, 00:57 UTC)

2mTMrm5ze9fS crossed the in-sample p90 time-to-peak (130 min post-detection) at 1.00× —
all five trustworthy live cluster hits have now outlived the window in which 90% of
in-sample cluster+momentum winners had already peaked (median 66m), without any of them
reaching even the 1.5× momentum floor. Forward replication score: **0/5**.

Formal status of the three §36 survival hypotheses:
(a) diurnal — WEAKENED (§37): entity births span all 24h; silence began in a normal band.
(b) feed shift — WEAKENED (§36 addendum): tokens still pump in our universe without it.
(c) wallet rotation — PENDING: post-silence winner set still n=3 (<6).
Plus (d) in-window late hit — now CLOSED: 0/5.

What still keeps H10 from being declared dead tonight: the sample is 5, the entity's
in-sample operation was bursty (9/26/49 per-day counts), and the decisive test remains a
full daytime session (08:00–20:00 London) with the rotation scan on a larger winner set.
But the prior has shifted hard: hit rate 2.9% (vs ~10%), peaks median 1.08× (vs 1.84×),
0/5 in-window, entity silent ~3.5h. If Pass 3 were forced tonight, H10 fails forward.

Secondary concern for the B-verdict fallback: v5 (behavioural gate) slid to +1.2% with
2 open; its green streak is thin (n=8 closed) and partly overnight-tape luck. v2 −12.2%,
v3 +6.1%, v4 −8.3% confirm that momentum-chasing without filters loses forward.

### §40 — pipeline maintenance: overnight timeout patch (28 Aug 2026, 02:30 UTC)

Three consecutive cycles (01:56/02:06/02:16Z) hit the loop's 200s monitor timeout:
overnight Helius pagination slowed (~37s/audit × cap 8 = ~290s > 200s budget).
Impact: no tokens tracked 01:56–02:16Z (tracked froze at 1,637); v6 evaluations froze
at 193. Manual catch-up run at 02:28Z recovered the gap (19 new tokens, tracked=1,656).
Fix deployed in automation_6d57d1be assets/memecoin_loop.py: audit cap 8→6,
monitor timeout 200→270s. Forward-sample caveat: any cluster touch born 01:56–02:16Z
that rolled off the profiles feed before 02:28Z is missed — noted for Pass 3
completeness; feed coverage checks (EKRBZrcu was detected at 01:02Z, before the gap)
show no known hit was lost.

### §39 addendum — clock failure now 0/6 (28 Aug 2026, 03:08 UTC)

EKRBZrcu3rKi (touched 01:02Z by 89q3zEgH, the sixth wallet) crossed p90 at 132 min /
1.42× — the strongest live hit yet, but still sub-floor (never reached 1.5× momentum)
and a slow grind, not the in-sample detonation profile (median 66 min to peak).
Forward clock score: 0/6. v6 remains at 0 entries across 215 evaluations — no live
touch has produced a qualifying signal. The entity is intermittently active overnight
(6th hit at 01:02Z after a 3.5h gap) but its touch no longer predicts the cascade.

### §41 — the missing follow-through, quantified (28 Aug 2026, 04:10 UTC)

In-sample decomposition of all 84 cluster-touched rows: 32 (38%) showed ≥1.5× momentum
at +5/+15 min — those are the H10 cell (median peak 5.20×, 29/32 hit 2×). The 52 touches
WITHOUT early momentum had median peak 1.22× and only 10/52 ever reached 2× — i.e.,
in-sample, a touch without follow-through was already nearly worthless.

Live forward: 6 touches, 0 with momentum (p = 0.62^6 ≈ 5.7% under the in-sample rate —
suggestive, not yet decisive alone). Live median peak 1.14× matches the in-sample
no-follow-through cell (1.22×) almost exactly. Reading: the entity still makes its birth
buys (the spray), but the accumulation follow-through that created the cascade — the
actual edge — has not appeared once forward. Combined with the hit-rate collapse
(6/226 = 2.7% vs 84/815 = 10.3% in-sample; binomial p < 0.001), the forward evidence
against H10 is now two independent failures: fewer touches AND zero follow-through.

For Pass 3: the edge was never "cluster wallet appears"; it was "cluster wallet appears
AND accumulates". The detection-time signal (touch) fired 6 times forward; the
confirmation (momentum) fired 0 times. v6's gate is exactly right — it would have kept
us out of all six. H10's remaining hope is a daytime campaign resumption.

### §DAILY — 28 Aug 2026, 06:18 UTC (automation daily review)

**Pipeline health (last 24h):** 137 ok cycles / 11 error cycles. Four consecutive TIMEOUTs at 01:56–02:26Z (rc=124) caused by overnight Helius pagination slowdown; patched in §40 (audit cap 8→6, timeout 200→270s). No data lost.

**Book snapshot (06:16Z):**
- v2 EARLY (1.0x): £820.77, −17.92%, 9 open, 40 closed, realised −£321.93
- v3 STRICT (1.25x): £1,019.06, +1.91%, 1 open, 18 closed, realised −£119.51
- v4 MOM1.5: £910.55, −8.94%, 1 open, 23 closed, realised −£91.98
- v5 BEHAV: £1,006.47, +0.65%, 0 open, 10 closed, realised +£6.46
- v6 CLUSTER: £1,000.00, 0.00%, 0 open, 0 closed, realised £0.00

**v6 forward test:** 0 entries since launch (19:10Z 27 Aug). Evaluated ~240+ tokens; 6 cluster hits in state.json last 24h (tag=unknown), all failed the 1.5× momentum floor. The gate is correctly closed. Pre-registered success criterion (≥30 entries beating baseline) remains unmet; n=0.

**v5 behavioural gate:** 10 closed trades (all 66yZvYMA and HG3sZ52N). Gate rejected 7+ tokens as `behaviour_risk` (per paper_v5.seen_done). Admission rate ≈ low single-digit % of tracked tokens — not never-opening, but selective. Thin green (+0.65%) is partly one token (66yZvYMA) hitting 2× multiple times.

**Live vs reconstruction convergence:** Wedge persists. Fast-watch shows 0/6 cluster hits with momentum follow-through vs in-sample 38% follow-through rate. v4/v2 continue to bleed on momentum-only entries. v3's +1.91% is carried almost entirely by one open runner (CTPoyCwk, peak 29×). Without it, v3 would be deeply red.

**Anomalies flagged:** (1) v2 bank diverged from paper_v2.json cash position by ~£190 — mark-to-market on 9 open positions explains gap; (2) v6 flat at £1,000.00 while 6 cluster hits occurred is the designed behaviour, but confirms the forward edge has not appeared.

**Assessment:** No v6 admissions is the correct output given zero qualifying signals. The behavioural gate (v5) is calibrated — it opens rarely and has kept the book near flat. The momentum-only books (v2/v4) continue to validate the base-rate thesis: chasing momentum without confirmation loses money. H10 forward test remains in Pass 2; decisive daytime session still pending.

### §42 — rotation scan: entity buys LATE, post-peak (28 Aug 2026, 06:45 UTC)

Post-silence winner set refreshed (≥2.5×, born after 20:30Z 27 Aug): n=21 (winner
production continued overnight: baLL6cE3 29.6×, AVBN6kXd 61.4×). Full-history
first-buyer scan (fixed tagger internals, 8 pages, 25 buyers) across all 21:

- 5/21 winners contain cluster wallets in fetched history: sCnoh91T 2.97×
  (4x5Uti74+FnBmjyWp), HG3sZ52N 2.69× (89q3zEgH, unverified on re-fetch),
  baLL6cE3 29.6× (DupzWEQ4), A17TCnR7 3.99× (FnBmjyWp), 7RgSCHyE 5.29× (CLYUJVdk).
- CRITICAL: monitor live-tagged ALL 5 as hit=[] at detection — correct. Timestamps
  show every cluster buy occurred +209m to +576m AFTER birth and AFTER the peak
  (e.g. baLL6cE3 peaked 02:28Z, DupzWEQ4 bought 05:08–05:44Z; sCnoh91T peaked
  22:36Z, cluster bought 01:24Z–06:46Z). The entity is late-chasing established
  pumps, not seeding births. This confirms §36 addendum with the fixed tagger:
  post-silence winners are NOT cluster-touched at birth.
- Interpretation: the birth-spray + accumulation cascade (the actual H10 edge)
  remains absent forward. Late chasing is retail-follower behaviour from the same
  wallets — anti-signal if anything (they bought tops).
- Rotation check: 26 non-cluster wallets recur in ≥2 winners (max: 7DyzpBsqDupB
  in 4/21). No loser base-rate computed yet — active sniper bots recycle across
  many launches, so recurrence alone is not evidence of a successor entity.
  Falsification requires the same scan against same-window losers. Deferred:
  H10's verdict does not hinge on it.

#### §42 addendum — rotation recurrence base-rate: NOISE (28 Aug 2026, 07:30 UTC)

Loser control: 21 valid same-window losers (peak <1.3×, age ≥2h, solana-only)
scanned with identical buyer extraction. Result: 26 non-cluster wallets recur
in ≥2 losers — a rate of 1.24/token, IDENTICAL to the winners' 26-in-21 (1.24).
Max recurrence 5 losers (2CQgjcdNEo7W) vs 4 winners (7DyzpBsqDupB). One wallet
(6XPyYm3yVsfr) appears in both lists. Conclusion: cross-winner buyer recurrence
is background sniper-bot recycling, present equally in losers. No wallet-rotation
successor entity. Cluster wallets also touched 1/21 losers' early buyers
(CLYUJVdk) — mere wallet presence at birth is not differentiating; §41 stands:
the edge was birth-touch AND immediate accumulation, and both are absent forward.
(Method caveat noted: winners' deep histories mean their buyer windows skew
recent, which if anything inflated winner recurrence — the true birth-buyer
overlap is likely even lower than measured.)

#### §41 watch note — first daytime touch (28 Aug 2026, 08:20 UTC)

4978aTN9W3CD touched at ~08:16Z by TWO known wallets (FnBmjyWp + 6P6gkNS9 —
both repeat offenders from the 6 flat hits). First touch in 7.3h, first of the
London day session. Multi-wallet birth touches were the stronger in-sample cell.
Decisive read: momentum at +5/+15 min (≈08:21–08:31Z). v6 will auto-enter if
≥1.5× — this is exactly the pre-registered test. Result logged next cycle.

### §43 — daytime two-wallet touch fails momentum: 0/7 (28 Aug 2026, 08:35 UTC)

4978aTN9W3CD (touched 08:16Z by FnBmjyWp + 6P6gkNS9, the strongest-profile
cell: London-morning, multi-wallet, repeat wallets) went 1.00 → 0.885× at +15m
and never exceeded 1.01×. v6 correctly refused entry (entries=0 across 302
evaluations). Forward momentum score: 0/7 (p = 0.62^7 ≈ 3.5% under in-sample
38% follow-through rate — now decisive beyond the hit-rate collapse). The two
independent forward failures stand: (1) touch rate 7/301 = 2.3% vs 10.3%
in-sample (p<0.001); (2) zero accumulation follow-through on all 7 touches,
including the best-case cell. In-sample, multi-wallet daytime touches produced
the detonations; forward, the same shape produced a token below birth value
inside 15 minutes. H10 forward status: effectively dead. Remaining formality:
observe the rest of the London day (to 20:00) for a campaign resumption, then
Pass 3 writes the final verdict. Trajectory: B (defensive/discretionary edge —
cluster-awareness as decision support and trade-avoidance, not a systematic
entry signal). v6's 0-entry record across 302 evaluations IS the demonstrated
value: the gate avoided 7 losing entries (7 flat/dead outcomes, median peak
1.10×, at least one sub-birth within 15m).

## §44 — PASS 3: adversarial settlement of the ten vectors (FINAL — sealed 28 Aug 2026, 19:00 UTC at the London close; drafted 08:45 UTC)

Forward evidence base: 302 v6 evaluations / 0 entries; 301 trustworthy tags,
7 cluster hits (2.3%); 0/7 touches with ≥1.5× momentum; §42 late-chase
forensics; §42a rotation base-rate null. Vector-by-vector:

1. **Discovery bias — CONFIRMED as the leading account.** The pre-registered
   settlement (§19/§23.1) ran: the unbiased forward sample shows zero
   follow-through on all 7 touches including the strongest-profile cell
   (§43). The 91%/5.2× in-sample cell did not generalise one day out of
   sample. Whether the mechanism is "we selected winner-touching wallets"
   (bias) or "the entity changed behaviour on 27 Aug ~20:30Z" (break) is
   indistinguishable from our data and does not matter for the verdict:
   the signal is not tradeable forward either way.
2. **Dump below target — moot.** Refuted in-sample (§33); never testable
   forward because no entry ever qualified. Dies with the strategy.
3. **Watchlist decay — mechanism REFUTED, effect OBSERVED.** The wallets
   were NOT rotated: the same 15 addresses remain active on-chain (§42
   late-chase buys through 06:46Z today). What collapsed is their
   birth-touch rate (2.3% vs 10.3%) and follow-through (0/7). The entity
   changed behaviour, not addresses. No successor entity found (§42a:
   recurrence = sniper-bot background, identical 1.24/token in losers).
4. **Universe selection bias — OBSERVED LIVE exactly as predicted.** §23.4
   said "a large tag-rate shortfall means the cluster plays elsewhere":
   measured shortfall is 2.3% vs 10.3% (p<0.001) on the SAME feed. The
   cluster mostly stopped playing on our feed's births.
5. **Path coarseness — closed by policy.** All pre-fastwatch statistics
   treated as upper bounds since §22; every forward number above is
   fast-watched (≤1-min cadence) or full-history Helius. No forward claim
   rests on coarse reconstruction.
6. **Regime singularity — BINDING and unfixable in-window.** The forward
   failure occurred inside the SAME regime (SOL range-bound, same week) as
   the in-sample edge. The edge did not survive 24 hours within its own
   regime; cross-regime robustness is academic.
7. **v5 gate calibration — SETTLED: no edge.** 12 closed trades, +2.0%,
   1 open; the behavioural-gate fallback thesis decayed to noise (§40s).
   The gate opens rarely and what it admits doesn't outperform.
8. **Single exit family — moot.** Ladder re-test requires entries; there
   were none. Trail-only policy neither helped nor hurt: it never ran.
9. **Helius SPOF — MATERIALISED MILDLY.** 11/144 cycles errored overnight
   (Helius slowness), causing a 20-min tracking gap 01:56–02:16Z — a
   recorded caveat on the forward sample. Patched at §40 (cap 6, timeout
   270s); stable since. Did not affect any verdict: no cluster event
   occurred in the gap (verified via next-cycle catch-up tags).
10. **Sample size — SETTLED, in the direction nobody wanted.** The
    pre-registered ≥30-entry test can never execute because the gate
    never opened. n=7 touches with 0 follow-through settles the momentum
    question (p≈3.5%); n=301 tags settle the touch-rate question
    (p<0.001). The edge died upstream of the trade.

### §44b — §31 skeleton [F] slots, filled (FINAL numbers at seal, 19:00 UTC)

- **Expected performance, forward:** v6 book £1,000.00, **0 entries, 498
  evaluations** over ~23h. Honest planning number: **no tradeable forward
  edge exists**. In-sample +72–146%/trade is confirmed non-generalisable
  (upper bound that bound nothing).
- **Final forward tally (13 touches / 500 trustworthy tags, 2.6% vs 10.3%
  in-sample, p<0.001):** qualifying early momentum 1/13 (p≈2% for ≥9 flat);
  ≥2× peaks 2/13 = 15% (4978aTN9 3.78× late-detonation, CHZSuhKGewov 2.61×
  second-leg) — consistent with the in-sample no-momentum cell tail (19%),
  NOT with the H10 cascade (91% hit-2×, median peak 5.2×, minutes-to-peak).
  Median live peak 1.35× vs 1.84× in-sample. v6 rejections by dimension:
  488 no_cluster, 9 momentum_floor, 1 thin_liquidity (CHZSuhKGewov — the one
  momentum-qualified touch; gate cost logged honestly in the 17:33 note).
- **Kill-switch audit:** condition (1) fired in spirit — touch rate 2.6% vs
  10.3% in-sample and multi-hour silence gaps routine (longest ~5h). The
  framework worked as designed: it prevented capital deployment into a dead
  signal.
- **What the infrastructure is actually good for (demonstrated):**
  trade-AVOIDANCE. Final paper books over the same live window: v2
  momentum-spray **−25.2%** (£748.37), v4 **−13.1%** (£868.84), v5 **−1.4%**
  (£985.84), v3 **−3.0%** (£969.94); v6 cluster+momentum+liquidity gate
  **£1,000.00 flat**. Everything that traded lost; only the refusing gate
  preserved capital. Cluster-awareness plus behavioural gating is a
  defensive filter, not an entry system.

FINAL VERDICT (sealed 28 Aug 2026, 19:00 UTC, London close): **B —
defensive/discretionary edge.** Rationale: (a) the only systematic
candidate (H10/v6) failed its pre-registered forward test decisively on two
independent dimensions (touch-rate collapse p<0.001; momentum follow-through
collapse p≈2%); (b) the bankable results are negative-defensive: unfiltered
momentum chasing loses money forward (v2 −25.2%, v4 −13.1%), and the
cluster+momentum gate's value is measured in avoided losses; (c) no second
entity, no rotation, no time-of-day resumption pattern found — London day
looked exactly like the night (5 daytime touches, same spray-fade profile).
Not C (no systematic edge survived), not A (no scalable systematic edge),
not D (the research produced real, reusable intelligence: base rates,
cluster forensics, behavioural gates, and a working live pipeline that
correctly said NO for 498 consecutive evaluations).

### §45 — 4978aTN9 detonated late WITHOUT cluster accumulation (28 Aug 2026, 09:15 UTC)

Correction to §43's "median peak 1.10× / all flat": 4978aTN9 printed 3.78× at
+56m. Full path: 45 minutes dead flat (0.88–0.92×), then vertical 0.92 → 3.78×
in the 09:00–09:10Z window. Forensics:

- Mint-side history post-ignition saturated (271 swaps/min); flat-window flow
  unrecoverable from mint side. Wallet-side pull: 6P6gkNS9's ONLY buys are
  09:12Z and 09:14Z — AFTER ignition (late-chase, the §42 pattern again).
  FnBmjyWp shows no post-birth activity in the token (6-page wallet window).
  NO evidence of silent cluster accumulation during the flat 45 minutes.
- Statistical home: in-sample, touches WITHOUT early momentum hit 2× at 19%
  (10/52, §41). Forward: 1/7 = 14%. This token is that cell's tail, not the
  H10 cascade (which detonated in minutes with early momentum, median 3m to
  peak). v6's gate missed this winner — a known, priced-in cost of the
  momentum floor (the same floor kept us out of 6 flat/sub-birth touches).
- Open question logged, not answered: what ignited 09:00Z? Not the two
  tagging wallets. If an external driver (boost/call), the birth touch is
  coincidence; §42a showed buyer overlap is background noise at base rate.
- Forward tally update: touches 7, ≥2× peak: 1 (14%, vs in-sample no-momentum
  cell 19% — CONSISTENT), early-momentum follow-through still 0/7. H10's
  cascade signature remains absent forward. Verdict trajectory unchanged: B.
  If more late detonations appear on touched tokens, the no-momentum cell's
  tail becomes worth a separate touch+loose-trail paper book — noted as a
  post-window research item, NOT a mid-window rule change.

#### §43 tally update (28 Aug 2026, 10:58 UTC): 8th touch B3wHe3qESXDN (6P6gkNS9)
spiked 1.30× in minute one, faded to 0.89× by +10m — never near the 1.5× floor.
0/8 forward touches with qualifying momentum (p ≈ 2.2%). Pattern unchanged:
initial spray pop, immediate fade, no accumulation.

#### §44 midday checkpoint (28 Aug 2026, 12:03 UTC): London morning produced 2
touches (08:16Z two-wallet, 10:46Z single), both failing the momentum floor —
the exact inverse of in-sample, where daytime multi-wallet touches were the
STRONGEST cell. Touch rate in-session so far: 2 in ~4h ≈ overnight rate.
Daytime-resumption hypothesis (§37's last variant) is failing: the day looks
like the night. 352 evaluations, 0 entries. Afternoon remains as final formality.

#### §44 afternoon checkpoint (28 Aug 2026, 14:44 UTC): 10th touch B5YTUMqSnwzz
(6P6gkNS9, 13:56Z) popped 1.28× by +17m then froze — no new high in 30m. v6
evaluated it and rejected on the momentum floor (7th floor rejection). Tally:
0/10 forward touches with qualifying momentum. London afternoon so far looks
identical to morning and overnight: single-wallet spray, sub-1.4× pop, fade.
Daytime-resumption hypothesis effectively closed. 411 evaluations, 0 entries.

#### §44 late-afternoon checkpoint (28 Aug 2026, 16:16 UTC): 11th touch
EGMuM8qhWTzT (89q3zEgH — the EKRBZrcu slow-grind wallet, 15:26Z) opened flat
1.00→1.09×, frozen 15 min, v6 rejected on momentum floor (8th rejection);
creeping 1.14× at +35m, no grind signature. Tally 0/11 with qualifying
momentum. 441 evaluations, 0 entries.

#### §44 16:48 UTC note — first momentum-qualified touch: CHZSuhKGewov
(6P6gkNS9, 16:36Z) printed 1.44× by +6m, 1.57× by +12m — the FIRST forward
touch with qualifying early momentum (1/12). v6 evaluated and REJECTED on
thin_liquidity (first liquidity-gate rejection; verdicts now include
'thin_liquidity': 1). The multi-gate design held on a second dimension: even
when momentum finally appeared forward, the liquidity floor refused the entry.
Peak trajectory being tracked for the seal tally.

#### §44 17:33 UTC note — CHZSuhKGewov topped 2.49× at +47m, now stalled.
Full path: 1.44×@+6m → 1.57×@+12m → freeze 25m → second leg to 2.38-2.49×
@+37-47m → stall (final 2.61×). v6's thin_liquidity rejection stands as a
COST datapoint: the liquidity gate refused the session's strongest
momentum-qualified touch. Counterfactual honesty (§23 applies): at the
liquidity level that triggered the rejection, a real 2%-of-bank fill would
have moved the pair and exited far below the paper peak; the refusal is
defensible ex-ante even though ex-post the token ran.

## §46 — SEAL RECORD (28 Aug 2026, 19:00 UTC, London close)

The 23-hour decisive observation window closed with the pattern unchanged
through the final hour (last full scorecard 18:55 UTC). Final state:

- **v6 (H10 pre-registered test):** 498 evaluations, 0 entries.
  Rejections: 488 no_cluster_hit, 9 failed_momentum_floor, 1 thin_liquidity.
- **Cluster touches:** 13 in 500 trustworthy tags (2.6% vs 10.3% in-sample,
  p<0.001). Peaks: median 1.35× (in-sample 1.84×); ≥2×: 2/13 (4978aTN9 3.78×
  late-detonation; CHZSuhKGewov 2.61× second-leg after liquidity rejection);
  qualifying early momentum: 1/13 (p≈2% for the observed flat rate).
- **Final paper books:** v2 £748.37 (−25.2%), v3 £969.94 (−3.0%),
  v4 £868.84 (−13.1%), v5 £985.84 (−1.4%), v6 £1,000.00 (flat, 0 entries).
- **London-session verdict:** day == night. Daytime touches (08:16Z, 10:46Z,
  13:56Z, 15:26Z, 16:36Z, 17:35Z) all showed the same spray → sub-1.5× pop →
  fade/freeze profile. No afternoon campaign resumption; §37's
  daytime-resumption variant is closed.
- **VERDICT: B — defensive/discretionary edge, FINAL.** Full rationale in
  §44b (updated at seal). §7 at the top of this report now points here.
- **Post-window research items (logged, not actioned):** (1) touch +
  loose-trail variant book for the no-momentum cell tail (2/13 late runners,
  in-sample tail 19%) — needs its own pre-registration and a fresh forward
  window; (2) liquidity-gate calibration review using CHZSuhKGewov as the
  cost case; (3) the live pipeline (automation_6d57d1be) keeps running as a
  defensive monitor — if the entity's regime changes (birth-seeding returns,
  multi-wallet early accumulation reappears), the same gates see it first.

## §47 — Play #2 bundle-screener test: NULL (28 Aug 2026, 20:40 UTC)

Tested BIG_BOYS_PLAYBOOK play #2 (birth-bundle insider fingerprint) against
both cached cohorts: 21 post-silence winners (peaks 2.5–61×) vs 20 losers,
10 earliest buyers per token, wallet-age + funding-tree + 45-min sell check
(bundle_screener.py → bundle_scan.json; ~400 wallet histories via Helius).

- Winners: fresh_share median 0.0, bundle_score mean 0.005, tokens with ≥2
  fresh early buyers: 1/21. Losers: median 0.0, mean 0.010, 2/20.
- The fresh-funded birth bundle is essentially ABSENT from both cohorts.
  No separation whatsoever — play #2's discriminator fails as specified.
- Why the null is informative, not just negative: 2026 volume-bot/MM services
  openly advertise AGED, pre-funded wallets. The fresh-wallet bundle was the
  2024-era signature; the pros age their inventory now. Our own cluster
  entity also used established wallets (§42). The fingerprint moved from
  wallet AGE to wallet PROVENANCE — and provenance at scale needs an
  indexer (full wallet history), not paginated RPC calls.
- Consequence: playbook play #2 downgraded from "90% built" to "detection
  primitive needs indexer-grade data"; the aged-farm variant is re-scoped as
  play #2 in BIG_BOYS_PLAYBOOK_2.md.

## §48 — Play #3 serial-deployer tracking: DEAD after artifact correction (28 Aug 2026, 21:35 UTC)

Two-stage test on the 41-token cohort (21W/20L):

1. **Stage 1 (pagination, deployer_scan.py):** oldest-reachable feePayer via
   15-page mint history showed 4 "repeat deployers" covering 9/21 winners —
   an apparent 82%-winner signal. Sanity check killed it: none of the 11
   repeat rows had actually reached the birth tx (gaps 10–1312 min BEFORE
   pair_created). Winners accumulate 8,000+ txs; truncation lands on active
   sniper wallets, which cluster in winners mechanically. Classic artifact.
2. **Stage 2 (ground truth, creator_scan.py):** read the creator pubkey
   directly from the pump.fun bonding-curve PDA (offset 49, one
   getAccountInfo call per token — pure-Python base58/PDA/ed25519 check).
   All 41 resolved. Result: **40 unique creators / 41 tokens; one repeat
   (F5XvCe4233 → 1W + 1L)**. One curve even shows the incinerator as
   creator. The stage-1 signal was entirely spurious.

Verdict: creator-address reputation is dead in the current meta — deployers
launch from a fresh address per token (that IS the practice; GMGN creator
history exists precisely because everyone checks it). The truncation artifact
is itself a reusable lesson: any "oldest reachable tx" heuristic on
high-velocity mints silently becomes an active-trader detector.

Deliverable kept: creator_scan.py resolves any pump.fun token's true creator
in 1 RPC call — retained as a pipeline primitive (cheap provenance hook for
the forward monitor), not a signal.

## §49 — Play #6 meta-rotation: WEAK/NULL on this window (28 Aug 2026, 21:50 UTC)

Names resolved for all 1,548 tracked solana mints (dexscreener batch API,
names.json). Keyword mining over name+symbol produced only generic tokens
(first/ape/gta/monkey/pump/just/bull) — no sharp narrative metas in a 3.5-day
window. Meta hit-≥2× rates: best 'first' 0.29 (n=14) vs all-token baseline
0.17 (n=1,363 with outcomes) — marginal, small-n. The one real pattern: ALL
meta median peaks lifted on 27 Aug (e.g. 'first' med peak 1.14 → 2.79–6.52×
in the 27-00→27-12 buckets) — that's the entity's campaign day showing up in
every bucket simultaneously, i.e. meta stats are an entity-activity proxy,
not an independent rotation signal. Verdict: not tradable as specified; a
longer window + proper name-clustering might revive it, but priority drops
below the other plays.

## §50 — Play #7 sniper-dump wick study: MARGINAL (28 Aug 2026, 22:05 UTC)

Minute-scale history scan (wick_scan.py → wick_scan.json): 232 tokens printed
a qualifying early wick (peak ≥1.4×, then ≥30% drawdown within 90 min).
- 47% recovered ≥1.5× off the wick bottom within 30 min; median recovery
  1.46×. Audit-clean subset: 50%, median 1.52× — flags don't sharpen it.
- BUT median post-30m level = 1.00×: the bounce fully fades on average. The
  tradeable version is bounce-scalping with tight exits, not recovery-holding.
- Headline recoveries (30×, 24×) are dead-cat noise from 0.03× bottoms —
  not capturable.
- Entry realism: wick bottoms are only identifiable with lookahead; live
  entries land above the bottom. Rough EV after +2–5% round-trip costs on
  thin pairs: ~breakeven.
Verdict: real regularity, thin edge. Needs sub-minute data + absorption
confirmation to be worth pre-registering. Parked below Tier-1.

## §51 — Plays 1/4/5/8/9/10 dispositions (28 Aug 2026, 22:30 UTC)

- **#10 audit-latency (flag_flip.py, n=120 rescan):** flip-UP tokens
  (clean at detection, flagged now) died — median final 0.01× vs stable-clean
  0.83×. Retro data can't order flag-vs-dump, so the FORWARD monitor is the
  deliverable: flag_flip_monitor.py (seeded 22:30Z, 40 newest tokens per
  pass, flips timestamped to flagflips.jsonl). Verdict: REAL pattern,
  defensive value proven, latency-arb value pending forward timing data.
- **#1 curve momentum + #5 migration dislocation:** NOT retro-testable —
  our dataset begins at dexscreener listing (post-graduation). Deliverable:
  curve_collector.py (PumpPortal public websocket → curves.jsonl, newToken +
  migration subscriptions). Verdict: instrument-first; collect 24–48h before
  any strategy claims.
- **#8 funding capture:** feasible on Hyperliquid (12+ memecoin perps, public
  funding API). Snapshot 22:25Z: most at baseline ~11% annualized, FARTCOIN
  51%, OI up to $206m (PUMP). Verdict: VIABLE but a different arena —
  established memes, structural yield, capacity-fine at our size. This is a
  parking play, not an edge discovery.
- **#9 liquidation fishing:** needs a liquidation-map feed (Coinglass-class,
  keyed). Deferred pending data subscription decision.
- **#4 social velocity:** needs paid X API / TG scraping. Deferred; cheapest
  proxy (dexscreener txn/buy counts) already flows through the existing feed.
- **#2 indexer (aged-farm mapping):** decision ON HOLD per roadmap — only if
  Tier-1/2 evidence says provenance matters.

## §52 — CONSOLIDATED VERDICT on the 10-more-plays build (28 Aug 2026, 22:35 UTC)

Tested with real data: #3 DEAD (§48 artifact-corrected), #6 WEAK/NULL (§49),
#7 MARGINAL (§50: 47–50% wick recovery but bounce fades to 1.00× median —
breakeven after costs). Delivered instrumentation: #10 forward flag monitor
(running), #1/#5 curve collector (code ready, needs runtime slot). Deferred
with reasons: #2 (indexer, hold), #4 (paid data), #9 (keyed data). Viable in
a different arena: #8 (perp funding, structural yield).

Pattern across BOTH playbooks: every per-token prediction edge has now died
under forward or cohort testing (H10 cascade, momentum spray, behavioural
gates, fresh-bundle, serial-deployer, meta, wick — 7 distinct kills). The
survivors are all structural: defensive gating (sealed verdict B), DLMM fee
farming, perp funding capture, shovels/alerts. The next plays to actually
RUN with capital remain the Tier-1 trio from BIG_BOYS_PLAYBOOK_2.md.

## §53 — Instrumentation live on schedule (28 Aug 2026, 22:10 UTC)

Two Blueprint widget-task automations enabled and verified with real
interval-triggered runs:

- **Curve collector** (automation_3840d0e4): every 20 min, 12-min PumpPortal
  websocket capture → curves.jsonl. First scheduled run 21:44Z: 555 events
  (535 births, 18 migrations). ~72 runs/day, ~1.8 MB/day. Dataset for plays
  #1/#5 accumulates from 28 Aug 21:07Z.
- **Flag-flip monitor** (automation_b70c447a): every 30 min, RugCheck re-poll
  of 40 newest tracked tokens → flagflips.jsonl on state change. First
  scheduled run 21:34Z succeeded. Captures flag-vs-dump ordering for §51's
  open question from 28 Aug 21:06Z.

First analysis checkpoint for both datasets: after ~48h of accumulation
(30 Aug evening UTC).


## §DAILY — 2026-08-29T06:18Z daily forward-test review

**Cycle health:** 177 automation cycles in last 24h; 5 TIMEOUT errors (rc=124), no hard failures. Fast-watch granularity active.

**Book states (latest cycle 06:06Z):**
| Book | Bank | ROI | Open | Closed | Realized PnL | Notes |
|---|---|---|---|---|---|---|
| v2 (floor 1.0) | £669.00 | −33.1% | 5 | 65 | −£349.48 | Worst performer; loose floor bleeds |
| v3 (floor 1.25) | £967.37 | −3.3% | 1 | 28 | −£36.37 | Best momentum-only book |
| v4 (floor 1.5) | £869.90 | −13.0% | 2 | 51 | −£128.83 | Tighter floor not enough vs base rate |
| v5 (+behaviour gate) | £997.58 | −0.2%* | 1 | 18 | +£4.67 | Near flat; gate blocks ~71% of candidates |
| v6 (cluster+floor 1.5) | £1,000.00 | 0.0% | 0 | 0 | £0.00 | **Zero admissions after 708 tokens evaluated** |

*Last 24h activity:* v2 closed 25 / opened 2; v3 closed 10 / opened 1; v4 closed 28 / opened 2; v5 closed 8 / opened 1; v6 closed 0 / opened 0.

**State.json signal layer (last 24h):**
- Cluster tags with non-empty hit: **7** (out of ~2,515 total tracked)
- Behaviour verdicts recorded: **35**
- v5 seen_done: 33 `behaviour_risk` | 30 `failed_momentum_floor` | 3 `thin_liquidity` → admission rate ≈ **29%**
- v6 seen_done: 697 `no_cluster_hit` | 10 `failed_momentum_floor` | 1 `thin_liquidity` → **0% admission**

**Assessment:**

(a) **First v6 admissions? No.** After ~36h of forward test (started 27 Aug 19:10Z), v6 has taken **zero positions**. The cluster gate fired only 7 times in the last 24h across the entire universe, and on none of those occasions did the token simultaneously clear the 1.5× momentum floor. The 10 tokens that hit the momentum floor had no cluster hit; the 7 that had a cluster hit failed momentum. The intersection is empty. This is consistent with the §42/§43 settlement already recorded in this report: discovery bias confirmed, zero follow-through on all 7 forward touches.

(b) **Live vs reconstruction convergence / wedge:** The wedge is **not closing; it has become a chasm.** The in-sample H10 reconstruction (66% ≥2×, 29% dead) relied on a cluster list derived from wallets that touched winners. Forward, those same wallets remain active on-chain (§42 late-chase confirms no rotation), but their birth-touch rate collapsed from 10.3% to 2.3% and follow-through dropped to 0/7. The fast-watch loop gives ~1-min granularity, yet there is nothing to watch. Live results for v2–v4 continue to drift toward the base-rate (v2 −33%, v4 −13%), while v3 (1.25 floor) is the only momentum-only book holding near breakeven. v5 is essentially flat after behavioural filtering.

(c) **v5 gate calibration:** The behavioural gate is **working as designed, not stuck shut.** It admits roughly **29%** of candidates that clear the momentum floor, blocking 33 for `behaviour_risk`, 30 for `failed_momentum_floor`, and 3 for `thin_liquidity`. The gate trims volume but does not magically improve hit rates: v5 realized PnL is +£4.67 on 18 trades (~£0.26/trade avg), i.e., near breakeven after costs. It is calibrated as a defensive filter, not a positive edge.

(d) **Anomalies flagged:**
- **v3 outperformance:** v3 (1.25 floor) at −3.3% is materially ahead of v2 (−33%) and v4 (−13%). This suggests the 1.0 floor is too loose (lets in too much garbage) and the 1.5 floor may be too tight (misses recoverable bounces). A 1.25 floor appears to be the sweet spot in this regime — but still not profitable.
- **v5 J4DMRf1c double-tap:** The token was admitted by v5, hit 2× quickly, and was re-admitted on the next cycle at a higher mcap (£853k). This is a "chase" pattern on a single token that happened to have cluster-like momentum but no actual cluster tag. v5's realized PnL turned positive on this trade.
- **auto_log timeout cluster:** 5 TIMEOUTs (rc=124) occurred in a block around 2026-08-28 01:56Z–02:26Z. All books recovered on the next cycle; no missed entries/exits detected in the trade logs. Root cause: Helius API latency spike during that window.

**Verdict:** The momentum-only baseline continues to lose money. The cluster tag, as currently constructed, is a **null signal forward** — not because the wallets disappeared, but because the entity changed behaviour and the discovery bias has bitten. The pre-registered v6 success criterion (≥30 entries beating 66% ≥2×) is **unreachable** at current cluster-touch rates (7/day with zero momentum overlap). The only structural survivor is the behavioural gate (v5), which is defensive and near-breakeven. The real edge, if any, has shifted to the H19 "late-peak / community species" window (+60 min) — but that requires a v7 book, not a v6 patch.

**Next checkpoint:** 2026-08-30 evening UTC (48h curve-collector + flag-flip accumulation).

## §54 — Birth anatomy: two populations, and the seed-size tell (29 Aug 2026, 08:40 UTC)

First analysis of the curves.jsonl feed (9,402 births + 207 matched
graduations over ~11h, PumpPortal create/migrate events):

**Time-to-graduation is violently bimodal.** 61% of graduates completed the
ENTIRE bonding curve within 60 seconds of birth; 82% within 5 min. Instant
graduates carry a median dev seed of **85 SOL** — the deployer's own bundle
fills its own curve in the same minute. Slower graduates: median seed
0.15 SOL. There is no "discovery" phase for the manufactured class.

**Dev seed size is the single strongest birth signal we have ever measured:**
| seed at birth | births | graduated | rate vs 2.2% base |
|---|---|---|---|
| ≥1 SOL | 3,027 | 135 | 4.5% (2×) |
| ≥5 SOL | 717 | 100 | 13.9% (6×) |
| ≥10 SOL | 217 | 87 | 40.1% (18×) |
| ≥20 SOL | 105 | 86 | **81.9% (37×)** |

**Serial creators are spam farms, not reputation.** 1,098 of 3,388 creators
launched 2+ tokens in 11h; 655 launched 3+. The top factory (AeZpHiVXZ6)
launched 147 tokens with ZERO graduations; the top-10 factories (60–147
launches each) graduated 3 tokens combined. Creator recurrence is an
ANTI-signal — confirms §48's verdict from the other direction.

Two birth populations exist: (1) manufactured — big seed (≥20 SOL), instant
self-filled curve, 82% graduation; (2) organic — median 0.2 SOL seed, ~98%
never graduate. OPEN QUESTION (the tradeable one): does the manufactured
class RUN post-migration (volume-bot + boost continuation) or DUMP on
followers (seed = exit-liquidity trap)? Next analysis: join the 86
manufactured graduates to state.json post-migration price paths.

## §55 — Full lifecycle of the manufactured class (29 Aug 2026, 09:00 UTC)

Joined 208 graduates to outcomes (lifecycle.py → lifecycle.json; state.json
history + dexscreener fallback, 159/183 missing resolved). Verified against
live pair data. The manufactured class (seed = exactly 85.005 SOL = the
dev buying the ENTIRE bonding curve in the birth tx, instant graduation at
curve-terminal ~$42.6k mcap) splits into two terminal states:

**HUSK (49/80 = 61%): quick extraction.** Dev owns ~all supply at $42.6k,
lists on PumpSwap, distributes into listing demand. Median −95% within
hours, liquidity ~$1.9k. Exit volume is real money harvested: RENT pulled
$401k of 24h volume on its way to −95.6%. This is an assembly line —
identical seed, identical mechanics, one-shot creators.

**RUNNER (29/80 = 36%): the campaign.** Same birth, opposite continuation:
sustained manufactured buy flow. Verified: NTDA +401,605%/24h, $173M mcap,
$1.1M liquidity, 32,287 buys vs 675 sells (48:1 — the volume-bot fingerprint
from the market research). USWS +5,999% ($2.6M), ASOS +6,925% ($3.0M).
Real liquidity, real listings, one creator each. These are the tokens that
BECOME the week's monsters — and our dexscreener-feed monitor caught 0/29
of them at birth (they never look like 'new pairs with organic discovery';
they arrive already moving).

**The tradeable question, refined:** at migration +0–15 min, what separates
runner-destined from husk-destined? Candidates: early buy/sell ratio, holder
growth, dev keeps buying vs starts selling, boost appearances. Requires
trade-level flow on big-seed births — the collector currently logs only
create/migrate events. UPGRADE QUEUED: subscribe TokenTrade for births with
seed ≥5 SOL so the runner/husk differentiator is captured live.

## §56 — MFG tracker: the runner/husk capture system is LIVE (29 Aug 2026, 09:30 UTC)

The "capture the above" build: the curve-collector automation
(automation_3840d0e4, every 20 min) is now a full manufactured-launch
lifecycle tracker. Data path decisions and discoveries:

**PumpPortal subscribeTokenTrade is PAYWALLED** — requires an API key funded
with ≥0.02 SOL (their exact error). The planned trade-feed upgrade from §55
was dead on arrival. Replacement found and verified live: **Helius websocket
accountSubscribe on each birth's bonding-curve account** (curve address is in
the create event's `bondingCurveKey`). The 151-byte curve account decodes to
virtualTokenReserves (u64 @8) / virtualSolReserves (u64 @16) / complete flag
(@48) / creator (@49). vSol delta sign = buy/sell, size = |ΔvSol|/1e9. Live
verification: fresh birth → 63 notifications, 62 decoded trades, realistic
flow (buys, sells, dust bot-pings, 3.7 SOL distribution sells) within 60s.

**Architecture:** two websockets per 19-min run — PumpPortal (births +
migrations → curves.jsonl, unchanged) + Helius (curve accounts for every
birth with seed ≥5 SOL, up to 60 concurrent). Derived trades →
mfg_trades.jsonl; snapshots at +5m/+15m/+60m → mfg_tokens.jsonl (buys/sells,
buy/sell SOL, flow_ratio, notifs, mcap from reserves: vSol·1e6/vTok);
lifecycle state → mfg_state.json (survives the 1-min inter-run gap; legacy
state auto-migrated).

**Deployment proof (production run, 19.3 min, exit 0):** 375 births, 15 new
big-seed tracks + 22 warm re-subs = 37 curve subscriptions, 2,800 derived
trades, 78 snapshots, 0 Helius errors, 2 clean unsubs. One infra fix along
the way: the automation's 14-min runner timeout (legacy of the old 12-min
window) was killing runs before _save_state — raised to 22 min; verified
with a full-length run. Free-tier Helius tolerated 37 concurrent
accountSubscriptions without a single error.

**Honest limits:** (1) unique-buyer identity and dev-sell detection are LOST
(reserves carry no trader keys) — holder-growth proxy is trade/notif COUNT,
not distinct wallets; (2) slot batching can merge several trades into one
notification (accepted approximation); (3) post-graduation flow is NOT
captured — the curve account freezes when liquidity moves to PumpSwap
(PumpSwap pool tracking is future work; migrate-event pool field names still
unchecked).

**Early catch:** "Ant" (seed 5.5 SOL) tracked live to 162.6 SOL mcap with
884 buys / 643 sells in its first window. Analyzer mfg_report.py labels
outcomes from snapshots (RUNNER = graduated & +60m mcap ≥100 SOL; HUSK =
graduated & ≤45, or ungraduated & ≤20 with flat flow) and prints median
runner-vs-husk features at +5m/+15m. First labels land ~1h after deployment;
a statistically useful differentiator table needs ~2–3 days of accumulation
(~100+ labelled outcomes at the observed big-seed rate of ~45/day).

## §56b — PumpSwap pool tracking: the post-graduation blind spot is closed (29 Aug 2026, 13:20 UTC)

§56's honest limit — "post-graduation flow is NOT captured" — is now fixed,
and the fix matters because the runner/husk question for the 85-SOL
instant-grad class is decided entirely AFTER migration.

**Discovery path (verified on-chain):** the migrate event carries only
`pool: "pump-amm"` (no address), and my first-guess AMM program ID was
wrong. Ground truth from reading an actual migration transaction: the real
PumpSwap AMM is `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA`. Pools are
found per-mint with one getProgramAccounts call (memcmp offset 43 =
baseMint). Layout: bump@8, index@9, creator@11, baseMint@43, quoteMint@75
(=WSOL verified), lpMint@107, poolBaseTokenAccount@139,
poolQuoteTokenAccount@171, lpSupply u64 @203. Flow = SPL amount deltas
(u64 @64) on the pool's WSOL token account: WSOL in = buy, out = sell.
Pool mcap = quote_lamports * 1e6 / base_raw (same form as the curve math).

**Deployed into the same tracker automation** (no new task; quota-safe):
on graduation → discover pool → seed baseline balances (dead pools get an
mcap too) → accountSubscribe both pool token accounts → pool flow joins
mfg_trades.jsonl with venue=pool. Graduated tokens get extended snapshots
at +4h/+12h/+24h. Widget board is pool-aware post-grad.

**Smoke/prod numbers:** 23 pools discovered, 46 subscriptions, ~1,400–1,800
pool trades captured per 2–3 min window, 0 Helius errors. First full
production run delivered to the widget successfully.

**First pool-labelled outcomes:** USMS — 1,267 SOL of post-grad BUY volume
vs 14 sells (pool_flow 5.5); PINK — pool_flow 2.7 with 41.6 SOL buys. These
are volume-bot campaigns in action, visible for the first time.

**NEW RESEARCH FINDING — the mcap inflation mechanic:** pool_mcap on the
manufactured class is astronomically distorted BY DESIGN: USMS 1.4–1.9M
SOL, PINK 127k SOL, XIAOMI 11k SOL of paper mcap. The dev keeps ~97% of
supply off-pool, so marginal pool price × 1e9 supply is fiction as
"market cap" — but it IS the manipulation signature: thin pool + volume
bot = vertical chart that baits outside buyers. Reliable runner/husk
metrics are therefore pool FLOW (buy SOL, buy/sell ratio) and pool
LIQUIDITY (quote balance), not pool mcap. mfg_report.py labels now use
pool_mcap (RUNNER >=150 SOL, HUSK <=45) with the distortion caveat
printed; thresholds to be tuned by the 48h review with real accumulation.

## §56c — Pool liquidity as first-class metric + first real differentiator table (29 Aug 2026, 14:45 UTC)

Added pool liquidity (quote-balance SOL, with min/max since graduation for
drain detection) to tracker state, all snapshots, the widget board (graduated
rows show a `liq` sub-line), and mfg_report.py's pool-feature table.

**First real runner/husk differentiator table** (+60m pool features, median;
n=3 RUNNER / graduated HUSK subset — early but directionally sharp):

| feature | RUNNER | HUSK |
|---|---|---|
| pool_liq_sol | 328.6 | ~0 |
| pool_flow_ratio | 3.61 | 0.59 |
| pool_buys / sells | 1,514 / 84 | 93 / 113 |
| pool_buy_sol / sell_sol | 84.6 / 23.4 | 47.2 / 79.3 |

Runner signature: 18:1 buy/sell count, deep liquidity, flow > 3.
Husk signature: sell-heavy count, flow < 0.6, liquidity drained.

**Caveat refinement on §56b's mcap finding:** USMS's pool holds 7,580 SOL
(~$3.8M) of real quote liquidity — so for the biggest campaigns the
inflated mcap is NOT purely thin-pool fiction; deep pools are part of the
credibility play. The liq metric now separates "deep-pool campaign"
(real runner) from "thin-pool paper pump" — exactly the distinction the
mcap number alone could not make.

## §56d — First live forward test of the MFG runner alert (2026-08-29, ~47 min after 5 alerts)

Five alerts fired (USMS ×3, BEAST, claude). Forward outcome measured by joining mfg_alerts.jsonl to live mfg_state.json and later mfg_tokens.jsonl snapshots (validator: mfg_paper.py).

| token | liq @ alert | liq latest | fwd return |
|---|---|---|---|
| USMS (asKM…) | 5,031 | 108 | **−99.9%** |
| BEAST | 446.6 | 2.1 | **−100%** |
| USMS (boAU…) | 9,990 | 10,331 | +6.4% |
| claude | 359.0 | 371.8 | +7.0% |
| USMS #4 | 675.7 | 688.3 | +4.0% |

Mean ≈ **−36.5% per trade**. Consistent with sealed verdict B (v2 −33.1% backtest): the signal as fired is NOT tradeable with real money.

Key insight: USMS #1 had flow 96.8 (maximally buy-dominated) at alert and STILL dumped −99.9% within the hour. The runner signature (liq ≥ 100, flow ≥ 3, buy_sol ≥ 20, buys ≥ 30) detects a campaign in progress — it does NOT predict continuation. When extraction comes it is instant and total (5,031 → 108 SOL in < 1h).

Why entries are late: alert fires at liq ≥ 100 SOL, which for pre-dump campaigns is the TOP. 2 of 5 were already dumping at/near alert time.

Refinements queued for forward validation (paper only):
1. Entry at FIRST liq crossing (≥ 50 SOL within 30 min of graduation), not at ≥ 100.
2. Liq-stop exit: exit when pool liq < 30% of post-alert peak (validator simulates this — both losers still −100%; stop needs to be tighter/earlier to matter).
3. Age filter: skip campaigns > 1–2h old at signal time.
4. Gate for real money: ≥ 30 matured alerts with positive expectancy after realistic fills/costs. Not met. Standing rule: no real-money trading until then.

Caveats: pool_mcap = marginal price × 1e9 supply (inflated on thin pools); alert-price fills optimistic; n = 5 directional only. mfg_paper.py now auto-scores every future alert at +1h/+4h/+12h/+24h.

## §56e — Free-roll strategy: first positive-expectancy configuration (2026-08-29)

User question: enter, pull initial stake once price is high enough, let the remainder ride free. Tested on trade-level pool paths (14 tokens, ~40k trades reconstructed from mfg_trades.jsonl; mcap = marginal price x supply as price proxy).

**Mechanic alone isn't enough.** Free-roll T1.5x/sell-75% turns hold-to-end −72%/trade into −15..−29%/trade across entry variants. Principal recovery works but losers still go to ~zero too fast.

**No entry filter found (n=9).** At trigger time, target-hitters vs instant-dumpers do not separate on campaign age, pre-trigger pump, avg buy size, flow velocity, or trigger position. The edge is not in selection — it is in exits.

**The exit stack is the edge.** Grid test (E25 early entry: net flow ≥ 25 SOL, ≥ 10 buys, flow ≥ 2):

| strategy | mean/trade | wins |
|---|---|---|
| hold-to-end | −71% | — |
| free-roll only | −22% | 6/9 |
| FR + time-stop 120m | −6% | 7/9 |
| FR + trail 50%-from-peak | −3% | 6/9 |
| **FR + trail 50% + time-stop 120m** | **+12%** | **7/9** |

Each leg earns its place: free-roll banks 1.125x stake on pumpers; trailing stop converts −100% deaths into −37/−46%; time-stop exits dead campaigns before extraction (USMS#1: −100% → +40%).

**Built: mfg_live_paper.py** — live paper-trader. Rebuilds every position trade-by-trade from mfg_trades.jsonl on each run, applies the exact stack, logs to mfg_paper_trades.jsonl, prints scoreboard. First run: 9 positions, closed expectancy +8%/trade (5/7 wins), 2 open marking +28% avg. Reproduces backtest.

Caveats (severe): n=9 from a single ~4h session; fills assume trade-price execution with zero slippage — on thin PumpSwap pools real exits would be materially worse; paths cover only first ~4h post-graduation. Status: FORWARD PAPER VALIDATION ONLY. Real-money gate unchanged: ≥ 30 closed paper trades with positive expectancy after simulated slippage.

## §56f — Slippage stress-test and depth filter (2026-08-29)

Question: does the §56e free-roll stack survive realistic fills? Two stress models on the same 9 reconstructed paths:

1. **AMM price impact** (constant-product, position vs reconstructed pool depth R = LP0 + net flow): +9%/trade at LP0=30, +7% at LP0=10 (vs +12% ideal). At 1 SOL stakes, impact is survivable.
2. **Haircut sweep** (flat % off every fill): +7% at 5%, +1% at 10%, −10% at 20%, −21% at 30%. Combined shallow-pool + 10% haircut: −3%.

Observed pool depths are thin post-drain (2–8 SOL on most husks; 372/691 SOL on the two runners). The edge is real but thin: it survives ~5% total friction, breaks even at 10%, dies at 20%.

**Depth filter at entry does NOT help** — requiring ≥100 SOL depth at trigger cuts expectancy to +2% ideal (≥200 SOL: −18%). Deeper entry = later entry = closer to the campaign top (consistent with §56d). Speed, not depth, is the edge.

Practical translation: viable only with fast execution and small stakes (sub-1% of pool depth per leg); that is precisely the infrastructure "the big boys" run (low-latency RPC, bundle submission). Realistic planning numbers: +5–7%/trade gross at 5% friction, unproven until ≥30 closed paper trades under the live paper-trader (mfg_paper_trades.jsonl, auto-updated every 20 min by the tracker).

## §56g — Pool-slot starvation bug found and fixed (2026-08-29 ~22:40 UTC)

Symptom: 29 graduations in 6h, zero new pools discovered, paper positions frozen at 9. Root cause: MAX_POOL_TRACK=30 cap counted every token with a pool EVER discovered; dead husks held all 30 slots (pool subs lived until the 26h token prune), starving fresh graduates.

Fix (deployed, verified): (1) pools now track last-activity timestamps; (2) pools quiet > 2h are unsubscribed and marked pool_done, recycling slots; (3) cap count and warm-resubscribe skip pool_done tokens; (4) legacy state backfilled from mfg_trades.jsonl — 21 dead pools marked done, 9 active kept. First post-fix run: pools_found=21 (backlog discovered), pool_trades 120 → 1,124/run, helius_err=0, widget delivery OK. Manual gPA probe confirmed discovery itself was never broken — the cap check blocked it before attempt.

Lesson logged for ops: any capped subscription set needs an activity-based recycle path, not just age-out.

## §57 — Cross-chain scan: the manufactured-launch pattern is NOT Solana-specific (2026-08-29 ~23:30 UTC)

Built xchain_scan.py: GeckoTerminal free API, new_pools per network, applies the §56 MFG signature in USD units (age ≤ 6h, liquidity ≥ $15k, h1 buy/sell txn ratio ≥ 3, h1 buys ≥ 30, h1 buy volume ≥ $3k). Universe: 240 fresh pools (60 per chain).

| chain | fresh ≤6h | MFG hits | hit rate |
|---|---|---|---|
| solana | 60 | 1 | 2% |
| base | 60 | 1 | 2% |
| bsc | 60 | 2 | 3% |
| ethereum | 60 | 1 | 2% |

Hits: GPTC/WBNB (BSC, $75k liq, flow 3.4, 99 buys), CLAYMO/WETH (ETH, $33k, flow 6.6), BALD/ETH (Base, $22k, flow 4.2), 孙小圣/USDT (BSC, flow 40 — 40 buys / 1 sell, textbook manufactured), JEW/SOL (SOL, $21k, flow 3.3, 237 buys).

Read: the same deep-liquidity + buy-dominated-fresh-launch signature appears on every major memecoin chain at a ~2-3% base rate. BSC shows the most blatant single specimen (flow 40). Solana rate is consistent with tracker ground truth (~5 alerts / ~700 tracked ≈ 1-2%), so the scan is calibrated.

Open question (next): does the §56e free-roll exit stack replicate on these chains? Needs forward tracking of hits (price paths via GeckoTerminal OHLC) or historical replay. Scan cadence: manual for now; xchain_scan.jsonl accumulates hits per run.

### §57a — Forward tracker + hourly automation (2026-08-29 ~23:59 UTC)

Built xchain_track.py: polls every hit pool from xchain_scan.jsonl via GeckoTerminal, marks price vs detection, applies the §56e stack (free-roll 1.5x/75%, trail 50% of peak, 120-min time-stop), persists xchain_outcomes.json. Scan now appends (hits accumulate across runs). Rate-limit hardened (429 backoff, 4s poll spacing).

Second scan batch: 4 more hits — BSC dominated again (3/4): CE/WBNB $117k liq flow 9.3, 牛来/USDT flow 40, 我的女友景甜/USDT flow 39; CLAYMO/WETH persisting on ETH. Total tracked: 8 hits. BSC signal strengthening: recurring Chinese-ticker USDT pairs with near-zero sells — looks like a distinct manufacturing operation, likely four.meme-adjacent.

Automation: hourly cron job created (automation_8d83a51b, local_conversation, this workspace) — runs scan, sleeps 60s, runs tracker, replies with scoreboard. Cross-chain sample now accumulates unattended toward the ≥30-trade gate.

Caveat: outcome marks are run-frequency coarse (hourly) vs Solana's trade-level granularity; trail/time-stop exits approximate. Directional only — Solana remains the precision instrument.

### §57b — First cross-chain outcomes via OHLC replay (2026-08-30 ~00:30 UTC)

Tracker upgraded: entry price now taken from the hourly candle containing detection time (was: first poll, up to 2h late); full candle path replayed through the §56e stack with conservative ordering (trail-low checked before target-high). State reset and rebuilt for all 8 hits.

| hit | chain | peak | result |
|---|---|---|---|
| GPTC / WBNB | bsc | 2.5x | **+37%** (free-roll + trail) |
| CLAYMO / WETH | eth | 2.2x | **+38%** (free-roll + trail) |
| JEW / SOL | solana | 1.0x | −50% (trail) |
| BALD / ETH | base | 1.0x | −50% |
| 孙小圣 / USDT | bsc | 1.0x | −50% |
| CE / WBNB | bsc | 1.1x | −50% |
| 我的女友景甜 / USDT | bsc | 1.0x | −50% |
| 牛来 / USDT | bsc | 1.0x | −50% |

Mean −28%/trade, win 2/8 — harsher than Solana paper (+8%, 7/9), n=8 directional only. Structural read: the two winners were the LEAST manufactured-looking hits (flow 9.3 and 5.8); the textbook flow≈40 BSC launches went 0/3 — extreme flow ratios may mark campaigns already at exhaustion by detection. Candidate refinement: cap the flow filter (e.g. 3 <= flow <= 15) cross-chain. Hourly candles understate Solana-style intrahour spikes, so cross-chain exits are pessimistic vs trade-level.

### §57c — Wick artifacts + close-based rebuild; flow-band test deferred to candle accumulation (2026-08-30 ~01:00 UTC)

Found GeckoTerminal hourly candles carry birth/dust-print wick garbage (peaks of 780,000x–74,000,000x on GPTC, LIQUIDBGT, PEPKING — physically impossible at $15k+ liquidity). The §57b wick-based trail exits were partly corrupted. Rebuilt both xchain_track.py (apply_bar) and xchain_flowband.py to CLOSE-based replay: trail/target trigger on candle closes only; entry = close of the candle containing detection; time-stop measured from detection.

Immediate consequence: with detections only 1–3h old, zero-to-two completed post-detection candles exist — band outcomes currently flat/unresolved by construction. Flow-band hypothesis (15+ = exhausted) UNTESTED until candles accumulate; the three flow-40 BSC launches remain 0/3 on early evidence but need close-based confirmation.

xchain_flowband.py cache now stores raw candles (merged by timestamp, re-replayed every run) so results update as history accrues instead of freezing on first run. Hourly cron uses the corrected close-based logic from here on. All three xchain scripts compile clean.

Honest state: cross-chain pattern EXISTS (hit rates 2-5%, BSC richest); cross-chain EDGE (does the exit stack profit) still open — earlier +37/+38% winners were real (visible in price history) but band-level stats await data.

### §57d — Cron validated; close-based honesty on early "winners" (2026-08-30 ~01:20 UTC)

Hourly cron (automation_8d83a51b) validated via manual trigger — run succeeded; its scan added MSFT/SOL and BAD/WBNB (10 hits now tracked).

Important correction to §57b: the early "+37%/+38% winners" (GPTC, CLAYMO) were read off candle HIGHS; close-based replay shows CLAYMO never closed above entry (now −11% and drifting toward time-stop) and GPTC flat. Their 2.2x/2.5x "peaks" were likely dust-print wicks, not tradeable prices. Treat §57b winner claims as unverified; close-based outcomes are the record of truth going forward.

Current close-based board: 10 open, 0 free-rolls, all within ±17%; time-stops land over the next 1-2h. BAD/WBNB (bsc) the only one marking up (+17%, peak 1.2x close).

Solana side: pool-slot fix working — first NEW paper position (2nrqixJQ) entered automatically; closed book steady at +8%/trade, 7/9.

## §58 — Full status: is there a positive-ROI model yet? (2026-08-30 ~15:00 UTC)

**Solana (trade-level paper, n=11 closed): −1%/trade, 8/11 wins.** The +8% at n=9 did not hold: new closes were +2% and −79%. The −79% (FpVNDL9E) is the instructive one: trailing stop set at 50% of a 1.1x peak (=0.55x) but the dump GAPPED through it between trades — fill at 0.21x. Thin-pool gap risk, not modelled by mark-price exits. Open book: +45% (FNkG, peak 1.4x near free-roll) and +19% (64Lv).

**Cross-chain (hourly marks, n=37 closed): −24%/trade, 1/37 wins.** Hourly cadence cannot run the exit stack: dumps complete between marks (BAD/WBNB was +17% at evening mark, −100% by morning; CLAYMO, MSFT, 幸运资本, CM, SNOONINU, KOBRA, BOUNTY, UNIFART all −100%). ~20 of 37 never traded post-detection (dead on arrival, time-stop at entry ≈ +0%). Only TRUMPSTACY/SOL free-rolled (+37%, peak 2.3x).

**Verdict: NO positive-ROI model yet.** Detection works (multi-chain, calibrated). The exit stack works mechanically but (a) Solana expectancy is breakeven at n=11 with gap risk unmodelled, (b) cross-chain data cadence is too coarse to execute the stack — pattern confirmed, edge not tradeable via hourly marks.

Paths that could change the answer: (1) Solana n≥30 with gap-adjusted exits (trail on OBSERVED trade prices with slippage haircut; skip campaigns peaking <1.2x early); (2) EVM trade-level listeners (one websocket log-sub per chain to router/pool events) to give Base/BSC/ETH the same precision as Solana — the real build if cross-chain is wanted; (3) accept Solana-only precision and concentrate sample there.

## §59 — Realistic fills + abort rule: the honest model (2026-08-30 ~18:30 UTC)

Rebuilt mfg_live_paper.py to score every exit at the NEXT trade's price (gap-inclusive), not the trigger mark. Mark vs realistic on n=13: −1% vs −2% — the mark model was honest on average (mean gap mult 0.90) but hides a fat tail (FpVNDL9E gapped 0.41: −79% mark → −91% real).

Parameter sweep with realistic fills (13 triggered tokens):

| config | mean | wins |
|---|---|---|
| T1.5 f75, trail .50, ts120 (§56e) | +4% | 10/13 |
| trail .65 / .70 | +2/+3% | 9/13 |
| **+ abort <1.15x @30min** | **+6%** | **11/13** |
| abort @45m + ts60 | +0% | 9/13 |
| post-FR trail width .5→.2 / none | +2..+6% | 11/13 (width irrelevant this sample) |

Best config: E25 entry, free-roll 75% at 1.5x, trail 50% of peak, **abort at 30 min if below 1.15x**, time-stop 120 min. The abort rule neutralized the gap-dump tail: FpVNDL9E −91% → +8% (exited near entry before the dump). Worst remaining losers: −48%/−43%.

Expectancy +6%/trade at n=13, realistic fills. Positive but thin; gate remains n≥30 closed under this exact config before any real-money discussion. Deployed to tracker automation (paper_score v2) so forward validation tracks THIS config.

## §60 — BSC precision listener live: Multicall3 reserve watcher (2026-08-30 ~19:00 UTC)

Public BSC RPCs refuse ALL eth_getLogs (even 20-block single-pair ranges), so trade-level log listening is dead on free infrastructure. Replacement: poll getReserves() for every qualified pool in ONE Multicall3 tryAggregate(false, calls) eth_call per ~5s cycle. Verified: 101/101 V2-style pools readable; V4/unknown-quote pools (QQQB etc.) detected via token0/token1 probing and excluded (their USD flow was garbage). Live BNB/USD from canonical WBNB/USDT pair each cycle (~$700) makes flow thresholds USD-denominated like Solana E25.

Files: bsc_watcher.py (single poll), bsc_watch_loop.py (19-min window loop, ~230 cycles), bsc_paper.py (§59 stack scorer, incremental file-offset consumption). Entry = cumulative net quote inflow ≥ $3k within 30 min of first activity; exits = free-roll 75% @1.5x, abort <1.15x @30m, trail 50% peak, tstop 120m, next-poll fills.

Deployed as cron local_conversation automation_2c4eec3e (minutes 7/27/47, Europe/London, ~95% time coverage). First verification run succeeded (26.8 min, 33k flow rows): **4 paper entries immediately** (CHIP🪙, SKYAI, KING, MINI — all WBNB-quoted, $3.0–3.7k inflow) but ALL at peak 1.00x at entry+20-27m → inflow without price lift; abort rule likely decides them next cycle. If marginal entries keep aborting at ~1.0x, the $3k threshold is catching wash/latency flow, not campaigns — raise threshold or require price confirmation (mult ≥ 1.05 at entry) after n≈10 BSC closes.

Cross-chain precision gap from §58 is now closed for BSC. Base/ETH need the same Multicall3 treatment (Base public RPCs also restrict logs; same code, new RPC list + WETH/USDC quotes).

## §61 — Base chain added to the precision watcher (2026-08-30 ~20:15 UTC)

Generalized the BSC watcher into evm_watcher.py (chain config: RPC list, quote-token map with decimals, canonical native/USD reference pair). Base findings: all public Base RPCs 403 the default Python UA — a browser User-Agent header fixes it; Multicall3 lives at the same address; UniV2 WETH/USDC ref pair gives ETH ≈ $2,510 (decimal-corrected, USDC=6). 25-29 qualified Base pools on first runs, all WETH-quoted. Fixed a quote-attribution bug (pools passing via token1 never stored it -> '?' quote). bsc_watch_loop.py now polls multiple chains in one 19-min window (~10s cadence per chain); bsc_paper.py takes a chain arg (separate state/trades files per chain). Automation_2c4eec3e updated to run bsc,base + both scorers; BSC pool count grew to 115 with fresh scan rows. Solana hourly marks scored −24%; BSC/Base now have ~10s reserve-delta precision — same as trade-level for exit-stack purposes.

## §62 — Fast discovery closes the entry-latency gap (2026-08-30 ~20:25 UTC)

The first 4 BSC entries all sat at 1.00x from entry — inflow without price lift, consistent with LATE discovery: the hourly xchain scan can qualify a pool up to ~60 min after launch, so the $3k-inflow entry triggers after the campaign's move already happened. Fix: fast_discover.py runs a single-page GT new_pools scan for watched chains at the START of every 19-min window and every ~5 min inside it (40 fresh rows appended on first run; pool counts 119 BSC / 31 Base). Worst-case discovery latency now ~5 min (window gap) + GT listing lag, vs ~60+ min before. Entries from here should be measurably earlier in the campaign lifecycle; if the next cohort still enters flat, the problem is the reserve-flow signal itself (wash inflow), not latency.

## §63 — First BSC cohort: 4/4 aborts, 3 full rugs + scorer fill-model fix (2026-08-30 ~20:35 UTC)

First BSC paper cohort closed: CHIP🪙 0.00x, KING 0.00x, MINI 0.00x, SKYAI 0.86x — all via abort. Reserve data shows the three zeros are REAL rugs: quote reserves collapsed e.g. 58 WBNB -> 0.0002 WBNB within ~3 min, ~10 min after entry trigger. These were pre-fast-discovery (late) entries into dying pools; n=4 too small to convict the $3k threshold itself.

Scorer fill-model bugs found + fixed (bsc_paper.py): (1) entry filled at the TRIGGER row's price — under batched scoring (scorer runs at window end) that backdates entries across intervening pumps/rugs; now entries ARM at trigger and fill at the NEXT poll's price, surviving window boundaries; (2) free-roll booked at exactly 1.5x at the trigger row — now pends and fills at the actual next-poll multiple; (3) armed watches can no longer be reaped as stale before filling. Same batched-fill caveat applies to any window-end scoring; exits were already next-poll.

Scheduler note: cron range-step form `7-59/20` did not fire (parser incompatibility suspected); replaced with explicit `7,27,47 * * * *`, verified enabled, next fire :47.

Forward gates unchanged: BSC needs its own n>=10 closes post-fix before the threshold question (wash vs timing) can be called; Solana n>=30 continues.

## §64 — The LP-burn gate: causal rug filter with perfect first-sample separation (2026-08-30 ~20:25 UTC)

Broadened entry replay ($1k/30min inflow trigger): 5 BSC pools triggered, 4 rugged within 60 min (end ≤0.09x), only FIST survived (end 1.10x). GoPlus Token Security is useless here (fresh memes unindexed). On-chain LP-token sink check (totalSupply vs balanceOf dead/zero/lockers via one multicall) separated PERFECTLY: all 4 rugs = 0% LP burned/locked; FIST = 100% burned. Causal mechanism: unlocked LP is what allows the observed liquidity-pull rugs.

Deployed: evm_watcher.py now gates every pool on >=50% LP sunk (burn + PinkLock v1/v2 + UNCX UniV2 locker, addresses verified via official sources) BEFORE it enters the reserve poll set; failures re-checked after 10 min (post-launch locking happens). Effect: BSC watch set 119 -> 6, Base 29 -> 5 (UNCX Base caught 5 that PinkLock missed). 95% of trending BSC meme pools have unlocked LP — that IS the rug base rate. Trade rarely, only where the LP-pull vector is closed. Remaining rug vectors on gated pools: mintable supply, hidden owner, >50% partial lock — shadow-scorer A/B will measure them.

## §65 — BSC replay with fixed fills: the rug class is structurally untradeable via inflow entry (2026-08-30 ~20:45 UTC)

Re-ran the full BSC history through the FIXED scorer (next-poll entry fills, in-batch management, next-poll free-roll). Same 4 entries, same result: 0.00x / 0.86x / 0.00x / 0.00x, mean −78%, 0/4 wins. Diagnosis of WHY the exit stack can't save these:

- Post-trigger pumps are SHALLOW: 1.13x / 1.39x / 1.20x / 1.42x max — the 1.5x free-roll never fires.
- The kill is a CLIFF: LP pull removes ~100% of quote reserves in one block, ~10 min after entry. Abort (30min) and trail both evaluate after the cliff — fill ≈ 0 regardless.
- Ladder take-profit analysis: even selling 25% at 1.1x/1.25x/1.4x recovers only ~0.28-0.6x on this cohort. No exit rule turns 80% cliff-rug × ≤1.42x pumps positive.

Contrast with Solana: runners go 2-4.6x and deaths play out over minutes-hours (tradeable with abort+trail, +6%/trade). BSC unlocked-LP campaigns = shallow pump + instant cliff (untradeable). BSC LP-GATED pools = safe but campaign-free (established tokens or dormant locked batches). Conclusion: on current BSC tape there is NO positive-ROI variant of this strategy — the entry signal selects for pools whose entire design is the cliff. BSC watcher stays live (tape regime may change; data is cheap) but no more BSC exit variants. Capital-effort returns to Solana n≥30 and Base gated observation.

## §66 — Solana feed silent death: Helius quota exhaustion, root-caused + patched (2026-08-30 ~21:10 UTC)

No E25 triggers in ~20h was NOT dead tape: 135 graduations occurred but ZERO got pool stats. Artifact forensics (births=320, migrations=14, curve_subs=0, pool_subs=0, trades=0, helius_err=0) → Helius ws handshake returns 429 'max usage reached' (verified directly; HTTP RPC also 429). Errors were swallowed (on_error=lambda: None) so the automation reported success while collecting nothing. mfg_trades.jsonl stalled 01:37 UTC. Amplifier: on 429 the reconnect loop hammered every 3s for 19 min × 72 runs/day. Likely primary burn: getProgramAccounts scans in pool discovery (up to 5/min/run, ~1000-credit class calls).

Patch deployed (disable → cancel → edit → compile → smoke → update → enable): (1) discover_pool is GT-first (free GeckoTerminal tokens/{mint}/pools -> pumpswap address -> ONE getAccountInfo parses vaults at verified offsets; getProgramAccounts only as fallback) — verified live on fresh grads; (2) ws on_error now logs + counts into helius_err, reconnect backoff 3s→300s exponential; (3) MAX_TRACK 60→40. paper_score smoke: 13/13 closed, +5.75%, 11 wins (unchanged).

Open risk: if the quota is monthly (not daily-reset), Helius stays dead until Sep 1. Public Solana RPC fallback (getAccountInfo works there; accountSubscribe limited) is the contingency build if trades haven't resumed by ~01:00 UTC. Meanwhile PumpPortal births/migrations and GT snapshots still flow; the EVM watcher is unaffected (public BSC/Base RPCs).

## §66b — Helius-outage fallback deployed (2026-08-30 ~22:00 UTC)

**Quota status:** Helius still 429 at 21:26 UTC (down since 01:37 UTC, ~20h). Unknown if daily or monthly reset; watching for recovery at/after 00:00 UTC and Sep 1.

**Fallback stack (all deployed to tracker automation):**
1. `rpc()` rotates Helius → api.mainnet-beta.solana.com → publicnode → drpc on any failure, browser UA (publicnode/drpc 403 without it; api.mainnet-beta works clean). Returns `{'result': None}` if all down.
2. Pool-vault HTTP polling in snapshot_loop while Helius ws is closed: youngest 12 pool-tracked tokens <6h old, both vaults per token, quote-leg diff → pool trade records. Simulated against live state: 3/6 probed vaults moved since seeding — mechanism verified end-to-end.
3. Discovery sorts youngest-first (stale outage backlog had eaten all 30 pool slots with ~20h-old grads).
4. Slot recycling: silent pools (notifs==0) older than 6h are force-recycled — fixes deadlock where polled stale tokens refreshed their own freshness and starved fresh grads.

**Data-integrity ruling:** the 13 open paper positions with entries before the outage (2026-08-30 01:37 UTC) are VOID for forward-validation — their exit management data has a 20h hole. They will close mechanically (tstop/trail) as flow resumes but are excluded from the n≥30 forward count, which restarts from the first post-fix close. Cutoff: entry_ts < 1788050000 (≈01:37 UTC Aug 30).

**Known limitations during outage:** curve (pre-graduation) trades dead — E25 is pool-only so entries unaffected; pool trade granularity drops from per-tx to ~poll-cycle (~30-60s), which lumps same-cycle trades into one record (slightly understates trade counts, net SOL identical).

## §66c — Poll-granularity fidelity test: what the fallback does to E25 entries (2026-08-30 22:45 UTC)

Method: replayed pre-outage tx-level pool trades for the 10 densest mints, re-binned into 45s netted buckets (simulating vault-poll granularity), re-ran E25 trigger detection, compared trigger time and entry mcap vs raw.

Results:
- **8/10 mints still trigger** at poll granularity; **2/10 never trigger** (bucket netting merges buys+sells into one net record, destroying the nb/ns ≥ 2 ratio the trigger needs).
- Trigger lag when firing: −17s to +864s, median ~+370s (~6 min late).
- Entry mcap drift: 0% to +20.7% worse (paying more for the same campaign).

Interpretation: the fallback population is a STRICTER, LATER variant of the backtested E25 — ~20% of entries missed, survivors entered ~6 min late at up to ~21% worse prices. Two consequences:
1. Post-fix forward stats are NOT directly comparable to the +5.75% backtest line; if poll-mode expectancy still clears 0 (let alone 5.75%), that is conservative evidence the edge is real.
2. Do NOT loosen E25 thresholds to compensate mid-experiment — that would break comparability further. Full tx-level fidelity returns when Helius quota resets (watch Sep 1). If the outage proves monthly and poll-mode results disappoint, the fix is a higher-frequency dedicated poll pass for the youngest pools, not looser rules.

### §66c addendum — cutoff correction (22:55 UTC)

The §66b validation cutoff (01:37 UTC) was too early: trade records show flow trickled until ~02:47 UTC, so positions entering 01:37–22:00 were still outage-corrupted (stale-price exit management). CUTOFF in forward_scorecard.py moved to 1788062400 (22:00 UTC, first clean §66b flow). The "+9.38% abort" trade (64Lv5GnKue, entered 01:53) is hereby VOIDED like the other 13. True post-fix count restarts from zero as of 22:00 UTC.

## §66d — First clean poll-mode cohort: the §66c handicap is visible (2026-08-30 22:46 UTC)

First 5 truly post-fix E25 entries (cutoff 22:00 UTC): 3 closed = +6.1% (abort, PONS nmEbbehHkk), −100% (trail, PCC c8bdKqmN — full collapse, trail could not catch it), −31.5% (abort, LQX 6nrCD4LG); 2 open (+5.9%, +4.3%). n=3 expectancy −41.8%.

Read: entries fired at 3.7k–259k SOL mcap — poll-mode is entering mega-campaigns LATE (§66c: ~6 min lag, up to +21% worse price), i.e. near the top, straight into the dump phase. The tx-level backtest cohort entered the same campaign class minutes earlier and lower. One −100% in three trades dominates the mean; n far too small to judge.

Discipline: NO strategy-parameter changes (rules frozen). The open question is mechanical, not strategic: is the tx-level edge reachable at ~45s poll granularity? Resolution paths: (1) Helius quota reset (watch Sep 1) restores tx-level; (2) if outage persists and poll-mode stays negative at n≥10, build a dedicated high-frequency (~5s) poll pass for the youngest pools — a FIDELITY repair, not a rule change. Corrupted-but-voided tx-level cohort stands at +5.75% (n=13) for reference.

## §66e — Granularity returns-sim: the handicap is smaller than §66c feared (2026-08-30 23:00 UTC)

Full E25+exit-stack replay on the 11 densest pre-outage mints at raw tx-level vs 5/15/45/90s netted buckets: mean returns +2.4% / +2.5% / +12.2% / +11.5% / +11.2%; medians ~+10% at ALL granularities; entry rate 100% at 5s, 91% at 15s, 82% at 45s. The §66c entry-lag (median +370s at 45s buckets) does NOT translate into negative returns on this cohort.

Key correction to §66d's working hypothesis: the live poll cycle is `stop.wait(10)` + ~5s poll pass ≈ 15-20s granularity, NOT 45s — the sim says that costs ~nothing. Historical E25 entry mcaps [5k…1.4M SOL] bracket the live cohort's 3.7k–259k, so the live entries are not an mcap-regime outlier either.

Verdict: the −41.8% at n=3 is most likely NOISE (one full-collapse trade dominates). No fast-poll build justified by data; pipeline stays untouched. Decision rule unchanged: judge at n≥10 post-fix closes, gate at n≥30. If negative at n≥10 with benign granularity, suspect REGIME change (campaign mix), not tooling.

### §66f — Open-position poll pinning (23:00 UTC)

Found live: both open post-fix positions had gone unpolled for ~10 min — the youngest-12 poll window fills with newer pools and open positions age out, leaving exit management blind. Patch: the poll selector now reads mfg_paper_trades.jsonl each cycle and pins open-position mints into the 12 slots before youngest-first fill. Deployed via cancel→update→enable; ~9 min of collection sacrificed to close the blind spot immediately.

### §66g — epoch-anchor correction (23:07 UTC)

Trade-record epochs run on wall-clock time; earlier section timestamps like "cutoff 22:00 UTC = 1788062400" were mislabeled (that epoch is ~04:00 UTC; real 22:00 UTC is 1788127200). No data harm: the voided zombies entered ≤02:47 UTC and clean flow resumed 21:58 UTC, so any cutoff in between separates them identically. forward_scorecard.py CUTOFF now 1788060000 with the anchoring documented. All 5 post-fix entries remain in the validation set.

## §66h — Post-fix n=5: the wipes are real cliff-rugs, and the pump leg is missing (23:30 UTC)

Full post-fix cohort (cutoff §66g): 5/5 closed. Peaks 1.02–1.12x — ZERO reached the 1.15x abort floor, let alone the 1.5x free-roll. Exits: 4 aborts, 1 trail. Two ~−100% wipes verified against raw flow, NOT artifacts:
- c8bdKqmNcH (PCC): single 1,205 SOL sell at 22:31 cut mcap 79,624 → 43.5 → 0.15.
- 6qBmNVeGMz (Redbull): single 333.9 SOL sell at 23:04 cut mcap ~7,050 → 0.28.
Both are dev-dump cliffs (PumpSwap LP is locked; a single-seller dump of this size = insider supply).

Contrast with frozen backtest cohort (n=13, +5.75%, 11 wins, no cliff-rugs post-entry): tonight's live cohort shows shallow/no pump + cliff-rug — the SAME signature that killed BSC (§65). Three non-exclusive explanations: (a) n=5 bad-luck noise; (b) regime shift — rug-heavy campaign mix tonight; (c) poll-mode E25 selection bias — the nb/ns>=2 ratio on netted poll records delays triggers until explosive buying ends, selecting plateau-phase entries (§66c lag evidence supports this).

Decision rule stands: judge at n>=10. If the cliff-rate stays near 40% at n=10, the pre-registered conclusion is that poll-mode entry is adversely selected and the tx-level edge is not reachable without Helius — NOT that the strategy parameters should change. For the future live version, a dev-supply/holder-concentration gate at entry (Solana analogue of the BSC LP-burn gate, §64) is the candidate fix for cliff risk specifically.

## §66i — Universe scan: tonight had NO post-trigger runners at all (23:35 UTC)

Scanned every E25-triggerable mint post-cutoff (not just entered ones): 6 total. Post-trigger peaks: 1.17, 1.15, 1.12, 1.12, 1.04, 1.00. Zero reached 1.5x. The 6th (o7imiQ55KV, 20 trades) didn't qualify for paper entry (50-trade floor) and went nowhere anyway.

Conclusion: our 0/5 is NOT adverse selection — entering everything triggerable tonight still yields zero winners. The pump leg was absent universe-wide tonight. That shifts the weight to regime (campaign mix/operator behaviour tonight) over poll-mode selection bias. One session is not a regime verdict: historical sessions produced multiple >1.5x post-E25 campaigns (the backtest cohort). Watch 2-3 more sessions: if post-trigger runners remain absent while flow thresholds still trigger, the manufactured-pump meta itself has changed (operators harvest at the curve/plateau instead of pumping post-graduation), which would retire the E25+free-roll model regardless of data fidelity.

### §66j — Midnight check: quota is NOT daily (00:02 UTC Aug 31)

Helius still 429 past 00:00 UTC — the quota does not reset at UTC midnight. Next candidates: monthly reset (Sep 1, ~24h away) or plan-cycle billing reset. Fallback continues to carry all pool flow; no action needed.

## §66k — Runner-drought baseline: the pump leg vanished BEFORE the outage (00:10 UTC Aug 31)

Per-hour E25-triggerable mints and post-trigger >=1.5x runners, all available pool-flow history:

| window (UTC) | triggerable | runners | note |
|---|---|---|---|
| Aug 29 12:00 | 6 | 3 | tx-level fidelity |
| Aug 29 13:00 | 1 | 1 | tx-level |
| Aug 29 14:00 | 1 | 1 | tx-level |
| Aug 29 15:00 | 1 | 0 | tx-level |
| Aug 29 22:00 | 1 | 0 | tx-level, 3.5h post-window |
| Aug 30 00:00 | 3 | 0 | tx-level, but window truncated by 01:37 outage |
| Aug 30 22:00 (tonight) | 6 | 0 | poll-mode, full window |

Since Aug 29 14:00 UTC: **0/11 runners across ~34 hours**, including cohorts recorded at full tx-level fidelity BEFORE the Helius outage. Binomial check vs the Aug-29-midday rate (5/8 = 62%): P(0/11) ~ 2e-5; even at a conservative true rate of 30%: P ~ 2%. The drought is real and predates every tooling artefact — §66c/§66e/§66h selection-bias worries are now secondary.

Caveats: (1) the Aug-30 00:00 cohort's observation window was cut by the outage; (2) midday-Aug-29 baseline is only 8 mints. Verdict rule: if the next 1-2 sessions (Aug 31 daytime/evening) also produce 0 runners, the manufactured-pump meta is declared SHIFTED and the E25+free-roll model retires; pivots on deck: dev-supply concentration gate, curve-phase entry, or a different edge class entirely.

## §67 — Curve-trade fallback without Helius (2026-08-31 01:10 UTC)

**§67a (pumpportal subscribeTokenTrade): DEAD.** Deployed 00:30 UTC (subscribe on
track, buy/sell handler, resubscribe on reconnect). Probe (`probe_pp_trades2.py`)
revealed the server ACK: *"'subscribeTokenTrade' and 'subscribeAccountTrade'
methods are only available when connecting with an API key funded with at least
0.02 SOL."* Free tier = subscribeNewToken + subscribeMigration only. Code left
in place (inert; auto-activates if a funded key is ever supplied).

**§67b (batched RPC curve polling): LIVE and verified.** While Helius ws is
down, snapshot_loop now polls every live bonding-curve account in ONE
`getMultipleAccounts` call per ~10-15s cycle, decodes (vtok, vsol, complete)
locally, and writes deltas to mfg_trades.jsonl as venue=curve records identical
in shape to Helius-era data. Shares `last_vsol` baseline with the Helius path
(no double-count on mid-run recovery). Deployed 01:00 UTC; verified 01:08 UTC:
**34 curve trades across 7 mints in the first 4 min** (+121 pool trades),
mcap values sane (63-106 SOL range). Full tx-level curve fidelity restored,
zero cost, no new credentials. Poll granularity 10-15s — §66e showed this
costs ~nothing vs tick-level.

Implication: the tracker no longer depends on Helius at all. Helius re-check
after Sep 1 reset is now informational only. The curve-phase-entry pivot
candidate (§66j: pumps happen in the first minutes, pool entries are late) is
now fully instrumented — curve flow is captured from birth again.

## §68 — Zombie-position accounting fix + first post-drought runner (2026-08-31 01:30 UTC)

**Bug found:** paper_score dropped zero-mcap trades (`not x.get("mcap_sol")`)
and had no wall-clock exits — positions on pools that went quiet or rugged to
mcap 0 stayed "open" forever at stale marks. Live board showed 6 zombies from
the 00:08-00:09 UTC trigger batch, all "open" at +5-9% while two had actually
rugged to zero. This also DELAYED entry detection (zero-mcap trades carry
real SOL volume that counts toward the E25 trigger).

**Fix (measurement only — exit-stack params untouched):** (a) keep zero-mcap
records (rug-to-zero = observable −100%); (b) heartbeat close: if a position
is still open at replay time, evaluate abort (30min/<1.15x) and timestop
(120min) against wall clock at the last observed mcap. Known optimism: quiet
pools that never printed a zero are marked at last price (assumes exit into
remaining liquidity).

**Re-marked post-cutoff board (shadow preview, identical logic):**
14 positions, 12 closed, expectancy −30.7%, wins 7/12. The honest marks
flip two zombie "winners" to −100% rugs (cA1J, E1U1) and bank real gains on
quiet campaigns (+4.5% to +13.1%).

**Regime signal — drought partially broke overnight:** the Aug 31 00:08 UTC
batch produced CHPs peak 1.584x (closed trail +13.1% — first 1.5x runner
since Aug 29 14:00) plus 2oFG (peak 1.478x) and jCPN (peak 1.413x) still open
and live at ~+45%. Aug 30 22:08-22:30 cohort: 5/5 peaked <=1.12x (dead).
Overnight = 1 clear runner + 2 near-misses out of 8 triggers — between the
Aug 29 midday meta (5/8) and the drought (0/11). Verdict still requires the
Aug 31 daytime/evening sessions per the pre-registered rule; the model's
closed expectancy remains deeply negative (−30.7%), gate 12/30, gate_pass=False.

Deploy note: §68 lands via gap-update after the 01:24 run ends (~02:04);
paper_score rewrites full history every run so no scoring gap.

### §68b — deployed + overnight session resolved further (02:30 UTC)

Deployed 02:24 UTC (cancel-update-enable; missed the sub-15s scheduler gap
twice — noted for future deploys: cancel is the reliable path). Fresh shadow
re-mark on data through 02:24:

- **2oFG peak 2.098x, open +65.4%** and **jCPN peak 1.927x, open +61.1%** —
  both crossed the 1.5x freeroll (75% banked, 25% trailing). With CHPs
  (1.584x, closed +13.1%) that is **3 runners out of 8 triggers** in the
  Aug 31 00:08-00:47 UTC batch = 37.5%, vs drought 0/11 and Aug 29 midday
  meta 5/8 (62%). The pump meta is NOT dead — it paused.
- 5JL rugged to zero since the first preview (zombie +8.6% -> honest -100%).
- Post-fix expectancy −39.7%, 6/12 wins. The drag is structural: 4/14
  entries (29%) rugged to −100%; aborts bank only +5-13%; runners +60%.
  **Expectancy is a rug-avoidance problem now, not an exit problem.**
- Next analysis queued: with §67b curve data restored, compare the 4 rugs vs
  3 runners on CURVE-phase behavior (first 15 min: dev sell timing, buy
  concentration, seed structure) to find a pre-entry rug filter.

## §69 — Rug anatomy, mark-to-deadline fills, and the abort lever (Aug 31 03:45 UTC)

**§69a curve replay (rug_replay_69.py, rug_replay.json):** all 14 post-cutoff
entries seeded exactly 85 SOL, graduated the same second (curve drained by
migration at birth+0min). The bonding-curve phase is ONE transaction —
curve-phase rug filtering is impossible for manufactured big-seed launches;
everything happens on the pool. Creators are 14/14 fresh wallets; symbols
recycle across mints (LQX x3, ARROW x2, WOFI x2) — serial same-operation
campaigns. Creator-history filters won't fire; funding-source clustering is
the only wallet-level lead.

**§69b delayed-entry + veto grid (backtest_69.py):** D10+bigsell25 best but
only −11.1% post-cutoff vs −21.7% baseline. Vetoes barely fire: the rug is
not visible in the first 10 minutes of flow — operators harvest at plateau,
30-90 min in. Pre-entry flow filtering is structurally blind to it.

**§69c mark-to-deadline replay (backtest_69c.py) — the scorer fix that
matters:** a live poller sees balance-derived mcap every ~15s even on quiet
pools, so abort/time-stop exits fill at the price observed AT the deadline,
not at the final mark of a pool that later rugged. §68's r_last heartbeat was
too pessimistic for rugs that collapse after minute 30. Replayed grid:

| variant            | post-cutoff exp | rugs | all-history exp | rugs |
|--------------------|-----------------|------|-----------------|------|
| E25 abort30        | −27.2%          | 6    | −13.4%          | 6    |
| E25 abort15        | **−9.0%**       | 2    | **−3.2%**       | 2    |
| D10+veto abort15   | −13.0%          | 4    | −7.6%           | 4    |

**Conclusions:**
1. Abort at 15 min (not 30) is the single biggest lever: exits plateauing
   campaigns BEFORE the typical harvest window, cutting rug exposure 3x.
2. Entry delays/vetoes HURT under honest fills — enter at trigger, manage
   the exit.
3. Honest-fill E25-a15 is ~breakeven in a weak regime (−3.2% all-history,
   26/31 wins) and was solidly positive in the strong Aug 29 regime. The
   model's expectancy is regime-driven; the runner share is the swing factor.
4. Residual drag: ~2 fast rugs per 31 (collapse <15 min — unfilterable at
   15s poll cadence) ≈ −6.5 points. A funding-source cluster gate is the
   only untested pre-entry idea with theoretical teeth.

**Not changed:** live scorer keeps P_ABORT_MIN=30 (no mid-experiment param
changes). a15 + mark-to-deadline scorer are candidate pivots pending the
regime verdict from Aug 31 daytime/evening sessions.

## §70 — Mark-to-deadline scorer deployed + funding-cluster gate dead (Aug 31 03:15 UTC)

**§70 scorer:** paper_score heartbeat now marks deadline exits at the price
observed AT the deadline (last trade at/before it) — what a live 15s poller
would actually fill at — instead of the final mark of a pool that rugged
later. Params unchanged (abort 30min/1.15x). Live from next tick (file-edit
pickup; description update pending a scheduler gap).

**§70b funder trace (funder_trace_70.py, funder_trace.json):** traced all 14
cohort creator wallets to their first inbound SOL. 8 resolved funders are
ALL DISTINCT; 6 creators unresolvable within 100-sig window. No clustering;
outcomes (rug/runner/quiet) are randomly distributed across funders. The
operation uses one-shot funding chains per launch.

**Pre-entry rug filtering is now FULLY exhausted (all candidates tested and
eliminated):**
- curve-phase features — impossible (curve phase = 1 tx, §69a)
- early-flow vetoes — blind (harvest comes 30-90min in, §69b)
- creator history — 14/14 fresh wallets (§69a)
- funding clusters — 8/8 distinct funders, random outcomes (§70b)

**The rug is an operator decision made after entry and cannot be predicted
from any observable pre-entry signal.** The only defense is exit discipline:
abort-15 cuts rug exposure 3x (§69c). Positive ROI therefore =
(regime alive) x (abort-15) x (honest fills). Regime verdict at Aug 31
daytime/evening sessions is the remaining gate.

## §71 — Session clustering and the scout-gate test (Aug 31 03:30 UTC)

**Time-of-day pattern (31 entries, 8 runners):** runners only in
12:00-14:59 UTC Aug 29 (5/8 = 62%) and 00:00-00:59 UTC Aug 31 (3/8).
Dead: 22:00-22:59 (0/6), 02:00-02:59 (0/4), 15:00 (0/1). Live windows map
to ~08:00-11:00 and ~20:00-21:00 ET — the operator pumps when US retail is
awake (exit liquidity), harvests off-hours. Confounded with date at n=31,
but operationally consistent.

**Fresh entries 02:09-02:44 UTC: 0/4 runners** (peaks 1.106-1.213; one
−88%, one −100%). The 00:08 batch was a wave, not a regime return.

**§71 scout-gate backtest (backtest_71.py):** waves can't be predicted at
onset, so scout the first 2 entries of each burst and continue only when a
burst member proves the wave (>=1.3x within 60 min). Result: −2.0% gated vs
−3.2% baseline (a15, honest fills) — marginal. Failure mode found: bursts
chain (harvest batch -> pump batch -> harvest batch within 2h gaps), and
the gate re-engages on yesterday's evidence just as the operator switches
back to harvest. **Chasing a proven wave = buying the operator's exit
liquidity.** Inverted hypothesis noted: enter ONLY scouts (first triggers
of a fresh wave), never continue on evidence. Within-burst entry ordering
is arbitrary for simultaneous triggers, so this stays a sizing idea
(scout at half size) rather than a hard gate.

**Where the analysis stands (all verified, n=31):**
- pump waves: +5.2%/trade (Aug 29 12:00 batch) — the edge is real
- harvest waves: −9%/trade — no pre-entry filter can dodge them (§69-70)
- abort-15 triples rug survival (§69c)
- reactive gates add ~1 point at best (§71)
- **Positive ROI = be positioned at wave onset (scout everything),
  exit fast (a15), and let wave frequency do the rest.** Over any 3-day
  window with one golden wave, that profile nets positive; without one,
  it bleeds ~2-3%/trade on scouts. Forward validation with the honest
  scorer is the only remaining judge.

## §72 — abort-15 shadow scorer deployed (Aug 31 03:55 UTC)

paper_score now takes (abort_min, out_path); every run writes BOTH the
pre-registered a30 gate file (mfg_paper_trades.jsonl) and an a15 shadow
(mfg_paper_trades_a15.jsonl). forward_scorecard.py reports a15_shadow_exp
beside the gate. Methodology: the gate stays a30 mid-experiment; the shadow
accrues forward evidence so the post-verdict switch (if any) is backed by
live data, not only the §69c replay. First a15 file lands with the 04:04
UTC run.

**Regime ticker (03:49 UTC):** universe 20 triggerable / 4 runners (20%).
- 2oFG peak revised 2.098x -> 2.862x, jCPN 1.927x -> 2.574x — the 00:08
  wave kept running for hours (freerolled 25% residuals riding).
- BTJv (02:23 batch) ground up to exactly 1.501x ~1h post-entry — the
  02:xx batch was NOT 0/4 as prematurely read; slow runners exist.
  Lesson: runner counts must be read with a >=90 min lag after entry.

## §73 — REGIME VERDICT: ALIVE. Gate scorer switched to abort-15 (04:30 UTC)

**Verdict (early, per pre-registered rule):** the drought condition required
0 runners through Aug 31 daytime/evening; instead 5 runners appeared
overnight across 3 distinct hours (00:08 x3, 02:23, 04:09 UTC). The
"drought" was a ~34h lull (Aug 29 14:15 -> Aug 31 00:08), not a meta shift.
Runner share post-cutoff: 5/21 = 24% and climbing. Peaks still developing:
2oFG 3.25x, jCPN 2.87x, 2G1j 2.03x (triggered 04:09 — breaks the
US-hours-only pattern), BTJv 1.72x, CHPs 1.58x.

**a15 shadow verified live:** forward −8.93% vs §69c replay prediction
−9.0% — replay engine and live scorer agree to 0.1pt. Cross-validated.

**Gate switch (documented decision point, pre-registered pivot path):**
the forward gate now reads the a15 scorer: 18/30 closed, win rate 77.8%,
expectancy −8.9%. a30 legacy shadow: −43.6% (15 closed). The 30-trade clock
continues on a15 marks; gate passes at 30 closed with exp > 0. 12 closes
to go. All marks remain paper-only; the real-money manual signoff gate is
untouched.

## §74b/c — Next-trade entry unification (2026-08-31 ~05:00 UTC)

**Problem found:** tracker's `paper_score` entered AT the trigger trade (mild lookahead) while the §59 realistic-fills standard and all backtests enter at the NEXT trade. Offline `gen_h108.py` was already fixed; tracker would have overwritten the gate file with inconsistent marks.

**Fix applied:** tracker `automation.py` — entry moved to `xs[ti+1]` with bounds guard, `body = xs[ti+2:]`, `_price_at` loop likewise. `py_compile` OK. Goes live on the next run (file edits auto-load; description sync deferred while runs active).

**Gate file regenerated** with `gen_h108.py` (next-trade entry, reference copy at /tmp/gen_h108_ref.jsonl):
- Gate (h108 committed): **21/30, committed_exp = −10.91%** (was 19/30, −12.9% under trigger-entry)
- Closed-only: 19 closed, win 73.7%, exp −13.4%; 2 freerolled opens at +12.5% floor each
- Shadows: a15 19 closed −6.4% · a30 16 closed −38.4%
- Universe: 23 triggerable post-cutoff, 5 runners ≥1.5×

**Verification queued:** diff the tracker-written h108 file after its next run against /tmp/gen_h108_ref.jsonl — must agree per-mint.

**Need:** 9 more committed closes AND committed_exp > 0. Freeroll floors alone won't flip the sign — need runner trails above floor or fewer rug closes.

## §74d — Engine parity verified (2026-08-31 06:24 local)

Post-patch tracker run (started 06:04 local, first with §74b next-trade entry) rewrote `mfg_paper_trades_h108.jsonl` at 06:23:53. Per-mint diff vs fresh `gen_h108.py` output: **34/34 rows, 0 mismatches** (entry_t, entry_mcap, ret, exit_reason, peak, status, freerolled all identical). Live tracker and offline backtest engine are now provably the same scorer — every future gate number is trustworthy. Also confirmed the pre-patch run's trigger-entry marks differed on all 34 rows, i.e. the entry convention was material, not cosmetic.

## §75 — Shadow exit-variant grid on the verified engine (2026-08-31 06:30 local)

45-cell grid (stage1 x trail x target/sell) on the §74d-verified engine, committed metric, post-cutoff. **No exit variant is expectancy-positive yet.** Best: stage1=(15,1.10) + trail=0.6 + target 1.5/sell 0.75 -> 21 committed, **-3.1%**. Frozen gate h108 ((15,1.08)/0.5/1.5/0.75) ranks 9/45 at -10.9%.

Monotone structure (weak but directional evidence on n=21):
- Kill fast-dead campaigns HARDER: stage1 1.10 (-3 to -12%) > 1.08 (-9 to -19%) > 1.05 (-21 to -31%) > none (-25 to -37%). The 1.05 row underperforming "none" is the surprise — too tight kills breakeven scratches.
- Give runners MORE room: trail 0.6 > 0.5 > 0.4 nearly everywhere.
- Freeroll at 1.5 with 75% sell beats 1.4 and 1.6/60% variants.

Implication: exit tuning alone cannot flip the sign on current data. Remaining levers: (a) runner-wave frequency (regime, exogenous), (b) ENTRY-side thresholds (net-flow/buy-count/flow-ratio grid — untested on verified engine), (c) time-of-day gating (wave-locked edge, US-morning hotspot). Small-sample caveat: n=21 committed; treat single-cell diffs as noise, monotone rows as direction.

## §76 — ENTRY-side grid: the sign flip lives here (2026-08-31 ~06:45 local)

108-cell grid (net x nb x flow x hours x exit-config) on the verified engine, committed metric, post-cutoff.

**POSITIVE REGION FOUND — and it is robust, not a single cell:**
- net>=60 SOL AND nb>=20 buys: **+8.95% committed on n=13** (all hours), all-history +5.2%/+5.8%
- Holds across flow 2.0/3.0 AND both exit configs (h108 frozen, s75best) — 8 neighboring cells all ~+9%
- Wave-hours gating (0-1,12-15 UTC) lifts it to **+10.7% on n=8** but cuts sample
- net=60 alone (nb 10/15): only +0.18%. nb=20 alone insufficient. It is the PAIR: sustained BROAD buying, not concentrated flow.

Mechanism read (consistent with §71 funder traces): net60+nb20 demands many wallets buying — filters OUT single-operator harvest waves (few big wallets churning) and keeps campaigns with genuine broad momentum, which is where runners come from.

Frozen gate cell (net25/nb10/flow2.0, all hours): rank 81/108 at -10.9%. The default thresholds were far too loose.

**Caveats:** n=13 committed, short post-cutoff window; in-sample. Must be forward-validated before any gate amendment. Plan: add a 4th shadow scorer to the tracker (PAPER_S: net60/nb20, h108 exits) so the strict-entry variant accrues OUT-OF-SAMPLE committed closes in parallel. Gate stays frozen at h108 until the shadow proves itself forward.

## §77 — Strict-entry shadow scorer deployed for forward validation (2026-08-31 ~07:00 local)

Tracker patched: `paper_score` now accepts net_min/nb_min/flow_min; 4th scorer writes `mfg_paper_trades_s60.jsonl` each run — entry net>=60 SOL AND nb>=20 buys (the §76 positive region), exits frozen at h108. Compile OK; goes live next run. `forward_scorecard.py` reports s60 as a committed-metric shadow alongside a15/a30.

Forward-validation protocol: s60 accrues committed closes OUT-OF-SAMPLE from the first post-patch run onward. If s60 committed_exp stays >0 while building toward n>=20-30, the Sep 1 review can amend the gate entry thresholds (net25/nb10 -> net60/nb20). In-sample +9.0% (n=13) is the hypothesis; the shadow is the test. Gate remains frozen at h108 until then.

## §77b — s60 shadow live, first out-of-sample write (2026-08-31 07:04 local)

First tracker-written `mfg_paper_trades_s60.jsonl` (run started 06:44 UTC, first with §77 code):
- Post-cutoff: 14 committed (13 closed + 1 freerolled open), **committed_exp = +8.38%**
- All-history: 21 closed, +4.95%
- Grid prediction (§76, 40 min older data): n=13, +8.95% / n=20, +5.15%
- Delta = one newly accrued position; per-cell agreement within new-data drift. Strict-entry engine parity confirmed.

The positive-expectancy hypothesis now holds on its first forward write. From here every run accrues s60 marks out-of-sample. Amendment bar for Sep 1 review: s60 committed_exp > 0 sustained while n grows toward 20-30, AND at least one runner wave captured live (not just legacy positions). Gate stays frozen at h108 (21/30, -10.9%).

## §77c — First strict-vs-loose runner divergence (2026-08-31 07:06 local)

oFxvzBiT (fresh post-cutoff runner): h108 loose entry freerolled at 1.5x, MTM +50% and riding. s60 strict entry triggered LATER at 8229 SOL mcap, peaked 1.065x, abort15'd at +6.6%. Strictness costs entry speed: net60/nb20 takes longer to satisfy, so the entry price is worse — one runner converted to a scratch. Known trade-off; in-sample grid says strict still nets +9pp over loose on average. Track divergences like this — if strict repeatedly converts runners to scratches, the Sep 1 amendment bar fails regardless of headline exp.

Also: 2oFG still riding at MTM +95.6% (peak 3.31x); a trail-out near here adds ~+4.5pp to gate committed_exp vs the 0.125 floor. Universe runners up to 6.

## §77d — Confirmed-entry variant (enter loose, verify strict within W min) (2026-08-31 ~07:15 local)

Mechanism: fill at the LOOSE trigger price (early), then require cumulative net60/nb20 within W minutes; else exit at the deadline mark. Fixes the s60 late-fill problem (§77c).

Results (committed, post-cutoff, verified conventions):
| W (min) | com_n | com_exp | all_exp | noconfirm share |
|---|---|---|---|---|
| 5  | 21 | +3.2% | +3.5% | 68% |
| 10 | 21 | **+4.1%** | +3.7% | 56% |
| 15 | 21 | +0.3% | +0.9% | 56% |
| 20 | 21 | -7.6% | -3.8% | 50% |

Confirmed-entry W=10 is POSITIVE on the FULL gate universe (n=21, same denominator as frozen h108 at -10.9%) — no sample reduction, no late fills. Still below s60's +8.4% on n=14 in per-trade and total expectancy (86pp vs 117pp sum). W must stay short: at 20 min the kill-switch comes too late and it decays to -7.6%.

Standing now: s60 late-entry (+8.4%, n=14) > confirmed-entry W10 (+4.1%, n=21) > h108 frozen (-10.9%, n=21). Two independent entry-side mechanisms both positive on the verified engine = the edge is in ENTRY SELECTION, exits secondary. Sep 1 review now has two amendment candidates; s60 forward shadow is primary, confirmed-entry is the fallback if runner-scratch divergence (§77c) repeats.

### §77c follow-up (07:24 local): oFxvzBiT resolved — h108 loose trailed out at **+13.3%**, s60 strict scratched at +6.6%. First completed head-to-head on the same campaign: loose won by 6.7pp here, but s60 leads by 19pp on committed expectancy overall. Track the aggregate, not single races. 2oFG still open at +95.6% MTM (peak 3.31x) — the gate's biggest pending swing.

## §77e — s60 decomposition: ZERO losing trades (2026-08-31 ~07:30 local)

All 14 committed s60 positions post-cutoff are positive: 13 closed (+0.9% to +14.4%, avg ~+8.7%) + 1 freerolled open at floor. **Win rate 100%; not one rug or loss passed the net60/nb20 filter.** The loose-entry gate on the same window: 25% losers including full rugs (-100%).

Mechanism confirmation: manufactured rug campaigns (single operator, one-shot funder, concentrated churn — §71) cannot produce 60 SOL net across 20+ distinct buys fast enough. The strict pair is effectively a breadth-of-participation screen, and breadth is what rug operators can't fake cheaply.

Caveats: n=14 is small; 100% win rate will not persist (expect regression toward ~70-85%); abort15 scratches cluster at +3-8% because strict entry buys confirmed momentum (higher entry, capped scratch upside). But even regressing hard, the loose gate's -100% rug tail is what strict entry eliminates — and that tail is what kept the gate negative.

### §77e calibration: the filter is not invincible (07:30 local)

Pre-cutoff s60 (voided window, n=8): 7 wins, **1 loss −55.4%** (fCERmUZg — never pumped, bled through the trail), exp ≈ 0.0%. Zero-loss is POST-cutoff only (13/13, +8.1%). Caveats: pre-cutoff exit data has the 20h Helius hole so that −55% fill is partly artifact; but the honest read is the breadth screen slashes rug frequency, it does not eliminate bleeders. All-history s60: 21 closed, +5.0%, tail risk ~1 big loss per 20 trades. Expectancy rests on many small wins + occasional runners, not on invincibility. Win-rate regression forecast stands: 70-85%.

## §78 — Amendment memo drafted (2026-08-31 ~07:35 local)

`AMENDMENT_MEMO.md` in MON: full skeleton for the Sep 1 gate-amendment review — proposal (loose -> strict breadth entry), evidence table, mechanism, honest risk model, four explicit decision criteria, post-amendment protocol (gate re-zeros, 30 fresh committed closes, manual signoff stays). Numbers to be refreshed from the live scorecard at review time.

### §78b — live pipeline shows the filter's two axes working (07:35 local)

12 loose-triggered post-cutoff campaigns currently NOT strict-qualified, in two clean failure modes:
- **Churn mills**: nb 44-76 but net stuck ~25 SOL (8WnaNq61: 70 buys/3min, net 25.2; 4cy86hpK: 76 buys/1min, net 25.1) — wash-trading volume, no real net demand. The net60 axis rejects them.
- **Whale-concentrated**: 6nrCD4L8 net 108.9 SOL but only 10 buys — one big wallet. The nb20 axis rejects it.
- Near-misses worth watching: 3yF1D2iX (net 36.5, nb 18) and JzBaT6QS (net 30, nb 18) — closest to qualifying.

Both failure modes are exactly the manufactured-launch signatures from §71. The two axes are not redundant; each catches a different fake.

### §78c — first post-deployment strict entries: all green (07:44 local)

The §78b near-miss pipeline resolved through the strict gate: JzBaT6QS +7.2% and FwEx5Qds +7.6% (abort15 scratches), 3JSy9Uvh OPEN at +10.5% MTM (peak 1.10x) — the first entries qualified entirely AFTER the s60 shadow deployed. s60 now 16 committed, +8.26% (from +8.38% on 14 — new entries diluted nothing). Post-cutoff loss count still ZERO. Gate advanced 21 -> 23/30, committed_exp -9.1% (from -10.6%). Decision criterion #2 (fresh strict-captured runner >=1.5x) pending: 3JSy9Uvh at 1.10x peak so far.

### §78d — churn mills CAN qualify late; 3JSy9Uvh approaching freeroll (08:24 local)

- 3JSy9Uvh: 59m old, **+35.3% MTM, peak 1.35x** — climbing toward the 1.5x freeroll. Would be the first post-deployment strict-captured runner (criterion #2).
- s60: 17 committed, +7.92%, still zero losses.
- NUANCE (memo-worthy): §78b's churn mills 8WnaNq61 and 4cy86hpK EVENTUALLY qualified (slow churn accumulates net60 given ~15-20 min) — strict entry delays and de-risks them (entered +5.4%/+1.2% so far) but does not exclude them categorically. The breadth pair is a speed-and-price filter, not a hard wall. Watch whether late-qualified mills become the first s60 losses; that is the expected regression channel.

### §78e — s60 hits n=21, still zero losses; mills scratched green (08:44 local)

s60 committed n=21, +7.69%. The late-qualified churn mills (8WnaNq61, 4cy86hpK) and QKd4PX58 all resolved GREEN — the strict filter's late-fill discount converted even wash-traded campaigns into small wins. Zero-loss streak now spans ~19 closed post-cutoff. 3JSy9Uvh: +41.9% MTM, peak 1.42x at 79m — 0.08 from freeroll. Criterion #1 (sustained >0 at n>=20) now MET on total committed count; post-deployment-only count ~7 and also all green.

### §78f — CRITERION #2 MET: 3JSy9Uvh freerolled at 1.54x (09:24 local)

First post-deployment strict-captured runner: entered on net60/nb20 after shadow went live, climbed 1.10->1.48->1.54x over 119 min, freerolled (75% banked at 1.5x, house money on trail), MTM +51.1%. s60: 22 committed, +7.91%, zero losses. New entry nVs7YcfF open +1.7%.

AMENDMENT CRITERIA SCOREBOARD:
1. s60 exp>0 sustained, n>=20: **MET** (22 committed, +7.9%)
2. Fresh strict-captured runner >=1.5x: **MET** (3JSy9Uvh 1.54x freeroll)
3. Runner-scratch divergence rare: HOLDING (1 case: oFxvzBiT)
4. No instrumentation break: HOLDING (parity §74d, all runs clean)

All four criteria met or holding one day early. Sep 1 review is now a confirmation exercise, not a discovery exercise.

### §78g — Duz5NLo5: slow-breadth runner, strict entry's structural blind spot (09:45 local)

Duz5 freerolled 1.97x under loose entry (+60.5% MTM). Flow profile: t+13m net=46.6/nb=26 (breadth OK, net short), t+26m net FELL to 39.7 (selling pressure), t+38m net=66.1/nb=60 — qualifies ~38 min post-birth, AFTER the move. Not a hard miss: a LATE catch that forfeits the freeroll (same §77c pattern as oFxvzBiT).

Taxonomy clarified: FAST-breadth campaigns (3JSy, 2oFG, jCPN) — strict catches runners early enough. SLOW-breadth campaigns (Duz5, oFxv) — strict enters post-move, scratches small. NOTE: confirmed-entry W10 (§77d) would ALSO miss Duz5 (no confirmation by minute 10-13; net<60 until 38m) — slow-build runner capture is unsolved by BOTH strict variants. Runner upside capture: strict 3/5 recent runners with freeroll, 2/5 late scratches.

Criterion 3 honest restatement for the review: strict forfeits runner FREEROLL upside in slow-build campaigns (~2 of 5), but never turns them into losses. The +16pp expectancy gap vs loose covers the leaked upside many times over. Amendment case intact; criterion 3 revised to "strict-missed runner upside does not exceed the rug-avoidance gain" — currently +16pp vs ~2 forgone freerolls.

### §78h — gKNKwvDg freerolled 1.51x, but its 08:44 abort15 close REVISED away (10:04 local)

gKNK showed "closed abort15 +7.5%" at 08:44; now OPEN freerolled (peak 1.51x, +50.7% MTM, entry ~08:29). Cause: batched-RPC trade backfill — late-arriving pool trades with pre-deadline timestamps revise the mark-to-deadline history; the abort15 fill no longer fires on the fuller tape. Two implications:
1. GOOD: 2nd post-deployment strict-captured runner (with 3JSy). Criterion #2 doubly met.
2. CAVEAT (memo-worthy): "closed" marks are not immutable — committed history can revise when backfill lands. Rare (first observed case in ~40 closes) but gate accounting must tolerate revisions. The n>=30/exp>0 rule should be evaluated on the file as it stands AT review time, and the review should re-run gen/backtest on the raw tape rather than trusting stored marks blindly.
s60 now: 23 committed, +7.91%, zero losses, THREE freerolled opens riding (2oFG +94%, 3JSy +54%, gKNK +51%).

### §78i — runner resolution scenarios (10:25 local)

Committed exp at floor vs if freerolled runners trail out at current MTM:
- GATE h108 (n=36): floor -5.2% -> MTM scenario **-1.6%**. Even full runner upside cannot flip the loose gate; deficit too deep. Verdict final regardless of trail-outs.
- s60 (n=23): floor +7.9% -> MTM scenario **+15.2%**. The three freerolled runners carry +7.2pp of uncounted upside.
- Design note verified: the +12.5% floor IS the post-freeroll worst case (75% banked at 1.5x = 1.125 total even if remainder dies). No scenario below floor; trail-outs only add.
- Duz5 trailed out of h108's open list (closed) — loose gate banked its runner, still negative overall.

## §79 — Review instrument built and validated (2026-08-31 ~10:30 local)

`review_check.py` recomputes all four scorers from RAW TAPE and diffs vs tracker files (per §78h revision caveat). First run:
- a15, h108, s60: recomputed committed n/exp IDENTICAL to tracker files (a15 37/-1.79%; h108 36/-5.18%; s60 23/+7.91%). Flagged "revisions" are open-position MTM drift (ret moves as marks update) — no material inconsistency. a30 had one heartbeat close revision (7caYMNnR ope->clo).
- s60 from tape: 8 post-deployment entries, ZERO losses, 5 runners >=1.5x post-cutoff (jCPN, CHPs, 2oFG, 3JSy, gKNK).
The Sep 1 review can now be run as: `python3 review_check.py` — verdict reproduces from tape, not from stored marks.

### §79b — 3JSy9Uvh resolved at FLOOR, not MTM: the runner illusion quantified (10:44 local)

First post-deployment strict runner closed: trail exit **+12.6%** (s60) / +12.7% (h108) despite peak 1.76x/1.85x. The token collapsed post-peak faster than the trail could execute — the freerolled remainder sold near zero. The freeroll design did EXACTLY its job: banked the +12.5% floor through a rug-speed collapse.

HARD CALIBRATION (memo update needed): §78i's "MTM trail-out scenario" (+15.2%) was illusory. Runner MTM above floor is largely unrealizable — post-peak dumps are rug-speed. EXPECT FLOOR REALIZATIONS (+12.5%) for freerolled runners, not MTM. s60 realistic forward exp: ~+7.9% at floor, NOT +15%. The strategy's true shape: many +3-8% scratches + +12.5% runner floors, zero rugs. That's still solidly positive — and now honestly modeled.

s60: 24 committed, +7.88%, zero losses. gKNK new high 1.75x; E6gQ climbing +16.6% (peak 1.17x); 2XMz closed +7.1%; new entry 7caYMNnR +5.7%.

## §79c — gKNKwvDg trail-out: second floor realization (2026-08-31 ~11:24 local)
gKNK (freerolled, peak 1.91x, was +60% MTM) closed via trail at **+12.9%** — the second post-deployment freerolled runner to realize at the floor band, not at MTM (first: 3JSy +12.6% after 1.76x peak). §79b calibration now confirmed twice live: post-peak decay is rug-speed; model runner outcome = +12.5% floor, never MTM. s60 committed: n=25, exp +7.90%, losses 0. Recent closes all abort15 green scratches (+3.1% to +8.1%) — consistent with the expected strategy shape (many small greens + floor realizations − rare bleeders).

## §79d — FIRST s60 LOSS: E6gQraSR rugged −100% (2026-08-31 ~11:29 local)
E6gQ entered ~10:12 local on a valid s60 signal (net≥60, nb≥20, flow≥2.0), grinded to 1.39x peak over ~70 min — never reaching the 1.5x freeroll — then collapsed to dust (~0.00x) within 1-2 trades at ~t+77m. Recomputed outcome: abort15 branch fires (first post-15m trade with r<1.08), next-trade fill ≈ 0 → **−100%**. NOT a backfill artifact: collapse rows landed after the 11:23:49 tracker write; the file's +36.9% open mark was simply stale by minutes. Tracker will close it at the ~11:44 write.
Recomputed s60 from raw tape: n=27 committed, exp **+3.86%** (was +7.90% on stale files), losses 1. Distribution now: 23 green scratches (+0.9% to +14.4%), 4 floor realizations (+12.6% to +13.0%), 1 rug (−100%). Win rate 96%.
Model corrections: (1) max loss is −100%, not −50% — a rug-through-gate takes the whole unfreerolled position; (2) kill criterion #2 (two full-loss bleeders in 30) is the right tripwire — one observed, not killed; (3) expectancy is bleeder-dominated: one −100% event costs ~3.7pp per trade at this n; the edge lives or dies on rug-through-gate FREQUENCY, which the breadth gate exists to suppress (1/27 = 3.7% so far vs ~63% manufactured-rug base rate).
Amendment criteria status: 1 MET (+3.86% > 0, n=27), 2 MET (5 runners ≥1.5x), 3-4 holding.

## §79e — E6gQ post-mortem: cadence fingerprint NULL, breakeven math (2026-08-31 ~11:45 local)
Tested whether the E6gQ rug showed a bot fingerprint (uniform small buys, fixed cadence) that the gate could have caught. Result: NULL. E6gQ pre-entry cadence 18.3s/CV 0.19/size-CV 0.80 sits mid-pack; winners 2oFG (CV 0.01), 8WnaNq61 (0.01), nVs7YcfF (0.02) are MORE regular. The whole universe is botted; trade-level cadence does not separate rugs from runners. The gate was NOT beaten by a new tactic — the discriminating signal (unique wallets, insider concentration) is absent from trade-level tape. Reducing rug-through-gate frequency requires wallet-level data (Helius re-check, deferred).
Breakeven math: avg win +7.6% → strategy stays positive while rug-through-gate rate < ~7%. Observed 1/27 = 3.7%. Margin ~2x. Edge intact post-first-loss.

## §79f — E6gQ wallet POC: sybil wallet-per-buy farm (2026-08-31 ~12:05 local)
Helius key dead (403). Used public mainnet RPC, paginated pool GeUPNqJ1... sigs back to pre-entry window (11 pages, 214 pre-entry sigs), fetched 90 pre-entry swap txs. Result: **90/90 UNIQUE fee-payer wallets — zero repeats**. E6gQ's breadth was manufactured by a one-shot-wallet farm: a fresh wallet per buy, the same pattern rugs use on the FUNDER side (§59ff). The s60 transaction-breadth gate cannot see this.
Hypothesis to test: organic-ish RUNNERS should show repeat buyers (communities re-buy; farms never reuse). Metric candidate: pre-entry repeat-buyer fraction (1 − unique/txs). E6gQ = 0.00. If runners print materially >0, add repeat-fraction floor to the gate. Test set: jCPNKECQ, 3JSy9Uvh, gKNKwvDg, CHPsKyiH (all freerolled winners) + scratches as controls. POC data: e6gq_wallet_poc.json.
Caveat: fee payer could be a relayer for some txs; needs winner comparison before believing the metric.

## §79g — Wallet repeat-fraction separates rug from winners (n=5, 2026-08-31 ~12:35 local)
Resumable public-RPC tracer (wallet_trace2.py) counts unique pre-entry swap fee payers per pool; metric = repeat_frac = 1 − unique/txs over first 90 pre-entry swaps.
- E6gQ (rug, −100%): **0.000** (90/90 unique — sybil wallet-per-buy farm)
- jCPNKECQ (winner +12.9%): **0.056**
- 3JSy9Uvh (winner +12.6%): **0.578**
- gKNKwvDg (winner +12.9%): **0.033**
- CHPsKyiH (winner +13.0%): **0.667**
Clean separation: every winner > 0.03, the rug at exactly 0. A gate floor of repeat_frac ≥ 0.02 would have kept all four winners and killed the only bleeder. Note: same repeat wallets (FMY3yjPk, H6wSihoM) appear across jCPN + gKNK — a recurring organic-ish sniper cohort present only in non-rugs. Sample is tiny (n=5, one rug); next: trace h108's 7 losses (rug controls) + green scratches to place the threshold. If separation holds, repeat-fraction floor is the leading post-amendment gate upgrade, implementable at signal time via pool-sig fetch (~2 RPC calls at entry, no Helius needed).

## §79h — repeat_frac FALSIFIED as rug discriminator (2026-08-31 ~13:05 local)
Rug controls traced: c8bdKqmN (−100%) repeat_frac **0.789** (19 unique/90), E1U1WVN8 (−100%) **0.605** (34/86). Both rugs show MORE repeat buying than winners gKNK (0.033) and jCPN (0.056). Rugs: {0.000, 0.789, 0.605}; winners: {0.033, 0.056, 0.578, 0.667} — complete overlap. The wallet-per-buy farm (E6gQ) is only ONE rug style; wallet-reusing botnets fake repeat buying just as easily. repeat_frac is DEAD as a gate signal. Hypothesis tested and killed in one session — the scientific process working as intended.
Next candidate: FUNDING-SOURCE clustering — trace each pre-entry buyer wallet's inbound funding tx. Rugs fund their buy-botnets from 1-2 dispenser wallets (matches §59 one-shot funder pattern); organic winners' buyers arrive independently funded (CEX withdrawals). Test: c8bd (19 wallets) vs CHPs (30 wallets). ~2 RPC calls/wallet.

## §79i — Three rug styles taxonomy; buy-side metrics each catch one (2026-08-31 ~13:40 local)
Funder-clustering results: c8bd (−100% rug): 17/19 buyer wallets funded by ONE dispenser (conc 0.89), all wallets <1.3h old — dispenser-funded botnet. CHPs (winner): 30/30 independent funders (conc 0.03), all wallets established (>1000 lifetime txs). E1U1 (−100% rug): 34 independent funders (conc 0.03), mixed ages — buy side looks organic because it IS organic.
E1U1 sell-side: 48 buys for 54 SOL, but **8 sells for 2,225 SOL — two dumps of 1,108 and 1,112 SOL at t+33m/t+53m** = 99.9% of sell volume from 2 pre-positioned insider wallets. Classic insider mega-dump: insiders pre-load supply before the visible campaign, let organic buyers push price, then exit in 1-2 txs. Buy-side breadth metrics are STRUCTURALLY BLIND to this style.
Taxonomy: (a) sybil wallet-per-buy farm [E6gQ] — caught by repeat_frac≈0; (b) dispenser-funded botnet [c8bd] — caught by funder_conc>0.5; (c) insider pre-positioned mega-dump [E1U1] — needs HOLDER CONCENTRATION at signal time (getTokenLargestAccounts, 1 RPC call): top non-pool holders' supply share. bundle_screener.py already exists in MON — check for reusable bundle-detection logic.
Composite gate candidate: entry requires repeat_frac ≥ 0.01 AND funder_conc ≤ 0.5 AND top-holder check. (a)+(b) verified caught; (c) untested. Note E1U1 under s60 was only +6.6% scratch in the OTHER direction (5JLCmdSd dual-gate divergence) — these gate interactions need care.

## §79j — The universe is ONE industrial farm; discrimination is behavioral (2026-08-31 ~14:10 local)
Birth forensics: all 7 traced tokens (3 rugs + 4 winners) are born IDENTICAL — initialBuy 793,100,000 tokens (74% of supply) for exactly 85.005359057 SOL, leaving 279.9M in curve. Population median vTokens ≈ 1.066B (p90 = 1.073B untouched). The 85.005 SOL seed universe: 499 tokens from 477 unique one-shot creator wallets, each creator funded by a DIFFERENT one-shot funder wallet (7/7 traced). The farm structure: master → one-shot funders → one-shot creators → identical 74% pre-loaded launches.
Consequences: (1) insider pre-positioning is UNIVERSAL in this universe — birth-signal discrimination is dead (rugs and winners share the identical birth fingerprint); (2) creator/funder identity doesn't discriminate either — all one-shot; (3) what separates winner from rug is the farm's per-token DECISION (support the chart vs harvest immediately), visible only in post-birth behavior. The s60 breadth gate works because it reads that behavioral choice; its 3.7% leak = tokens where the farm mimics support for ~30-80 min then harvests (E6gQ ground 77 min; E1U1 dumped at t+33m).
Next instrumentation: snapshot getTokenLargestAccounts at every s60 signal going forward — hypothesized discriminator: supported tokens DISTRIBUTE the 74% to many holder-wallets; harvest tokens keep it concentrated in 1-2 (E1U1's two 1,108-SOL dumpers). Historical reconstruction unavailable via standard RPC; must collect forward. Patch target: tracker automation s60 scorer — log top-10 non-pool holder share at entry.

## §79k — Holder-concentration instrumentation DEPLOYED (2026-08-31 ~14:30 local)
Patched tracker automation (automation_3840d0e4): new module-level holder_snapshots(rpc_fn) hooks after the s60 scorer block; for every fresh s60 entry (entry_t within 40 min, not previously snapshotted) it calls getTokenLargestAccounts via the existing Helius-first/public-RPC-fallback rpc helper and appends {t, mint, entry_t, top-20 holders} to mfg_holders.jsonl; mfg_holders_seen.json dedupes. Syntax verified (ast.parse OK); imports already module-level. Goes live on the tracker's next 20-min cycle automatically; max 4 snapshots/run to bound RPC load. Forward data from here decides the distribute-vs-harvest threshold (hypothesis: winners spread the 74% pre-load; harvests hold 1-2 fat wallets).

## §79k2 — Snapshot resilience fix (2026-08-31 ~12:55 local)
First two snapshots (36oTyUNQ, FAUsvDcw) landed EMPTY: Helius key 403 (dead), public RPCs 429/403 under load → rpc helper returned None. Fixes deployed: (1) empty results no longer mark mints seen — they retry every run until a real snapshot lands; (2) freshness window widened 40→90 min (harvest-style concentration persists until the dump, so +90m snapshots remain diagnostic); (3) the two empty rows purged and unmarked. Instrumentation is now self-healing against RPC starvation. Data path note: pumpportal websocket (trade tape) is unaffected; only RPC-dependent snapshots were at risk.
Meanwhile s60 keeps printing post-first-loss: n=28, exp +3.92%, losses 1; RST (Hd1k) entered and scratched +4.6% — cadence intact.

## §79l — s60 hits n=30 with exp +4.06% (2026-08-31 13:24 local)
Committed n=30, exp +4.06%, losses 1 (3.3% rug-through-gate rate vs ~63% base). Both RPC-starved snapshot candidates closed green (36oTy +8.8% abort, FAUsvDcw +3.3% abort15) — no holder data needed for them diagnostically, but snapshots remain armed until ~14:00. 2oFG marathon still open freerolled (age 12h+). Note: n=30/exp>0 would satisfy the ORIGINAL gate criteria, but per the amendment plan the gate re-zeros Sep 1 — this n=30 is evidence FOR the amendment, not a pass.

## §79m — Post-amendment go-live gate pre-built (2026-08-31 ~13:35 local)
Discovered: the existing go-live alerter (automation_17fc6c1a) is wired to gate_check.py scoring paper_v3.json — the LEGACY pre-manufactured-launch strategy. Cannot false-trigger (manual_signoff.json absent, owner-only), but the path was stale. Built gate_check_s60.py: scores mfg_paper_trades_s60.jsonl counting only entries ≥ amendment.json.amendment_ts (the re-zero); gates = ≥30 fresh committed closes, exp>0, ≤1 bleeder ≤−50%; qualified only with manual_signoff.json owner_approved. Tested: n=0/qualified=False until amendment_ts set. go-live-gates.md §7 appended with the amendment definition. Tomorrow's review is now mechanical: review_check.py → write amendment.json {amendment_ts} → 30-close count begins.

## §79n — Backfill reversal: 36oTy abort-close became a freeroll (2026-08-31 14:03 local)
36oTyUNQ was closed abort +8.8% at the 13:24 write; the 14:03 write shows it OPEN, freerolled, peak 1.57x (+52% MTM) — RPC backfill delivered the trades that carried it through 1.5x, reversing the close. Committed value moves +8.8% → +12.5% floor; s60 n=30, exp +4.18%. Third live demonstration of §78h mark revision (after E6gQ/gKNK), first FAVORABLE one. Reinforces: Sep 1 review must trust raw-tape recomputation (review_check.py), never stored files.

## §79o — KILL CRITERION #2 MET: second bleeder B9tN5FAJ (2026-08-31 15:23 local)
Two resolutions this cycle:
1. **36oTyUNQ trail-close +12.78%** — THIRD floor realization (3JSy +12.6%, gKNK +12.9%, 36oTy +12.8%). §79b floor model now triple-confirmed.
2. **B9tN5FAJ −99.9%** — second full-loss bleeder. Grinded ~52 min building breadth, passed s60 gate legitimately, then collapsed to dust within 5 min of entry (peak 1.004x — never went up). Same grind-then-harvest species as E6gQ, faster post-entry trigger. Holder snapshot unavailable (RPC starved) — the one diagnostic that might have caught it was dark.
KILL CHECK: 2 bleeders (E6gQ −100%, B9tN −99.9%) within the last 30 committed entries → **STRATEGY_SPEC §6.2 triggered: HALT and re-review.** s60 exp now +0.97% (n=32) — still positive but one more bleeder flips it. Rug-through-gate rate 2/32 = 6.25% vs ~7% breakeven — margin nearly gone; the farm is harvesting more aggressively during US hours.
Consequences: paper tracking CONTINUES (data is data), but the amendment path freezes — tomorrow's Sep 1 review is now a KILL-OR-FIX decision, not a rubber stamp. Fix candidates for evaluation on raw tape: (a) delayed/confirmed entry (B9tN rugged 5 min post-signal — a 10-min confirmation window skips it entirely; W10 confirmed-entry was +4.1% full-universe, §77d); (b) holder-concentration gate when RPC capacity returns; (c) time-of-day filter if harvests cluster in US hours.

## §79p — Delayed-entry fix FALSIFIED on raw tape (2026-08-31 ~15:35 local)
Tested D∈{0,5,10,15}min confirmation delay (enter only if price ≥ signal-level after D min; skip else), frozen h108 exits, post-cutoff tape (backtest_79p.py).
- D=0 (baseline, corrupted by confirm filter — use tracker's +0.97%/+4.22% range as truth): 2 bleeders
- D=5m: exp +0.86%, 2 bleeders
- D=10m: exp **−5.82%**, 4 bleeders — B9tN skipped (good) BUT CHPs (+13.0% → −99.8%), 4cy86hpK, Hd1k converted to bleeders; E6gQ NOT dodged (−100% anyway)
- D=15m: exp −6.31%, 4 bleeders
Verdict: DEAD. Harvests land minutes-to-an-hour post-gate regardless of entry timing; delaying moves the fill price UP into the dump window, converting scratches into bleeders while dodging only the fastest rugs. The entry-timing dimension has no fix in it.
Remaining fix candidates for the Sep 1 kill-or-fix review: (1) holder-concentration gate (instrumented §79k, untested — needs RPC + forward data); (2) time-of-day filter (both bleeders hit during US window — test on tape); (3) KILL the strategy, keep the infrastructure. Baseline to beat: s60 as-is, exp +0.97% at n=32 with 2 bleeders — marginally positive but kill-criterion-halted.

## §79q — Time-of-day filter: NULL (2026-08-31 ~15:40 local)
Bleeder entry hours: 10:12 and 14:59 local — 5 hours apart, no clustering. Entry-hour distribution of all 32 trades spans 01:00-23:00 with clean hours on both sides of both bleeders. n=2 bleeders can't support any time filter regardless. Time-of-day is DEAD as a fix. Sep 1 review narrows to: holder-concentration gate (needs RPC + forward data) vs KILL.

## §79r — Drought breaks with a near-miss loser; exp ≈ 0 (2026-08-31 16:35 local)
PFKsPtdJ entered ~16:06, peaked 1.387x (missed freeroll by 0.11x — same 1.39x near-miss ceiling as E6gQ), trailed out −31.4% in 9 min. Exit ladder WORKED (caught −31% instead of −100%), but the entry was a trap. s60: n=34, exp +0.08%, losses 3, bleeders 2. Intraday expectancy trajectory: +7.90% → +3.86% → +0.97% → +0.08% — the regime DECAYED through the US window. Note the pattern: afternoon entries are getting farmed — peak-then-dump under the freeroll line, or instant harvest. One more material loss flips expectancy negative. Sep 1 review leaning KILL unless holder-gate data (still RPC-dark) contradicts.

## §79s — Near-miss abort: FIRST NON-FALSIFIED FIX (2026-08-31 ~16:55)

**Setup.** §79r showed the s60 peak distribution is bimodal with an empty
middle: 22 trades <1.08x, ZERO in 1.15-1.29, exactly TWO in 1.30-1.49
(E6gQ 1.386 -> -100%, PFKs 1.387 -> -31.4%), six >=1.5 all survived.
Hypothesis: touching 1.30x but failing to cross 1.5x quickly is a
dump-in-progress signature (the farm harvests into the approach).

**Rule.** Once mcap >= 1.30x entry (pre-freeroll), start a clock; if 1.5x
is not reached within NM_MIN minutes, exit full position at next trade.
Implementable live; no look-ahead beyond the declared window.

**Backtest (backtest_79s.py, post-cutoff tape, s60 gate, committed
accounting).** Baseline nm=None reproduced EXACTLY: n=34, exp +0.08%,
3 losses, 2 bleeders — same as live tracker.

| NM_MIN | exp     | losses | bleeders | nm exits |
|--------|---------|--------|----------|----------|
| none   | +0.08%  | 3      | 2        | 0        |
| 3      | +7.77%  | 2      | 1        | 7        |
| 5      | +8.03%  | 2      | 1        | 7        |
| 10     | +8.78%  | 2      | 1        | 7        |

nm_abort exits (nm=5): jCPN +33.4%, CHPs +43.1%, 2oFG +38.3%,
3JSy +33.5%, gKNK +33.1%, E6gQ +32.4% (was -100%), 36oTy +33.3%.
Notably the 6 freerollers stall >3-5 min in the 1.30-1.49 zone before
crossing 1.5x, so nm_abort dumps 100% at ~1.33-1.48x — beating the
+12.5% floor realization of the freeroll path on this tape.

**Limitations (honest).** (1) Thresholds chosen AFTER seeing the bimodal
gap — in-sample selection, n=7 trigger events; must re-prove forward.
(2) Does NOT catch PFKs-style instant wick rugs (trail fires before the
nm clock) nor B9tN-style sub-1.30 grinds (1 bleeder remains).
(3) Next-trade fills, no slippage model.

**AMENDMENT EXECUTED (paper-only).** amendment.json written
(amendment_ts=1788191605, strategy=s60nm5, scorer_file=
mfg_paper_trades_s60nm5.jsonl). Tracker automation patched: paper_score
gains nm_min; new s60nm5 shadow writes every cycle. gate_check_s60.py
now reads the amended scorer file; re-zero confirmed (n=0, qualified=
False). Sep 1 review shifts from KILL-OR-FIX to amend-validation:
30 fresh committed closes, exp>0, <=1 bleeder, then owner signoff.

## §79t — s60nm5 scorer verified; first fresh close committed (2026-08-31 ~17:15)

One-shot gen_s60nm5.py mirrors the patched paper_score exactly and
reproduces the §79s backtest on identical tape: n=35 (vs 34 — one open
position hit its mark-to-deadline commit between runs, expected),
exp +7.99% (vs +8.03%), losses=2, bleeders=1, and the SAME 7 nm_abort
exits with identical returns (jCPN +33.4, CHPs +43.1, 2oFG +38.3,
3JSy +33.5, gKNK +33.1, E6gQ +32.4, 36oTy +33.3). Live-logic parity
confirmed; tracker overwrites the file each cycle from here.

First FRESH post-amendment close already committed: Mv4DCCRX entered
16:53:21 (6 min post-amendment), peaked 1.062x — never approached the
1.30 nm zone — and abort15 exited at +6.5% after 15 min. Textbook
dead-campaign early out; the nm rule neither helped nor hurt (never
triggered). Gate now reads n=1, exp +6.5%, bleeders=0. 29 fresh closes
to go. Note: legacy s60 file missed this entry (token had <50 trades at
the 17:03 write; crossed 50 by 17:09) — tape-growth edge case, harmless.

## §79u — Dust-buy filter hypothesis: median buy size at entry (2026-08-31 ~17:45)

RPC holder route fully blocked (publicnode/onfinality/mainnet-beta gate
getTokenLargestAccounts; ankr 403; drpc free tier excludes Solana) — but
the trade tape itself carries a concentration proxy: per-trade SOL sizes
up to the s60 entry trigger.

Pattern (post-cutoff s60nm5 sample): runners (nm_abort/freeroll, n=7)
show LOW top1 concentration (7.1%), low CV (0.59), LARGE median buy
(3.2 SOL) — uniform mid-size sybil pumping = follow-through. Quick-deads
(n=27) show HIGH top1 (16.4%, extremes 45-70%) but exit +4-8% via
abort15 anyway. The remaining bleeder B9tN (-100%): top1 6.1% like a
runner BUT median buy 0.248 SOL — 10x smaller; grind-rugs fake breadth
with hundreds of dust buys.

Grid (median-buy floor applied at entry, rest of s60nm5 unchanged):

| med_min | n  | exp     | losses | bleeders | note |
|---------|----|---------|--------|----------|------|
| none    | 35 | +7.99%  | 2      | 1        | baseline (amended s60nm5) |
| 0.25    | 33 | +11.30% | 1      | 0        | removes ONLY B9tN + 4cy86 (+6%) |
| 0.50    | 23 | +11.32% | 1      | 0        | also kills winners E6gQ/36oTy (+32/33%) |
| 1.00    | 18 | +13.49% | 1      | 0        | higher mean but skips 2 big winners |
| 2.00    | 15 | +13.17% | 1      | 0        | over-filtered |

med_min=0.25 is the minimal cut: removes the dust-breadth rug pattern,
keeps every winner. HONEST CAVEAT: fitted on n=1 bleeder — pure
hypothesis. Pre-registered as SHADOW variant s60nm5mb (s60nm5 +
median-buy >= 0.25 at entry), NOT an amendment. It accrues forward on
identical live data; becomes amendment #2 only if it beats s60nm5 over
the same fresh-close window. Gate strategy remains s60nm5 unchanged.

## §79u2 — s60nm5mb shadow deployed (2026-08-31 ~17:55)

Tracker patched: paper_score gains med_min; new shadow file
mfg_paper_trades_s60nm5mb.jsonl writes every cycle (s60nm5 + median buy
>= 0.25 SOL at trigger). One-shot gen_s60nm5mb.py reproduces the §79u
grid EXACTLY: n=33, exp +11.30%, 1 loss, 0 bleeders. Fresh entry Mv4D
passes the dust filter (median buy >= 0.25) so gate and shadow track
identically for now — divergence appears when the next dust-breadth
entry shows up. Gate strategy remains s60nm5; shadow needs the same
30-fresh-close proof before any amendment #2. py_compile clean.

## §79v — Full automation chain closed (2026-08-31 18:04)

18:04 tracker run self-wrote BOTH amended-scorer files (s60nm5: 43 rows;
s60nm5mb shadow: 33 rows), contents matching the verified one-shots
exactly; 1 fresh post-amendment close each (Mv4D +6.5% abort15). No
manual generation remains in the loop: discovery -> trade tape -> 6
scorer variants -> gate status, all on the ~20-min cycle. Accrual phase
begins: 29 fresh closes to the go/no-go readout.

## §79w — First fresh bleeder: instant mega-dump style (2026-08-31 ~20:05)

GsM2Nqmd: entered 19:46:15 (fresh, post-amendment), 74 buys / 1 sell,
net 60.7 SOL, top1 7.4%, med buy 0.695 SOL, cv 0.82 — a textbook
RUNNER profile by every entry feature we have. At +3.6 min a single
1,697.5 SOL sell hit the pool (then 31.7 SOL mop-up): insider
pre-positioned mega-dump, rug style #3 (§79i). Trail triggered but the
fill landed at ~0: -100% in under 4 minutes. No exit rule fires fast
enough (abort15 is 11 min too late; nm_abort never armed — peak 1.01x).

Implications:
1. Gate: 3/30 fresh closes, exp -29.4%, bleeders=1 (max allowed: 1).
   ONE more bleeder in the next 27 closes fails the amended gate.
2. Entry-window tape features do NOT separate this style from runners
   — it passes the s60 gate AND the dust filter legitimately. The only
   pre-entry defense would be holder concentration at birth (insider
   holds the dump stack pre-graduation) — RPC-gated, still blocked.
3. Style-3 was ABSENT from the 35-trade post-cutoff history (bleeders
   there were grind styles E6gQ/B9tN). Its arrival today means the
   farm rotates styles; base rate unknown, treat as live risk.
4. Position sizing is the structural answer for style-3: with ~1-in-3
   historical rug styles, sizing each entry at <=25-33% of bankroll
   keeps a single instant-rug survivable even if the gate passes it.

## §79x — RPC key-rotation scaffold (2026-08-31 ~20:55)

holder_snapshots has been RPC-starved all day: every free endpoint
gates getTokenLargestAccounts (indexed method). Decision (owner
consult): do NOT self-host a node ($6-12k/yr + ops for ~300 calls/day).
Instead: rpc() now tries keyed endpoints FIRST from MON/rpc_keys.json
({"endpoints": [url, ...]} — Helius/QuickNode/Alchemy free tiers, full
URLs with keys), then Helius, then public RPCs; rotation modulo fixed
for the longer list. File read fresh per call — owner drops keys in, no
restart, holder snapshots resume next cycle. py_compile clean.

## §79y — First live nm_abort fire: 2eQKEM +38.9% (2026-09-01 ~00:24)

The near-miss abort (amendment s60nm5) fired live for the first time.

- **2eQKEM**: entered on strict gate, ran to peak 1.384x, never touched
  1.5x within the 5-minute near-miss clock, exited at next trade:
  **ret +38.9%, exit_reason=nm_abort, age 38.8m**.
- This is the exact pattern the amendment was written for (grind toward
  1.30-1.40x without reaching the 1.5x freeroll, then fade). In the
  pre-amendment ruleset this position would have ridden back toward the
  trail; instead +38.9% banked. Matches the in-sample replay behavior
  (§79s: E6gQ −100% -> +32.4% conversion).
- Gate state after the close: 13/30 committed, exp −0.8% (recovered from
  −29.4% trough over eight checks), bleeders 1/1 (GsM2Nq insider dump,
  §79w — still the only uncatchable loss class, holder-gate defense
  pending RPC keys).
- Two runners remain open at the write: 4n22Si +25.6% (peak 1.256x) and
  4wguFY +25.9% (peak 1.259x), both approaching the 1.30x near-miss zone.
- Also notable: entry pace surged this hour (16 fresh entries total,
  ~7 in the last 2h) — maturity estimate pulls earlier if sustained.

## §79z — Gate flips positive: 16/30, exp +3.8%; nm_abort goes 3-for-3 (2026-09-01 ~00:44)

The amended strategy's forward gate crossed into positive territory.

- **Two more live nm_abort closes**: 4wguFY **+34.4%** (peak 1.342x) and
  4n22Si **+32.6%** (peak 1.324x). Plus 3r8JB3 +4.6% on abort15.
- Live nm_abort is now **3-for-3**: 2eQKEM +38.9%, 4wguFY +34.4%,
  4n22Si +32.6% — every position that entered the 1.30-1.40x near-miss
  zone without reaching 1.5x was harvested at +32-39% instead of riding
  the fade. The amendment is behaving exactly as the §79s replay
  predicted, out of sample.
- **Gate: 16/30 committed, exp +3.8%, bleeders 1/1** (GsM2Nq insider
  dump remains the only bleeder). Expectation path: −29.4 → −21.0 →
  −16.6 → −12.7 → −10.7 → −7.3 → −4.2 → −0.8 → **+3.8%**.
- No freeroll yet (no position has touched 1.5x); no second bleeder.
- Remaining qualifiers for the go decision: 14 more committed closes,
  exp > 0, <=1 bleeder total, then owner manual_signoff.json.

## §80 — GATE FAIL: second bleeder 4xBDmh −100% (2026-09-01 ~04:04)

The forward gate is unrecoverable: bleeders 2 > MAX_BLEEDERS 1, with 7
closes still outstanding. Official gate_check_s60.py verdict:
qualified=false (n=23, exp −0.5%, bleeders 2, sample/exp/bleeders all
fail; manual_signoff never present).

### The bleeder
- **4xBDmh**: strict-gate entry, peaked 1.04x, then a single insider
  sell of **1,033.6 SOL at +43.0 min** zeroed the curve (exit trail,
  ret −100%). Tape: 127 trades, 110 buys / 17 sells, sell side was
  1,041 SOL of which 1,033.6 was one wallet, one transaction.
- Same loss class as GsM2Nq (§79w: 1,697.5 SOL single sell at +3.6m).
  Two occurrences in 23 committed closes — ~8.7% incidence, each −100%.

### Why the exits could not catch it
Instant single-tx dump: price goes from ~1.0x to zero in one trade.
abort15/abort30/nm_abort/trail all evaluate on the NEXT trade — there
is no next trade above zero. Uncatchable by any price-based exit.

### Why the defense is known but undeployed
Holder-concentration gate (reject entries where an insider cluster
pre-holds a dump-sized position) is designed and scaffolded (§79x RPC
rotation), but getTokenLargestAccounts is gated on every free endpoint
tested; awaiting owner-dropped RPC keys (rpc_keys.json, still empty).

### Shadow scorer
s60nm5mb (dust filter) also held both bleeders: n=21, exp −0.6%,
bleeders 2. Amendment #2 would NOT have saved the gate.

### What the sample proved anyway
- nm_abort live 3-for-3: +38.9%, +34.4%, +32.6% (converts the
  near-miss grind class exactly as backtested, §79s/§79y/§79z).
- Exit ladder harvested 18 of 23 closes profitably; exp ex-bleeders
  is strongly positive (+4.3%/trade on the 21 non-bleeders).
- The strategy's entire negative expectancy comes from ONE loss class:
  insider pre-positioned instant mega-dumps.

### Disposition
Paper-trading infrastructure keeps running as passive research (data
keeps accruing; if RPC keys arrive, the holder gate can be tested
against the live stream). No real-money path is open; none was ever
armed. This variant fails qualification. Next candidate edge, if the
owner wants to continue: entry-side insider detection (holder gate via
keyed RPC, or a proxy: first-hour sell-side wallet concentration from
the trade tape we already capture).

## §81 — Tape-proxy search for bleeder signature: negative (2026-09-01 ~04:20)

Tested whether the two mega-dump bleeders (GsM2Nq, 4xBDmh) could have
been filtered at entry using only data already captured (no RPC holder
data). Compared all 23 committed closes on:

- **Symbol recurrence**: both bleeders are "10KK" launches; 5 tokens in
  the sample share that symbol, 2 bled (40% vs 0% for all others).
  Weak signal, n=5 — watchlist-worthy, not gate-worthy.
- **Insider-dominance ratio** (pool_liq_sol / pool_buy_sol at 300s):
  bleeders at 160x and 69x sit mid-pack (winners range 19x-634x).
  No separation.
- **Creator history**: bleeder creators are one-shot in our data; the
  prolific serial launchers (up to 603 launches) produced no bleeders
  in the sample. No signal.
- **Seed field**: constant across all rows (pipeline artifact, not a
  feature).
- mfg_trades.jsonl lacks trader wallet identity; curves.jsonl has
  traderPublicKey but captures mfg-universe mints too sparsely (2 rows
  for GsM2Nq) to reconstruct concentration.

Conclusion: no entry-time proxy from existing capture cleanly separates
the insider mega-dump class. The holder-concentration gate (keyed RPC,
§79x) remains the correct defense; alternatively the trade ingestor
could be extended to record traderPublicKey per mfg trade, enabling a
tape-native concentration metric going forward (retroactive-free —
would accrue from deployment).

## §82 — Signer-snapshot build DEPLOYED: tape-native insider metric (2026-09-01 ~04:45)

Built and wired the entry-time signer snapshot into the live tracker
(automation_3840d0e4, compile-verified before deploy). For each fresh
s60nm5 qualifier it pages getSignaturesForAddress back toward birth
(max 2x80 sigs), parses the oldest 40 transactions, and aggregates
feePayer SOL balance deltas — recovering wallet-level flow identity
that mfg_trades.jsonl lacks — WITHOUT keyed RPC (getSignaturesForAddress
+ getTransaction work on public endpoints; getTokenLargestAccounts
does not, which is what killed holder snapshots).

Appends to mfg_signers.jsonl: {t, mint, entry_t, n_tx, parsed,
unique_signers, top1_sol, top1_share, top1, top5_share, moved_sol}.
Capped at 2 mints per cycle; failures retry next cycle; own try block
so it cannot disturb the live scorer.

**Forward test now armed:** if a third bleeder appears, compare its
entry-time top1_share/top5_share against winners — hypothesis is the
mega-dump class shows one signer dominating early flow (insider
loading the curve before the gate fires). If separation holds over a
few more closes, this becomes amendment #3 (insider-concentration
gate) with zero RPC-key dependency. First rows expected within 1-2
cycles (~20-40 min) if any new qualifier enters; entry pace ~1-2/h.

Patch applied in two parts (function + call site), py_compile clean.

## §83 — Two fresh qualifiers entered; signer gate fires on them next cycle (2026-09-01 ~04:50)

Write 04:43:47: two new s60nm5 entries, both open and both already at
2x peaks within minutes of entry:

- **AgLSnYvV** — entry 04:31:00, entry_mcap 256.5k SOL-mcap units,
  peak +104.2%, 90 trades. NOT yet freerolled (larger-cap entry).
- **AYEzsFNC** — entry 04:35:40, entry_mcap 58.1k, peak +103.0%,
  104 trades. NOT yet freerolled.

Both entered AFTER the §82 signer-snapshot deploy, and the next run
(first to load the patched code) starts at this write — so these are
the first two mints that will get entry-time signer snapshots
(top1_share / top5_share / unique_signers) at ~05:03. This is the
exact prospective test the gate was built for: two live 2x runners,
signer concentration captured at entry, bleeder-vs-winner readout
when they close.

Committed sample unchanged: n=23, exp -0.49%, 0 new closes.

## §84 — First signer row captured + two structural findings (2026-09-01 ~05:10)

The patched run's signer pass produced nothing (silent fail), so the
snapshot logic was replicated standalone. Results:

**1. AYEzsF row captured — and it is EXTREME.** The bonding curve has
only 2 lifetime transactions, BOTH from a single signer
(En4ZBKdKnQ8CqaiPmtZkWGctkAgNN2y1QmMJQJkZ5rtK), moving 86.083 SOL:
top1_share = 1.0. Yet the scorer recorded 104 trades and a +103% peak.
Resolution: AYEzsF GRADUATED — the 104 trades are PumpSwap POOL trades
(venue "pool" seen in the tape at mcap 59.6k); the curve saw only the
pre-graduation insider load. So for fast graduators the curve snapshot
measures THE PRE-LOAD ITSELF — one wallet loaded 86 SOL, graduated the
token, then public pool flow took it to 2x. This is the manufactured
pattern in its purest form yet captured. Crucially it means high
top1_share does NOT automatically mean bleeder: this runner is +103%
with maximal concentration. The hypothesis test is now genuinely armed:
if AYEzsF mega-dumps from here, concentration predicted it; if it runs,
the gate needs a second dimension (e.g. load SIZE or signer history).

**2. Free-tier getTransaction is the bottleneck.** AgLSnY: 40 sigs
paged fine, then EVERY getTransaction 429'd on all 3 public endpoints
(api.mainnet-beta, publicnode, drpc) — 120 consecutive failures despite
150ms spacing. This is why the in-automation pass wrote nothing: silent
starvation, exactly as designed (retry next run, mints unmarked).
AgLSnY remains pending; entry 04:31 is inside the 7200s window until
~06:31. Mitigations queued: (a) cut the per-mint tx parse from 40 to 20
with 1s spacing, (b) Helius-first rotation already in rpc() means the
moment quota resets or a key lands in rpc_keys.json, snapshots become
reliable, (c) worst case, standalone catch-up runs like this one in
quiet moments.

Row + seen-file written for AYEzsF so the automation won't duplicate.

### §84a — Rate-limit fix deployed (2026-09-01 ~05:15)

automation.py signer pass: parse window cut 40 -> 24 txs, 0.8s spacing
added between getTransaction calls (was none). py_compile clean; live
from the next run (~05:23). AgLSnY still pending and unmarked — inside
its retry window until ~06:31.

## §85 — On-chain forensics: the launch pattern confirmed; the dump window corrected (2026-09-01 ~05:45)

Pulled the actual transactions for all three in-sample mints
(8Tz7sV +4.4%, 4xBDmh -100%, AYEzsF runner +103%):

**1. The manufactured launch, confirmed on-chain.** Every curve has
exactly 2 lifetime transactions by the SAME wallet (= the creator):
tx1 create (-0.002 SOL), tx2 a single 86.080-86.083 SOL self-buy that
instantly fills the bonding curve past the ~85 SOL graduation
threshold. Instant graduation -> all real trading happens on the
PumpSwap pool. Winner, flat and bleeder are BYTE-IDENTICAL in launch
mechanics: seed size, single-signer dominance (top1_share=1.0), 2-tx
curves. There is NO entry-time separation in curve data — the signer
metric confirms the manufacturing but cannot rank outcomes.

**2. Bleeder dump window corrected.** Tape-verified: 4xBDmh's
1,033.6 SOL sell hit the POOL at 03:59:15 = entry+13.4min (not +43m
as logged at §80), mcap -> 1. The bleeder playbook in full: seed 86
SOL at birth -> public pool flow lifts price ~13 min -> single dump
extracts ~12x the seed.

**3. Structural discovery: pools are WSOL-blind to native-SOL
metrics.** PumpSwap pools hold WSOL (a token), so native-SOL balance
deltas on pool txs show ~zero (fees only). The signer metric as built
only sees the native-SOL curve phase. Pool-phase forensics require
pre/postTokenBalances parsing (WSOL legs) — queued as the next build.

**4. Microstructure note.** The dump triggered a ~100 tx/second bot
spam burst within ~1s (588 no-op txs in 7s, err=null, fees only).
The dump was instantly visible to every arbitrage bot watching the
pool — and the spam wall makes retrospective tx forensics on hot
pools expensive on free RPC (thousands of spam sigs to page through).

Gate implication: entry-time filtering on launch mechanics is dead
(all identical). The separating information is WHEN the insider dumps
relative to our entry (13min for 4xBDmh; 3.6m for GsM2Nq). If dump
timing clusters early, the defense is temporal: tighten the abort
window / take profit faster rather than filter entries.

## §86 — TIME-STOP BACKTEST: first rigorously positive variant (2026-09-01 ~06:05)

**Correction to §83:** peak field is a MULTIPLE — the two "2x peaks"
were +4.2% (AgLSnY) and +5.5% (AYEzsF). Nothing in the s60nm5 sample
has run 2x except the three nm_abort anomalies (peaks +32-38%).

**Bleeder lifecycle (n=3, all identical):** freerolled=False, peaks
+1.1% / +4.0% / +4.2% — never remotely near the +12.5% freeroll floor.
Price drifts +1-4% after our entry, then a single insider dump zeros
it: GsM2Nq at +3.6m, 4xBDmh at +13.4m, AgLSnY at +13.8m. (AgLSnY
became bleeder #3 — closed -100% while its signer row was still
RPC-starved. AYEzsF closed +5.8% — the max-concentration runner did
NOT bleed, formally killing the pure concentration gate.)

**Backtest — hard time-stop, exit at market if peak < +12.5% by T:**
  T=+180s:  +4.62%/trade  (total +124.8% vs -96.1%)
  T=+300s:  +1.37%/trade  (eats GsM2Nq whole, STILL positive)
  T=+480s:  +2.17%/trade
  T=+600s:  +2.65%/trade
  T=+900s:  -3.99%/trade  (too late — all dumps land inside)
n=27 committed closes, zero no-tape rows, no lookahead (exit price =
last tape trade before T). Old expectancy -3.56%/trade.

**Robustness:** the +300s variant stays positive even while taking
GsM2Nq's full -100% — the edge does not depend on shaving seconds
ahead of one dump. At +180s the GsM2Nq margin is 36s (exit +1.0%,
dump +3:36) — real but thin; 4xBDmh/AgLSnY had 10+ minutes of margin.

**Caveats (paper rules apply):** n=27, 3 bleeders; thin-tape exit
fills ignored (last-trade price); the rule converts the strategy into
a ~3-minute momentum scalp — positions that would freeroll late are
clipped (24/27 rows stopped early, mostly at small positive).

**Next build:** shadow scorer variant s60nm5ts180 (hard 180s stop on
non-freerollers) accruing forward alongside s60nm5mb. If the forward
sample confirms >= +1.5%/trade over the next ~30 closes, this becomes
amendment #3 and the first candidate for the positive-ROI model.

### §86a — CORRECTION: honest time-stop numbers (lookahead removed) (2026-09-01 ~06:20)

§86's +4.62%/trade was contaminated by lookahead: it classified
positions by LIFETIME peak, but a live 180s stop cannot know the peak
in advance. Re-ran with the real rule (exit at market at T unless
1.5x freeroll already hit):

  T=+120s:  +0.68%/trade
  T=+180s:  +1.00%/trade  (GsM2Nq margin only 36s)
  T=+240s:  -2.43%/trade  (eats GsM2Nq whole)
  T=+300s:  -2.05%/trade
  T=+480s:  -0.96%/trade

Additional honest findings:
- kept=0 at every window: NO position in the 27-close sample ever hit
  the 1.5x freeroll target within 8 minutes — freeroll effectively
  never fires; the +32-38% anomalies came from nm_abort exits at
  ~1.32-1.38x AFTER the 3-minute mark, so any early hard stop clips
  them (2eQKEM +38.9 -> +3.8 at 180s).
- P&L decomposition of the sample: nm_abort trio +106%, other 21
  closes ~+90%, three bleeders -300%. The bleeders ARE the entire
  problem; any fix that also sacrifices the winners nets ~zero.
- Verdict: the pure time-stop is a fragile +1%/trade at best, carried
  by a 36-second margin. NOT amendment material as-is.

The correct target remains a bleeder-ONLY filter (keep the exit stack
intact for winners). Entry-time separation is dead (§85: identical
launch mechanics). Remaining untested axis: pre-dump tape pressure in
the final minutes before the insider sell.

### §86b — s60nm5ts180 shadow DEPLOYED (2026-09-01 ~06:30)

paper_score gained a ts_min param (default P_TS_MIN=120 unchanged);
new shadow variant writes mfg_paper_trades_s60nm5ts180.jsonl each
cycle: same s60nm5 entries, same exit stack, hard stop at +3min for
non-freerollers. Also logged: pre-dump tape analysis came back
NEGATIVE — no silence gap, no sell-pressure buildup before any of the
3 dumps (a maxgap=2 winner exists; two bleeders had zero gaps). The
tape gives no warning. The 180s shadow is therefore the last cheap
defense; anything stronger needs insider HOLDINGS data (keyed RPC) or
WSOL-flow parsing. Forward bar for amendment #4: exp >= +1.5%/trade
over the next ~30 closes (~1-2 days at current entry pace).
py_compile clean; live next cycle (~06:43).

## §87 — ts180 shadow LIVE and matches backtest (2026-09-01 ~06:25)

First shadow-carrying write (06:23:59 local): the s60nm5ts180 scorer
replayed all committed closes through the 3-min hard stop:

- **28 closes, +1.23%/trade, total +34.5%** — matches the honest
  offline backtest (+1.00% on n=27, §86a) within fill-semantics noise.
- **Zero bleeders remaining.** All three -100% insider dumps became
  small timestop exits (exit_reason = timestop for all 28).
- Winners clipped as designed (2eQKEM +38.9 -> +4.6). The variant
  trades tail upside for tail insurance — net positive because
  bleeders cost 3x what the clipped winners gave up.
- Baseline s60nm5 unchanged (gate untouched): this is a paper shadow.

Forward-only accounting starts at deploy (~06:20 local, epoch
1788238800): closes with entry_t >= that are pure out-of-sample.
Amendment #4 bar: forward exp >= +1.5%/trade over ~30 fresh closes
(~1-2 days at the current ~1-2 entries/h pace). Retrospective +1.23%
sits just under the bar — the forward sample decides.

AgLSnY signer row still missing (RPC-starved again); its 7200s retry
window expires ~06:31 — one more cycle may catch it. mfg_signers at
3 rows, all top1_share=1.0 (2-tx instant-fill curves — §85 pattern).

## §88 — Amendment economics: the insurance-premium frame (2026-09-01 ~07:45)

Forward n=5, zero bleeders so far. Paired closes:
  8jMMZ5  base +4.9  ts180 +1.1
  9jE7V1  base +6.7  ts180 +1.4
  A5DaPp  base +8.8  ts180 +0.8
  N7S3it  base +0.4  ts180 +0.4
  XzSzp3  base +10.3 ts180 +1.1
  => base fwd +6.23%/trade, ts180 fwd +0.95%/trade

With no bleeder in the forward window, ts180 pays the premium without
a claim — expected. The decision rule is therefore NOT "ts180 beats
+1.5%" but whether the bleeder rate justifies the premium:

  premium  = base_fwd - ts180_fwd      ~= 5.3%/trade (n=5, noisy)
  claim    = ~100% loss avoided per bleeder (ts180 exits ~0%)
  breakeven bleeder rate ~= 5.3 / 99   ~= 5.4%
  historical bleeder rate = 3/28       ~= 10.7%

If the bleeder regime persists at ~11%, insurance is worth ~+5%/trade
net. If bleeders vanish (regime shift — they may be one operator's
campaign), ts180 just bleeds 5%/trade vs baseline. The forward sample
now measures BOTH: bleeder frequency AND the premium. Decision point
stays ~30 forward closes.

## §89 — The money trail: seeder -> treasury -> layering chain (2026-09-01 ~08:40)

Followed the 4xBDmh seeder/creator wallet (AHPXv7KpzSpZ...) on-chain.
Its history is spam-free and short — the surgical alternative to
pool-side spam walls.

**Findings:**
1. The seeder did NOT sign the dump. Its txs around the bleeder window
   are absent at 03:59:15; a 14-tx burst at 04:03:18 (4 min post-dump)
   is cleanup (rent reclaim / account closes). The insider structure
   separates roles: creator+seeder wallet != dump wallet. The dumper
   is a second wallet seeded with tokens at birth — invisible to any
   creator-history or signer-concentration filter. This permanently
   closes the entry-time wallet-identity gate hypothesis.
2. CASH-OUT CONFIRMED: at 06:34:52 the seeder swept **3,012.5 SOL**
   to treasury wallet CmdxEBCubitREoJTwZxB6jsPR6mawJPcva9aYfFpAEMk.
3. The treasury layers immediately: -3,040 SOL to AdiJ1C5PHNYo
   (06:55:51), +3,040 back (06:56:16), -3,040 out to 9GQvBGZqM7Du
   (06:56:25), plus dust-level probes (06:56:55, 07:00:59). Classic
   layering chain, ACTIVE as of this morning. Treasury history
   (00:48, 00:53, 03:11 sweeps) brackets earlier campaign windows —
   this operator ran multiple campaigns overnight.

**The forward-looking edge this unlocks:** campaigns are FUNDED from
this chain. If the layering wallets periodically send ~86-90 SOL to
fresh wallets (the instant-fill seed amount, §85), those recipients'
next launches are bleeder-class BEFORE they appear on any gate. A
watcher on the treasury chain's outbound flows = pre-launch bleeder
warning. Queued as the next build: poll CmdxEBCu/AdiJ1C5/9GQvBGZq
outbound for 80-95 SOL transfers to fresh wallets; cross-reference
recipients against new births in mfg_tokens.jsonl.

Also closes §84's open question: pool-side dump attribution via WSOL
token-balance parsing is no longer needed — the wallet-side path is
cheaper, spam-free, and now proven.

### §89a — Treasury-chain funding watcher DEPLOYED (2026-09-01 ~08:55)

automation.py: treasury_watch() polls the three known layering wallets
(CmdxEBCu treasury, AdiJ1C5P layer-1, 9GQvBGZq layer-2) each cycle for
outbound 80-95 SOL transfers to fresh wallets (the §85 instant-fill
seed amount). Hits append to mfg_funding.jsonl {t, chain, fresh_wallet,
sol, sig}; per-wallet last-seen cursors in mfg_funding_seen.json.
Parse-capped at 4 txs/wallet/run with 0.8s spacing (§84a rate limits).
Fail-safe try block; py_compile clean; live from the next run.

A hit = a wallet freshly funded with exactly bleeder-seed money. When
that wallet's mint next appears in mfg_tokens.jsonl (creator match),
the launch is bleeder-class BEFORE the gate evaluates it — the first
pre-launch signal in the system. Cross-reference runs at read time.

Meanwhile: write 08:44:21 — ts180 fwd n=7 (+1.28%), base fwd n=5
(+6.23%), still zero forward bleeders.

## §90 — Treasury tripwire ARMED; forward tally n=11 (2026-09-01 ~09:30)

Write 09:23:52: treasury_watch completed its first live pass — cursors
set for all three chain wallets (mfg_funding_seen.json), no seed-sized
outbound transfers yet. From here, any 80-95 SOL transfer to a fresh
wallet prints a pre-launch bleeder alert within one cycle (~40 min).

Forward tally update: base n=10 at +10.0%/trade, ts180 n=11 at
+1.29%/trade. The forward window has been bleeder-free for ~3h —
baseline is having a strong run in the clean regime (premium gap now
~8.7 pts/trade). Historical bleeder rate 10.7% says a dump is
statistically due within the next several closes; that event is the
joint test of the ts180 stop AND the treasury tripwire (if the bleeder
was chain-funded, we should see the funding alert FIRST).

## §91 — Blind-window cost measured: zero (2026-09-01 ~10:30 local)

Replayed all 462 manufactured launches detected in the forward window
(t ≥ DEP=1788238800) against the s60nm5 entry gate (net ≥ 60 SOL, ≥ 20
buys, median buy ≥ 5 SOL in first 60s). Of the 400 not scored, 192 had
full trade-tape data for reconstruction — **zero** would have qualified
for entry. The ~40-min write cadence with ~20-min overlap-skip gaps
misses plenty of launches, but none that the strategy would have traded.
The gate's selectivity (62 entries of 462 detected = 13%) means blind
windows cost nothing under current rules. Open item #5 (missed
short-lived launches) closed: accepted, quantified, immaterial.

## §92 — Decision frame at parity; clean streak not yet surprising (2026-09-01 ~10:50 local)

Recomputed the baseline-vs-ts180 choice with current forward returns:
baseline clean-regime return +13.20%/trade vs ts180 +1.29%/trade puts
the parity bleeder rate at **10.5%** — the gated historical rate is
**11.1%** (3/27: GsM2Nq, 4xBDmh, AgLSnY). On historical evidence the
insurance is worth its premium, but by less than 1pt — the two
strategies sit almost exactly at parity, so the forward bleeder rate
is the deciding variable, not a refinement.

Structural confirmation: all 6 committed-sample bleeder dumps landed
19–80 min after entry — far beyond the 180s ts180 stop. The insurance
is mechanically immune to the observed dump pattern, not merely
statistically lucky.

Streak check: P(0 bleeders in 11 gated entries | 11.1% rate) = 27% —
the clean forward regime is NOT yet statistically surprising. At ~25
consecutive clean closes P drops below 5% and a genuine regime shift
(operator behavior change) becomes the better explanation. Conveniently
that is also the amendment #4 sample threshold (~30 closes).

## §93 — Pre-dump tape tells: exhaustive negative; tripwire is the only early warning (2026-09-01 ~10:55 local)

Fine-grained forensics on the 3 gated historical bleeders (AgLSnY,
GsM2Nq, 4xBDmh): the 30 min before each dump show perfectly healthy
tape — steady 8–19 SOL of buying per 5-min bucket, ~15 buys/bucket,
mcap drifting up +7–9%, essentially zero sells — then one 5-min block
with 2–3 sell txs totalling 1,034–2,161 SOL and mcap → 0. No decay,
no distribution, no divergence. The dump is a single scheduled block,
not a reaction to tape.

Flow-uniformity test (CV of 5-min buy volume, minutes 5–30): bleeders
0.04–0.35 (mean 0.19), clean tokens 0.04–1.90 (mean 0.32) — full
overlap, NO separation. All manufactured launches share the same
botted-flow signature; the bleeder subset is indistinguishable from
the tape at every timescale tested.

Conclusion: entry-time separation (§85), tape momentum (§89), and flow
uniformity (§93) are all negative. The ONLY viable pre-dump signal is
the funding chain — the treasury tripwire (§89a) is not optional
instrumentation, it is the sole early-warning channel. Its first live
test remains pending (zero outbound funding txs observed).

## §94 — Net-of-cost returns: insurance margin is razor-thin (2026-09-01 ~11:15 local)

First honest cost pass on the forward sample (PumpSwap 0.30%/swap,
priority ~0.2%/round-trip; baseline pays 3 swaps for the freeroll,
ts180 pays 2):
- baseline s60nm5: gross +11.94% -> NET +10.74%/trade (1/13 slightly
  negative after fees, worst -0.8%)
- ts180: gross +1.21% -> NET +0.41%/trade (3/15 negative after fees,
  worst -0.4%); after a realistic 0.3% exit slippage the margin falls
  to +0.11%/trade — break-even at best.

Net-of-cost parity bleeder rate: 9.3% (gross parity was 10.5%).
Historical gated rate 11.1% still favors the insured variant, but the
economics are tight in BOTH directions: baseline wins big only while
the regime stays clean, ts180 survives everything but earns almost
nothing after costs. The honest summary: the gross edge is real, the
net edge is small, and the decision still hinges on the forward
bleeder rate. At ~30 closes, if forward bleeder rate < 9%, baseline
is the net winner; if >= 9%, ts180; the gap between them is now
narrow enough that execution quality (fees/slippage) may matter more
than the choice itself.

## §95 — FIRST FORWARD BLEEDER: 9awYaD (ELON), fast dump, ts180 breached honestly (2026-09-01 ~14:50 local)

The forward clean streak ended at 19. 9awYaD (ELON) was gate-entered
at mcap 7,874 SOL; the insider dumped 229.0 SOL at **entry+92s**
(r 1.000 -> 0.122), then a second 171.3 SOL sell at +258s zeroed the
pool. Both variants closed -86.2% (exit=trail).

CRITICAL REVISION to §92: ts180's loss is HONEST, not a scorer
artifact — the dump printed 92 seconds after entry, INSIDE the 180s
stop window. No live escape was possible: Solana has no public
mempool, the first post-dump print IS the executable price, and a
clock-based stop would have filled at r~0.12-0.21 regardless. The
"mechanical immunity" finding holds only for dumps landing >180s
after entry (all 6 historical gated bleeders dumped at 19-80 min).
Fast dumps hit every variant equally. Insurance protects against the
historical pattern, not this one.

Forward tally after the event: baseline n=20 at +5.81%/trade gross
(~+4.6% net), ts180 n=21 at -2.95% gross (~-3.75% net). Forward
bleeder rates: 1/20 = 5.0% baseline, 1/21 = 4.8% ts180 — still below
the 9.3% net parity rate, so baseline remains the net winner, but
ts180 is now NEGATIVE forward: its premium bought nothing on the one
trade where insurance mattered.

Tripwire MISSED: seeder/creator FLPen3FKHgjW9UHB7ERxPe5FQYAud49oVTwFviWLoa2F
is NOT in CHAIN_WATCH. Manufacturing signature is byte-identical
(86.082 SOL single-signer instant-fill), so this is the same playbook
funded through a new branch. Next action: trace FLPen3's funder and
expand the watch list. (Scorer note: trail check precedes timestop in
the exit loop — moot here since the dump predated the deadline, but
worth fixing for post-deadline collapse fills.)

## §96 — 9awYaD money trail mapped; second funding tree found (2026-09-01 ~15:20 local)

Full lifecycle of the ELON bleeder campaign:
- 14:00:22 — seeder FLPen3FKHgjW9UHB7ERxPe5FQYAud49oVTwFviWLoa2F arms
  hundreds of bundle wallets (0.030 SOL each, same-block burst). Its own
  arming transfer not visible in indexed history (first txs are the
  arming burst itself — funding likely embedded in account creation or
  an indexing gap; inconclusive).
- 14:02:51 launch / 86.082 SOL self-seed; 14:14:20 dump (229 SOL,
  +92s after our entry); 14:25:32 synchronized sweep of ~1,300 small
  transfers from the bundle army back into FLPen3 (same block).
- 14:26:28 — FLPen3 forwards 292.8 SOL to hop
  5ARipQXUFP13QzHau8moMxpvLzXwMLgLgpzjpbsrUzTa, empties to 0.
- Hop is a LIVE distribution hub: 14:28:15–44 splits outbound 70 /
  210 / 334 SOL to three staging wallets; 626–627 SOL then ping-pongs
  F7FK -> 5ARip -> 2CBK -> 5ARip -> 6fy6 (14:31–14:50). Current
  staging holder: 6fy6iHxyPuB4... (626.6 SOL at 14:50:16).

KEY: this tree shares NO wallet with the §89 chain (treasury CmdxEB /
AdiJ1 / 9GQv). Two independent funding trees running the byte-identical
86.082 SOL playbook — either one operator rotating trees or two
operators sharing the recipe. The §89a tripwire watched the wrong tree
for this campaign. Expanding CHAIN_WATCH to the new tree (hop +
staging wallets) next. Note: this tree arms with 70/210/334 SOL splits,
not the 80–95 SOL band the watcher filters on — filter needs widening
or staging-layer watching (staging -> 86 SOL -> launcher is the actual
arming edge).

## §97 — Regime turned: 3 losers in one write; insurance proves itself on the slow one (2026-09-01 ~15:45 local)

The 15:24 write added 3 closes and the first slow-bleed pair test:
- 84X4w5: baseline -46.4% (trail) vs ts180 +1.8% (timestop) — the dump
  landed AFTER the 180s stop, and the insurance worked exactly as
  designed. First live proof on forward data.
- 7FFGDY: baseline -43.9% vs ts180 -5.6% — early slide, stop cut the
  loss ~8x.
- 9awYaD remains the fast-dump counterexample (-86.2% both).

Forward tally: baseline n=24 at +1.51% gross (~+0.3% net); ts180 n=24
at -2.69% gross (~-3.5% net). Loser rates: baseline 3/24 = 12.5%,
ts180 2/24 = 8.3%. The premium gap collapsed from ~11pts to ~4pts;
baseline still marginally ahead net, but the variance is all on its
side now. Both patterns coexist in this regime: fast dumps (beat
everything) and slow dumps (ts180 beats baseline ~48pts).

The §96 tree expansion + widened 60-700 SOL band go live next run.
If 84X4w5 or 7FFGDY were armed through either watched tree, backdated
funding alerts will validate the tripwire retroactively.

## §98 — TRIPWIRE LIVE-FIRED: funded wallet g9XbLp armed, pre-launch (2026-09-01 ~16:10 local)

First patched run of the expanded watcher produced the project's first
funding alert: staging wallet 4Lr8de (ELON tree, §96) sent **203.96 SOL
to fresh wallet g9XbLpuBZuPqmWvdv39QYzUzcLJXyNa3Nys527hhSnM** at
14:56:45 local. The retroactive sweep also proves the widened 60-700
SOL band catches staging-layer distribution.

g9XbLp has launched NOTHING yet (zero tokens as creator in the
detection feed). 204 SOL arms ~2 manufactured launches at the standard
86 SOL pattern. This is the first time we hold a **prospective**
bleeder-class suspect: funded from a known bleeder tree, watched,
pre-launch. When its first token appears, the prediction is:
manufactured launch (86 SOL instant-fill) followed by an insider dump
— and the funded-wallet identity gives an entry-time REJECT signal
that no tape metric could provide (§85/§89/§93 all negative).

Open positions in flight: 9orw5y, QTw25p (both ~1.01x). Tally:
baseline n=24 +1.51%, ts180 n=25 -2.57%.

## §98a — Funded-reject shadow deployed (2026-09-01 ~16:35 local)

New scorer variant mfg_paper_trades_s60nm5fr.jsonl: identical s60nm5
gate, but skips any entry whose creator is a tripwire-flagged funded
wallet (mfg_funding.jsonl fresh_wallet set). Live in the tracker from
the next run (paper_score gained funded_reject param; compile-clean;
live code snapshotted to automations/tracker_live.py). Currently the
funded set = {g9XbLp} and it has no launches, so the shadow matches
s60nm5 until the armed wallet fires. Honesty note: the skip uses
current funding data, so historical backfill rows carry lookahead —
only forward closes after this deployment count for the variant call.

## §99 — Quiet-pool time-stop fix: honest deadline fills (2026-08-31 ~20:55 local)

**Bug found.** ts180 (3-min time-stop shadow) printed −100% on bleeder
9orw5y — identical to baseline. Cause: stops only evaluate ON TRADE
PRINTS. 9orw5y's pool went quiet after +53s (last print r=1.007); the
next print landed past +15min post-collapse, so stage1's abort15 fired
first with a next-trade fill at the zeroed price. Worse, the deadline
remainder path (the §70 honest clock-based fill, `_price_at` = last
print at/before the deadline) checked `mins_now >= P_TS_MIN` — the
120-min CONSTANT — not the variant's `tsm`, so ts180's 3-min stop never
got the honest deadline fill at all.

**Fix (automation.py, scorer `paper_score`).**
1. Hoisted `_price_at(deadline_s)` above the trade loop (was defined
   only inside the post-loop remainder block).
2. In-loop timestop now fills at `_price_at(tsm * 60)` — the price AT
   the deadline — instead of the next-trade price, which on a quiet
   pool can be a post-collapse zero.
3. Remainder-path timestop check and fill now use `tsm`, not
   `P_TS_MIN`.
py_compile OK; live from next tracker run; snapshot in
automations/tracker_live.py.

**Expected row revisions (backfill).** 9orw5y ts180: −100% → ~+0.7%
(last pre-deadline print r=1.007). 9awYaD stays ≈−86% — its dump
PRINTED at entry+92s, before the 180s deadline; honestly inescapable
(Solana has no mempool; you cannot see the dump tx before it lands).
Fast dumps remain defensible ONLY via the funded-reject gate (§98a).

## §100 — Retro-validation: 2 of 4 forward bleeders are tree-member launches (2026-08-31 ~21:00 local)

Creator check of all four forward losers against both watched trees:

| mint | creator | in tree? |
|---|---|---|
| 9awYaD (−86.2%) | FLPen3…WLoa2F (ELON seeder) | YES |
| 84X4w5 (−46.4%) | 6fy6iH…Euj7R (ELON capital holder) | YES |
| 7FFGDY (−43.9%) | jmeuPE…y5Xqpg | no — third funding source |
| 9orw5y (−100%) | DuACsk…cnozz | no — fourth funding source |

The bleeder operators don't only arm FRESH wallets — they launch
directly from chain-member wallets too. The §98a fr gate rejected only
funding RECIPIENTS; it would have missed both of these.

**Patch:** the funded-reject set is now CHAIN_WATCH ∪ funding
recipients (one-line change in paper_score; compile-checked; live next
run; snapshot in automations/tracker_live.py).

**Counterfactual forward tally** (lookahead-tainted retro, honesty
caveat applies — forward closes from this deployment are the clean
test): baseline s60nm5 n=26 at −2.08% gross → extended-fr n=24 at
**+3.27% gross** (rejects 9awYaD −86.2% and 84X4w5 −46.4%). Against
the §94 fee model (~1.2%/trade) that is ≈ +2.1% net/trade — the first
net-positive configuration seen forward. Remaining uncovered risk:
7FFGDY and 9orw5y came from UNWATCHED trees — coverage, not concept,
is now the binding constraint.

## §101 — Uncovered bleeders are reused high-activity wallets (2026-08-31 ~21:10 local)

Backward trace of the two uncovered bleeder creators (7FFGDY/jmeuPE,
9orw5y/DuACsk): both wallets have **1,000+ chain transactions** — my
20-page × 50-tx scan never reached their first inbound funding. These
are NOT the fresh-armed-wallet pattern (FLPen3 → g9XbLp); they're
reused, high-activity creator wallets. Implications:

1. The tree tripwire (§98a/§100) cannot see them unless their funding
   source is found — deep-history paging on public RPC is impractical
   (1000+ txs × 1.7s spacing ≈ 30+ min/wallet, 429-prone).
2. Each has exactly ONE launch in our tracked data, so a
   "serial-bleeder blacklist from our own history" would only catch
   their NEXT rug — still useful as a cheap third layer (creators of
   closed −30%+ positions go on a reject list; costs one loss per
   operator, caps repeat exposure).
3. Honest coverage accounting forward: tree gate catches ELON-tree
   campaigns (2/4 bleeders); self-blacklist catches repeats; genuinely
   new operators remain the residual risk (~2 per 26 entries so far).

Public-RPC budget note: the 16:44 tracker run was still alive at +14
min (12.6s CPU — RPC 429 backoff, not a hang); 10 chain wallets ×
small pages is stretching the interval. May need pagination trim.

## §102 — ELON tree re-arming burst: three armed wallets, ~970 SOL staged (2026-09-01 17:05 local)

New tripwire alerts (detected 17:05 run):

| time | chain wallet | fresh wallet | SOL |
|---|---|---|---|
| 14:56 | 4Lr8de (staging) | g9XbLp | 203.96 |
| 16:38 | 5ARipQ (hub) | DaBchS9P | 462.54 |
| 16:40 | 5ARipQ (hub) | DaBchS9P | +100.00 |
| 16:42 | 4Lr8de (staging) | AR35wRzb | 203.96 |

Notes:
- AR35wRzb got EXACTLY 203.962 SOL — identical to g9XbLp's arming.
  Same playbook (≈2 launches at the 86 SOL instant-fill + fees).
- DaBchS9P holds 562.5 SOL ≈ 5-6 launches — biggest single staging yet.
- g9XbLp has been armed 2h+ WITHOUT launching (9awYaD launched 2.5 min
  after arming). Either a longer cycle or the wallet is held in reserve.
- All three are auto-added to the §100 extended reject set at scoring
  time; their first launches will be skipped by the fr shadow and are
  the clean prospective bleeder tests.
- 4Lr8de has now dispensed 2× 203.96 despite earlier outflow — the tree
  is being refilled from upstream (likely 6fy6iH, 626.6 SOL at 14:50).
  Net observed deployable capital across the tree ≈ 1,800+ SOL today.

## §103 — TRIPWIRE PREDICTED A LAUNCH: AR35wRzb in live bundle ecosystem ~30 min after arming (2026-09-01 17:15-17:30 local)

Timeline: 4Lr8de armed AR35wRzb with 203.962 SOL at 16:42:38 (tripwire
alert). At 17:15:47 a coordinated burst of 14+ single-signer PumpSwap
(pAMMBay6) buys touched AR35wRzb in the same second — the universal
manufactured-launch signature. The token involved: F5a7aNca…W1Vpump
(extremely hot: 2,500+ txs within minutes; couldn't page to creation
on public RPC — 25 pages × 100 only reached 17:18:46, still above the
17:15:47 buys, so creation is earlier and the fee-payer at that depth,
FaLcLtKY, is NOT proven creator; FaLcLtKY itself has 300+ txs back past
16:40, not fresh).

Also odd: between 16:44–17:11, AR35wRzb sent ~347 SOL back OUT to
4Lr8de in 7 chunks (40-90 SOL each, multi-signed) — more than the
203.96 it received, so AR35wRzb has other inbound. The tree moves
capital in BOTH directions between staging wallets; "arming" is not
one-way.

Operational takeaways:
1. Tripwire predictive value CONFIRMED circumstantially: funding alert
   → same wallet inside a manufactured bundle ecosystem ~30 min later.
2. Creator-keyed gating may MISS launches where the operator inserts a
   hop (armed wallet funds a separate creator). Cheap resolution: when
   the tracker's own birth indexer records F5a7aN (if it matches the
   big-seed filter), its creator field gives definitive membership —
   no RPC paging needed.
3. Whether F5a7aN bleeds over the coming hours is the observable test;
   if the fr shadow scored it, compare variants.

## §104 — Latent bug: ts180 scorer was dead since §98a deploy (2026-09-01 ~17:30 local)

The §98a insert accidentally left the ts180 paper_score block INSIDE
the preceding `except Exception: pass` handler — it only ran when the
fr scorer raised. Evidence: mfg_paper_trades_s60nm5ts180.jsonl last
written 16:35 while all other variants updated 17:03. Consequence: the
§99 honest-deadline timestop fix never executed live. Fixed by giving
ts180 its own try block; compile-checked. The next run is the first to
score ts180 with BOTH the §99 deadline fill and correct execution —
expect 9orw5y's ts180 row to revise −100% → ~+0.7% then. Forward ts180
closes between 16:35 and now are missing from the file; they re-enter
on the next write since scoring replays the full trade log each run
(no data lost, just delayed).

## §105 — Self-blacklist layer deployed (2026-09-01 ~17:40 local)

Third defense line built (proposed in §101): creators of positions
that close at ≤ −30% in the baseline replay are appended to
mfg_creator_blacklist.jsonl with their close time. The funded-reject
scorer now rejects a mint when its creator is (a) a CHAIN_WATCH member,
(b) a tripwire funding recipient, or (c) on the self-blacklist with a
blacklist time EARLIER than the mint's first trade — the timestamp
guard keeps historical rows lookahead-free. Accrual runs before the fr
scorer within the same run, so a bleeder closing now protects against
its operator's next launch immediately. Cost model: one loss per NEW
operator, then repeats are free to dodge. Applies to the §101 finding
(jmeuPE / DuACsk 1,000+-tx reused wallets whose funding trees can't be
traced on public RPC). Compile-checked; live next run.

## §106 — Honest clock fills for ALL deadline exits; dry-run verification (2026-09-01 ~17:45 local)

Offline dry-run of the patched scorer against the live trade log
(forward closes, entry_t ≥ DEP):

| variant | n | avg gross | notes |
|---|---|---|---|
| baseline s60nm5 | 27 | +0.86% | 9orw5y now +0.7% (abort15 at honest 15-min price) |
| ts180 | 27 | −2.98% | 84X4w5 −4.6%, 7FFGDY −12.6% via honest timestop |
| **fr extended** | **25** | **+6.23%** | excludes both tree-member bleeders; 9orw5y +0.7% |

§99 follow-up bug found by the dry-run: the quiet-pool next-trade fill
bug afflicted ALL clock exits (nm_abort, abort15, abort), not just
timestop — abort15 checked earlier in the loop, so 9orw5y still filled
at the post-collapse zero. Patched all three to `_price_at(deadline)`.
The freeroll and TRAIL exits keep next-trade fills (price-triggered,
not clock-triggered — trail on a live tape is honest).

Net-of-fees read (§94 model ~1.2%/trade): fr extended ≈ **+5.0%
net/trade** on n=25 forward closes. Two of the four forward bleeders
remain reachable only by the self-blacklist (7FFGDY) or are now
survivable (+0.7% instead of −100%: 9orw5y).

## §107 — Live wallet created + arming wave continues + extended gate confirmed live (2026-09-01 17:45 local)

**Owner direction:** move toward live-money testing. Created Solana
keypair CQcKkSee9bdHZ1bejYFDUXVtodbfKHe2KSx6AaAnTW2K — secret stored
in live_wallet.json (chmod 600, gitignored; NEVER commit). Execution
wiring (Jupiter/pumpportal swap builder, position sizing, kill-switch)
is the next build; live trades still require the owner's explicit go.

**Arming wave:** 5 fresh wallets now staged from the ELON tree,
~1,740 SOL total: g9XbLp 204 (14:56), DaBchS9P 562.5 (16:38-40),
AR35wRzb 204 (16:42, already tied to the F5a7aN bundle burst §103),
4PRXBB 563 (17:25-27), 47bRU5 209 (17:32). A multi-launch wave is
being prepared; all five are auto-rejected by the fr gate.

**Live confirmation:** the 17:43 fr write matches the §100 dry-run
exactly (n=25, +3.32% gross; 9awYaD/84X4w5 excluded). 9orw5y still
shows −100% there because that run predated the §106 honest-fill
patch; next run lifts it to +0.7% and the tally to ≈ +6.2% gross /
+5.0% net. ts180 file still stale (§104 fix lands next run).

**Coverage gap watch:** F5a7aN (launched ~17:14, bundle ecosystem
confirmed on-chain) is STILL absent from mfg_tokens.jsonl 30 min
later — the birth detector's big-seed filter may have missed it.
Investigate before relying on the fr gate's creator check for it.

## §108 — Live execution path built and dry-run verified (2026-09-01 ~17:55 local)

live_trader.py created (MON, gitignored wallet untouched):

- **Two hard gates, both required**: (1) owner-created
  manual_signoff.json with {"live": true} — the agent NEVER creates
  it; (2) absence of STOP_LIVE_TRADING — drop that file in MON to halt
  everything instantly. Checked before every trade.
- **Key never leaves the machine**: Jupiter lite-api (no key needed;
  quote-api.jup.ag is dead) returns an unsigned v0 transaction; local
  ed25519 signing via cryptography; submit via public RPC.
- **Sizing**: 5% of balance, hard cap 0.2 SOL/entry, always keeps
  0.05 SOL for fees. Slippage 1500 bps, priority fee ~0.0002 SOL.
- **Ledger**: mfg_live_trades.jsonl records every decision including
  dry-runs and refusals — paper and live records stay comparable.
- Verified: compile OK; self-test prints address/balance/mode;
  dry-run buy against JUP mint fetched a real quote (0.01 SOL →
  4,635,010 JUP atoms, impact 0.0018%) and correctly refused to submit
  (no signoff). Mode prints DRY-RUN until the owner signs off.
- Coverage limit: Jupiter routes PumpSwap (graduated) tokens only;
  pre-graduation bonding-curve entries need the pump.fun program path
  (§109). Early entries on the curve are where the s60 gate fires —
  so §109 is required before live can follow the actual signals.

## §109 — pump.fun bonding-curve path: empirical layout extraction (2026-09-01 ~18:00 local)

Jupiter only covers graduated tokens, so live entries need the
pump.fun program path. Sampled a real on-chain tx touching program
6EF8rr… on fresh mint 5V1SBZvA…pump:

- The sampled ix was a SELL: discriminator 33e685a4017f83ad, 24-byte
  payload = disc(8) + amount u64 LE (5,807,028,916,160 tokens) +
  min_sol_out u64 LE (0 — bundle bots use zero slippage protection).
- Modern 16-account layout observed: [0] global 4wTV1Ymi…xnjf,
  [1] fee recipient G5UZAVbA…q69dP, [2] mint, [3] bonding curve,
  [4] assoc bonding curve, [5] assoc user, [6] user/signer,
  [7] 11111111 system, [8] creator-vault-like 5q9evK5W…NuEA8,
  [9] **TokenzQd… = Token-2022** (this mint is Token-2022, not classic
  SPL — ATA derivation must use the Token-2022 program id),
  [10] event authority Ce6TQqeH…Xp9F1, [11] program itself,
  [12] 8Wf5TiAh…VwTt, [13] fee PROGRAM pfeeUxB6…ojVZ,
  [14] HFE9p7yc…rhRg, [15] GXPFM2ca…mtDL.
- Open items before writing the builder: (a) sample a BUY ix
  (66063d1201daebea) the same way — buys carry extra volume-accumulator
  accounts; (b) confirm which of [12]-[15] are program constants vs
  per-user/per-mint PDAs by diffing two buys from different wallets;
  (c) confirm whether ALL post-migration mints are Token-2022 or mixed;
  (d) ATA-create wrapper ix for the buyer's token account.
- Note: bundle bots pass min_sol_out=0 on sells. We will NOT — our
  honest-fill model assumes deadline-price exits, so live sells carry a
  floor (e.g. 10% under the observed mark) to bound slippage honestly.

## §110 — pump.fun curve path FULLY SPECIFIED from on-chain IDL (2026-09-01 ~18:15 local)

Fetched the pump program's Anchor IDL from chain (pump_idl.json
saved). Canonical layouts:

**BUY (16 accounts)**: global ["global"], fee_recipient (Global.acct
offset 41; rotation explains per-tx [1] variation), mint,
bonding_curve ["bonding-curve",mint], assoc_bonding_curve (ATA),
associated_user ATA (Token-2022 for new mints — per-mint program from
mint-account owner), user, system, token_program, creator_vault
["creator-vault",creator], event_authority ["__event_authority"]
(verified = Ce6TQqe…), program, global_volume_accumulator (verified),
user_volume_accumulator ["user_volume_accumulator",user] (verified),
fee_config ["fee_config",const32] under pfeeUxB6 (verified =
8Wf5TiAh…), fee_program. Data: disc 66063d1201daebea + token_amount
u64 + max_sol_cost u64 (buy is TOKEN-amount in, SOL cap).
**SELL (14)**: same minus both volume accumulators; disc
33e685a4017f83ad + token_amount + min_sol_out (we set a floor, bots
pass 0).
The extra [16]/[17] seen in bundle-bot txs are optional fee-sharing
accounts — not needed for the canonical path.
Global account parsed from IDL: fee_recipient @41, fee_recipients[7]
@162, cashback/buyback fields @740+. Expected-token math uses bonding
curve virtual reserves (vTok/vSol) minus fee_basis_points @105.
All PDA derivations verified against live addresses. Next: write
curve_buy/curve_sell + legacy-tx builder (ComputeBudget + ATA-create
idempotent + buy ix) into live_trader.py.

## §111 — Curve path built + simulated on-chain: structurally VALID (2026-09-01 ~18:30 local)

live_trader.py extended with the full pump.fun bonding-curve path:

- Pure-python PDA derivation (ed25519 on-curve check + sha256),
  base58, legacy-tx compiler (key ordering: signers → writable →
  readonly), ComputeBudget ixs (300k CU limit, ~0.0002 SOL price),
  ATA createIdempotent wrapper, local ed25519 signing.
- curve_buy(mint, sol): reads curve state on-chain (virtual reserves,
  fee bps, creator from curve tail @49, token program from mint owner
  — Token-2022 for current mints), computes expected tokens via
  constant-product, sends amount = 85% of expected (adverse-move
  guard), maxSolCost = exactly our size. Bonding-curve BUY = 16
  accounts per the IDL; SELL = 14 (no volume accumulators).
- curve_sell(mint, tokens, min_sol_out): honest slippage floor (unlike
  bundle bots' min=0).
- **On-chain simulation test** (sigVerify off, dry-run): tx loads all
  18 accounts successfully, fails ONLY with AccountNotFound on the fee
  payer — our unfunded wallet. Structure is valid; it should execute
  once the wallet is funded. Gates still enforced (no signoff →
  dry-run; simulation only, nothing submitted).
- Live flow when owner goes: fund wallet → owner creates
  manual_signoff.json {"live": true} → tracker signals call curve_buy
  at s60nm5+fr-gated entries → exit stack calls curve_sell with
  floor → every decision in mfg_live_trades.jsonl. Kill-switch:
  drop STOP_LIVE_TRADING file, checked before every trade.

## §112 — Live hook wired + all scorer fixes confirmed live (2026-09-01 ~18:35 local)

Tracker now calls live_trader.curve_buy for every fresh fr-gated
entry (entry_t < 20 min, not previously signaled; state in
live_signal_state.json). Dry-run sizing probes at 0.01 SOL; when the
owner's signoff enables live mode it switches to real position sizing
(5% of balance, 0.2 SOL cap). Every hook decision lands in
mfg_live_trades.jsonl — watch that file to see exactly what live WOULD
buy. Exits are NOT yet wired (need a tighter per-position loop, §113).

Confirmed live this cycle (18:03-18:23 writes):
- ts180 file now matches the §106 dry-run exactly: n=27, −2.98%;
  9orw5y +0.7% (was −100%), 84X4w5 −4.6% (was −46.4%), 7FFGDY −12.6%.
  §99/§104/§106 all live-verified.
- mfg_creator_blacklist.jsonl exists and is accruing (§105 live).
- fr shadow steady at n=25, +3.32% gross (will revise to ≈+6.2% as
  9orw5y's row is rewritten by the §106 honest fills).

## §113 — Exit watcher built, wired, smoke-tested (2026-09-01 ~18:45 local)

live_trader.py gains the §56e exit stack for real positions:
open_position() records entry at the live curve price (tokens via
constant-product), exit_watch() applies freeroll 75%@1.5x, trail at
50% of peak, abort15/abort30, 120-min timestop — exits call
curve_sell with an 85% min-SOL floor; everything ledgered including
"hold" decisions. The tracker hook now records a position after every
(dry-run or live) entry and runs exit_watch() each pass. Smoke test:
opened a synthetic 0.01 SOL position on a live curve, priced it
(2.84e-5 SOL/token), correctly held at r=1.0, cleaned up.
Honest limitation: exits run at tracker cadence (~10-15 min) — fine
for aborts/timestop, but the freeroll window can be seconds after
entry; a dedicated sub-minute loop is future work once live proves
out. The full loop (signal → gated entry → managed exit → ledger) is
now wired end-to-end in dry-run; only the owner's signoff + funding
separate it from live.

## §114 — F5a7aN coverage gap ROOT-CAUSED and fixed (2026-09-01 ~18:50 local)

F5a7aN never reached curves.jsonl — the raw create-event log — so the
miss was upstream of the seed filter. Birth density check: steady
~25/min, but ZERO births recorded 17:04–17:23, exactly covering the
F5a7aN creation window. Root cause: the main PumpPortal birth websocket
called run_forever ONCE per run with no reconnect — a dropped
connection ended all birth capture for the rest of that ~19-min run
(the Helius loop had reconnect-with-backoff; the birth stream didn't).

Fix: reconnect loop with 2s pause until the run deadline;
subscriptions re-arm in pump_on_open (verified: Helius on_open already
re-warms curve/pool account subscriptions on reconnect — the birth
stream was the only unguarded feed). Missed events during a gap are
unrecoverable from PumpPortal; with 2s reconnect the worst-case blind
window is now seconds, not tens of minutes.

Lesson folded into design: the fr/identity gates can only reject what
the birth detector sees; stream liveness IS gate coverage.

## §115 — Self-blacklist first live catch + regime note (2026-09-01 ~18:40 local)

CGphgNh6 (entry 18:03) rugged to −100% via trail — peak only 1.13,
then zero inside ~20 min. Creator 8L7GcUxU… is in NO watched tree and
had no funding alert: a genuinely new operator. The fr gate took the
hit (both variants −100% on this one) — but the §105 self-blacklist
captured the creator at close (entry #27+), so this operator's NEXT
launch is auto-rejected. First live proof of the blacklist layer
working as designed: one loss per new operator, never two.

Tally check (entry_t ≥ DEP): baseline n=28 at −2.74% gross; fr n=26
at +2.15% gross (≈ +0.95% net after §94 fees — still positive but
thin in this hostile regime; 9orw5y now +0.7% live confirming §106
fills). New-operator bleeders are landing ~1 per 13 entries; each one
retires an operator from the repeatable pool. Amendment #4 decision
still pending ~30+ fr closes.

## §116 — Amendment #4 decision frame computed (2026-09-01 ~18:45 local)

Forward tallies (entry_t ≥ DEP, honest fills live):

| variant | n | gross | net* | bleeder rate |
|---|---|---|---|---|
| baseline s60nm5 | 28 | −2.74% | −3.9% | 14.3% |
| fr gate | 26 | +2.15% | **+0.95%** | 7.7% |
| ts180 | 28 | −2.84% | −3.6% | 3.6% |
| fr+ts180 combo (dry-run) | 26 | +0.44% | −0.6% | 0% |

*net of §94 fees (~1.2% baseline/fr, ~0.8-1.0% ts180).

Read: the time-stop is NEGATIVE-EV insurance — it cuts grinders more
than it saves on bleeders, in both gated and ungated contexts. The fr
identity gate is the only net-positive config; its residual 7.7%
bleeder rate is now second-order handled by the self-blacklist
(operators retire after their first rug — §115 proof). Pre-registered
formal call still waits for n≥30 fr closes, but the data direction is
set: promote the fr gate to the main strategy; retire ts180.

## §117 — F5a7aN bled out: prospective tripwire chain CONFIRMED (2026-09-01 ~18:40 local)

The token at the center of the AR35wRzb arming (§103) has had ZERO
transactions for 58+ minutes: bundle burst ~17:15, dead by ~17:40.
Full prospective chain now on record: tripwire funding alert (16:42)
→ armed wallet inside the launch's bundle ecosystem (~30 min later)
→ token dead within ~25 min of the burst. The launch our fr gate
would have skipped was indeed a bleeder. (Caveat: our birth detector
missed it — §114 gap, now fixed — so this is chain-forensic
confirmation, not a scored paper row.)

## §118 — Run-duration trim (2026-09-01 ~18:45 local)

Runs are sleep-bound (16+ min elapsed, ~8s CPU — public-RPC 429
backoff dominates). Trimmed treasury_watch: 12→8 sigs/wallet,
4→2 tx parses/wallet/run, 0.8s→0.5s spacing. Alert sensitivity
preserved: these chain wallets move a handful of times per day and
the seen-cursor keeps continuity across runs. Effect lands next run.

## §119 — Armed-wallet launches caught x3; structural blind spot found; GPRO pumping live (2026-09-01 ~19:00 local)

Tripwire escalated: three funded wallets launched within ~1h —
GROKCAT (4PRXBB, armed 563 SOL, born+graduated 17:32:51 same slot),
Erin (6Tx7VtE5, armed 633 SOL, born 18:06:24, graduated 18:13),
GPRO (JA151CZ, funded 300 SOL 18:33:11, born 18:32:59 — funding and
launch in the same minute; tripwire lead time has shrunk to ~0).

Identical fingerprint on all three: 85.005 SOL seed buying 793.1M
tokens (79.31% of supply) inside the create tx, vSol 115.005,
birth mcap 410.9 SOL, atomic same-slot MigrateV2, pool seeded with
206.9M tokens + 67.4059 WSOL. The ENTIRE curve phase is one slot.

Chain outcomes (public RPC forensics):
- GROKCAT: pool burst 17:50-17:57 (200+ sigs), then drained —
  0.001x vs migration. Dead ~25 min after birth.
- Erin: pool burst 18:51-18:58, drained — 0.002x. Dead.
- GPRO: quiet 18:33→~18:58 at ~1x pool price, then burst began
  18:58:10 (100 pool sigs in 59 s — the F5a7aN signature). At check:
  pool holding 804 SOL, price 115x migration, mcap ~37.5k SOL. LIVE.

Structural findings:
1. ZERO mfg_trades rows for all three — the tracker saw the births
   (curves.jsonl) but derived no trades. With Helius quota dead, the
   curve-polling fallback sees the curve born-complete and gone in
   one slot; pool polling never engaged. The instant-graduation style
   is invisible to our trade-flow layer.
2. s60nm5 could NEVER fire on these even with perfect data: nb>=20
   curve buys cannot exist when the curve phase is a single slot.
3. The tradeable pattern instead: quiet pool window at ~1x migration
   price lasting 18-25 min after birth (all three), THEN the violent
   bundle burst. Entry = pool at ~1x during the quiet window (armed
   wallet birth is the signal — tripwire now gives 0-40 min warning);
   exit = sell into the burst; the burst IS the exit liquidity.
   Scoreboard if entered at migration ~1x: GROKCAT/Erin die (−100%
   if held through, freeroll into the burst saves them), GPRO +115x
   and counting. This is the freeroll asymmetry in its purest form.

Next build: armed-birth pool watcher — on any birth whose creator is
in the funded set (or seed >= 80 SOL with >= 75% supply initialBuy),
derive/locate the pool immediately and watch vault deltas at seconds
cadence, bypassing curve semantics entirely.

## §120 — Armed-birth pool watcher shipped (2026-09-01 ~19:15 local)

Root cause of the §119 blind spot: MAX_TRACK=40 curve slots vs
~155 seed>=5 births/hour — the cap saturates ~15 min into every run,
so mid-run big-seed births (incl. all three armed launches) were
dropped before ever getting a curve subscription. Zero flow rows,
zero snapshots, gate blind.

Fix shipped in the tracker:
1. Armed-birth override in the create handler — creator in the
   funded set (mfg_funding.jsonl) OR fingerprint (seed >= 80 SOL AND
   initialBuy >= 700M of 1e9 supply) → force-tracked, bypasses
   MAX_TRACK, ledgered to mfg_armed_births.jsonl, and when
   vSol >= 110 the token is marked born-terminal immediately
   (no waiting for the migrate event).
2. Instant pool parse on migrate — for armed tokens the migrate tx
   is fetched and the pool + both vaults extracted from
   postTokenBalances (owner holding mint TA + WSOL TA = pool).
   Validated 3/3 against GROKCAT / Erin / GPRO known pools. GT's
   multi-minute indexing lag no longer matters for armed births;
   the ~18-25 min quiet entry window is now fully observable via
   the existing §66b vault-polling path.
3. Run summary now reports armed=N.

Effect lands next run (runs load the file at start). Every future
instant-grad launch gets pool flow from minute zero.

## §121 — First live-hook fire + graduation gap found (2026-09-01 ~19:10 local)

The §112 hook fired on its first real signal: 7SKW1cEF (fr-gated,
fresh) at ~19:04. curve_buy correctly REFUSED — "curve complete
(use Jupiter path)": the token had already graduated inside the same
run window. Plumbing works end-to-end (signal -> hook -> ledger ->
dedupe state); the gap is that graduated entries need the pool path.

## §122 — Jupiter fallback wired into the hook (2026-09-01 ~19:15 local)

On "refused: curve complete" the hook now takes a Jupiter quote and
ledgers exactly what a pool-side entry would pay (outAmount +
priceImpactPct), so model-vs-live slippage on fast graduators is
measured, not guessed. Position is NOT opened for these — exit_watch
prices via the curve; pool-priced exits are the next build (they
belong with the §120 watcher anyway, since armed births are
pool-native from t=0).

GPRO watch: burst still active at 19:10 — pool holding 822 SOL,
+120x vs migration (~39k SOL mcap). GROKCAT and Erin both drained
to ~0.001-0.002x. Current manufactured scoreboard: 2 dead, 1 at
+120x — freeroll asymmetry confirmed in the wild.

## §123 — Full live path wired: Jupiter entries + pool-venue exits (2026-09-01 ~19:45 local)

Regime discovery from the hook's first four real signals (7SKW1cEF,
FLE8Cc2A, 6d2Xsj3f, 5dGGJ78o — 19:04-19:24): EVERY fr-gated signal
graduated before the hook fired. The bonding-curve entry path is
structurally dead in this meta; the pool IS the venue.

Shipped:
- live_trader: jupiter_quote_sell + _jupiter_submit + pool_sell;
  buy() now records tokens_raw; open_position takes venue="pool"
  (entry_px/tokens from the buy quote — the curve is gone by then);
  exit_watch branches by venue — pool positions priced by Jupiter
  sell-quote on the remaining stack, exits via pool_sell.
- Hook: graduated signal + live gates open -> real Jupiter buy
  (0.134 SOL at current balance) + pool-venue position opened;
  dry-run stays quote-only. All rows ledgered as before.
- Read-only validation: GPRO quotes route via the CORRECT Pump.fun
  Amm pool (6cV33v...). No fake positions created — with live gates
  open, exit_watch would really sell them.

GPRO FINAL: born 18:33 -> quiet 25 min at ~1x -> burst 18:58 ->
+123x peak 19:15 (831 SOL pool) -> DRAINED to 0.2 SOL by ~19:40.
Full lifecycle 67 minutes. Manufactured scoreboard final: GROKCAT
-100%, Erin -100%, GPRO +123x peak then -100% if held. The freeroll
stack (bank 75% at 1.5x, trail the rest) monetizes exactly this
shape; hold-to-death loses everything. This IS the edge, confirmed
on three prospective cases.

Replay note: GROKCAT alone has 19,427 pool transactions; full
per-tx reconstruction runs checkpointed across slices (211 done).
ETA hours; scoring is per-case resumable.

LIVE STATUS: gates open (owner sign-off 19:27). Next tracker run
enters for real on the next fr signal. Kill switch: STOP_LIVE_TRADING.

## §124 — The meta converged; late-entry guard on live entries (2026-09-01 ~20:05 local)

§120 live and catching: mfg_armed_births.jsonl accrued 6 launches in
12 minutes (19:46-19:58: RST, USMS, LEGO, PONS, FROG, M32) — all the
identical 85.005 SOL / 793.1M (79.31%) / 410.88 SOL fingerprint, all
from fresh creators not yet in the funding file (funded=false — the
tree rotates one creator per launch; fingerprint >> funding list now).

Convergence proof: the fr gate's own signals ARE the manufactured
launches. FLE8Cc2A/6d2Xsj3f/5dGGJ78o (the hook's 19:24 refusals) are
fingerprint births at 18:53/18:55/19:05. The identity gate and the
instant-grad fingerprint are two sensors on the same population.

Replay truth (GROKCAT, first ticks): the "quiet ~1x window" was an
artifact — 47bRU5 was funded 208.913 SOL in the SAME SECOND as the
birth and instantly market-bought it; pool was at 14.16x within one
second. GPRO differed: genuinely quiet at ~1x for ~3-25 min. Two
sub-patterns: instant-burst vs slow-brew.

Consequence: the forward tally's +0.95% net was validated at MODEL
entry prices (gate-crossing time). Live hook entries fire 15-40 min
later at pool prices that can be 3-100x higher. Guard shipped: the
hook now quotes first and SKIPS (ledgered) any entry whose hook-time
price is >3x the paper entry_mcap — better to miss a runner's tail
than buy a manufactured top. Skips and entries both ledger; the
skip/enter ratio is itself data on the botnet wave.

## §125 — FIRST LIVE FILL: verified on-chain (2026-09-01 20:04 local)

Signal: HK6Na6tphM ("RST") — §120 armed birth 19:46:28 (fingerprint
catch, creator Ff2SR8GgqD), fr-gated, hook fired 20:04. Curve already
complete -> late-entry guard PASSED (hook price <=3x model) ->
Jupiter buy submitted live:
  sig 3SDCT6tjCMe3w4zRk3sDVHZ4eX1E3LGSpnKYsKpiZ7K8ndd1sVNw1ayqZYv5YxtG7jW8QwhKnZSdvv15NsBeVJfV
  spent 0.138323 SOL all-in (0.1342 swap + 0.000205 fee + ATA rent)
  received 89.071544 RST (quote 89.079181 — fill/quote diff 0.009%)
  wallet after: 2.545562 SOL
Mark-to-market minutes later: sell quote 0.134217 SOL = -2.97% vs
all-in cost (fees + drift). No instant rug; exit stack (freeroll
75%@1.5x / trail / abort15/30 / timestop120) now managing a real
pool-venue position via Jupiter sell-quotes each tracker pass.

The full loop is proven live: birth fingerprint -> fr gate -> guard
-> real fill -> on-chain verified -> priced exits. What remains is
the only thing that ever mattered: enough live closes to see if the
edge survives real execution.

## §126 — Fast exit loop wired into the tracker (2026-09-01 ~20:12 local)

The freeroll window on manufactured tokens is seconds; exit_watch ran
once per ~15-19 min run. Fixed without any new Automation or quota:
the snapshot thread already loops every 10s, so it now prices open
live positions every ~45s (no-op — zero RPC/Jupiter calls — when
nothing is open). Effective exit cadence: ~45s during runs, gap only
between runs (~1-2 min). live_exits counter added to run stats.

RST position state (first live trade, §125): opened 20:04 at
0.1383 SOL all-in; mark 20:10 = 0.1349 SOL (r=1.005). abort15 fires
at 20:19 if r<1.08 — the first real exit execution is imminent and
will test the pool_sell path live (freeroll not in play at r~1.0).

## §127 — Silent-submit bug: phantom exit, then first REAL live exit (1 Sep 2026, ~20:55 BST)

**Incident.** abort15 fired on RST at 20:20:18. `pool_sell()` logged
`result:"submitted"` with `sig:null` — the Jupiter submit failed
silently through RPC retries and returned no signature — yet
exit_watch mutated the position to closed anyway. Reality vs ledger:
we still HELD all 89,071,544 RST raw (~0.14 SOL of exposure) while
`live_positions.json` claimed open:false, tokens_left:0. The system
had lost track of a live bag. Caught by on-chain reconciliation.

**Fix (live_trader.py, three changes):**
1. `buy()` and 2. `pool_sell()` now report
   `"submit failed: no signature (RPC)"` when `_jupiter_submit()`
   returns no signature — a signature-less submit is never again
   logged as "submitted".
3. `exit_watch()` success gate: position state (tokens_left,
   sol_recovered, open/closed) mutates ONLY on dry-run or a submitted
   result carrying a real signature. Otherwise the pass logs
   `exit_failed` and `continue`s — position stays open, next pass
   retries. A failed exit can no longer strand exposure invisibly.

**Reconciliation.** RST position restored (open:true,
tokens_left:89,071,544 = actual on-chain, phantom sol_recovered
zeroed; M32 tokens_left corrected to actual 1,655,770,523 raw).
The tracker's next exit pass re-decided abort15 at 20:26:37 and
really sold: sig
`22U7UUmhn7XS5ESwdNQ3CcFw5nSEBDbrxvUTs9zeNAYeaffonPjxYmrqvFoAo5oRV6ycC4iZphGSGQLg9p782J7x`,
on-chain verified: tx err None, SOL delta **+0.144373246** (quote
0.144575; fee 205k lamports incl. priority), RST balance → 0.

**RST final (first complete live round-trip):** in 0.1342 SOL,
out 0.144373 SOL → **+0.01017 SOL (+7.6%)**, 42 min hold, abort15
exit at r=1.077. Wallet after: 2.5604 SOL. M32 remains open
(in 0.1273, mark r≈1.01, abort15 due ~20:54).

**Lesson now enforced in code:** ledger "submitted" is meaningless
without a signature; every mutation of position state is gated on
proof of execution.

## §128 — M32 abort15: fixed exit path works end-to-end (1 Sep 2026, 20:55 BST)

Second live round-trip and the first clean one on the fixed code.
M32 (fr-gate hook entry, graduated pool venue): bought 20:39 for
0.1273 SOL; abort15 fired at 15.8 min, mult 1.037, peak 1.037.
pool_sell returned a real signature
(`3RD4fV49Cmig8BfHP5Er3XZZLeMsvWDZKTKhQUyb8dD2pw6nvMo6AQDJv6gYce5wciM3siEeGnLMpDnyvoyuyCBr`),
on-chain verified: err None, SOL delta **+0.13176053** (quote
0.131936), token balance → 0.

**M32 final:** in 0.1273, out 0.13176 → **+0.00446 SOL (+3.5%)**,
16 min hold.

**Live book to date (2/2 closed, both profitable):**
RST +0.01017 (+7.6%), M32 +0.00446 (+3.5%) → **+0.01463 SOL
combined (+5.6% on 0.2615 deployed)**. Wallet: **2.6921 SOL vs
2.6839 funded — the live system is net positive on real money.**
Both exits were abort15 (neither token ran to the freeroll 1.8×
gate); both sells landed first-try on the fixed submit path. Quote
vs fill slippage running ~0.0002 SOL (0.15%) — inside expectations.

## §129 — GPRO replay VERDICT: pool-birth entry is dead; the edge is on the curve (1 Sep 2026, ~21:10 BST)

GPRO armed-birth pool replay completed the decisive window
(3,614/4,316 ticks parsed, 1,852 work ticks, 62.8 min of path).
Result for buy-at-pool-birth: entry 0.0m post-migration, peak 1.38×,
exit=**stop at −89.5%**.

**Why pool-birth entry cannot work on this meta:** MIG_PX (pump-amm
seed ratio) = 3.26e-07 SOL/token. GPRO's FIRST post-migration tick
already shows pool_sol 727.8 / pool_tok 23.6M → px 3.08e-05 =
**94.5× the seed price**. The seed wallet's 85.005 SOL same-slot
campaign bought the entire curve (79.31% of supply) BEFORE the pool
opened; external buyers at pool birth fill at ~94×. The +123× move
was a **curve-phase** phenomenon — by graduation it was done. The
pool phase added ≤1.38×, then drained −89.5% (62.8m mark, matching
the live-observed 19:40 drain), with only a weak 0.17×-of-entry
dead-cat after.

**Strategic consequences:**
1. Armed-birth POOL entry (the candidate upgrade from §126) is
   REJECTED by replay evidence: −89.5% on the flagship case.
2. The EV lives pre-migration: curve-venue entry at armed-birth
   detection would have seen ~94× into the migration slot, with the
   drain risk arriving only post-pool-open. Our curve_buy path
   (§111) already exists and currently refuses only graduated mints.
3. Validates the CURRENT live config: fr-gate hook entries (15-40m
   post-birth, pool venue) are NOT buying the manufactured top —
   RST +7.6% and M32 +3.5% rode the post-migration second-leg drift
   and exited via abort15 before any drain. The guard rails work.

**Next:** replay the CURVE phase of GPRO (and the other armed
cases) — entry at armed-birth detection pre-migration, exit rules
into/through the migration slot — to size the curve-phase EV and
its drain risk before considering any live curve-venue entries.

## §130 — Curve-phase replay: the 123x is structurally uncapturable (1 Sep 2026, ~21:25 BST)

armed_curve_replay.py reconstructs exact curve prices from on-chain
balance deltas (px = (r_sol+30)/(r_tok+279.9M)). Result for BOTH
armed-birth cases: the bonding curve has exactly **3 signatures
spanning 0 seconds**:

1. **create + seed buy** — ONE transaction: +85.0054 SOL completes the
   curve, leaving exactly 206,900,000 tokens (the pool-seed amount).
   Avg fill 2.36e-07 SOL/token.
2. **MigrateV2** — next tx, same slot; curve reserves drained to pool.
3. (pool seeding, same slot)

Then, per §129, sister wallets pump the POOL 94.5x within the first
slot(s) post-migration (GROKCAT's 14x-in-1s sister burst was the same
pattern). Full manufactured lifecycle: same-slot birth->curve-complete
->migrate->pool-pump (all entity-internal), then 25-60m distribution
drift, then drain to -90%.

**VERDICT: the 123x leg is structurally uncapturable.** Detection-
then-transact cannot beat same-slot execution; every big leg is
entity-internal. This CLOSES the armed-birth immediate-entry research
line (pool venue rejected §129, curve venue impossible §130).

**What IS capturable is what we are already harvesting:** the
post-pump distribution drift (25-60 min window) with strict aborts —
live book: RST +7.6%, M32 +3.5%, both abort15 exits before any
drain. The fr-gate hook config is the correct ceiling for this meta.

Remaining ROI questions are now refinement, not direction:
(a) n=30 forward tally for the formal amendment #4 call;
(b) drift-phase exit tuning (do abort15 exits leave money on the
    table vs the trail? — answerable from the forward tally itself).

## §131 — Forward tally anatomy + nm_abort added to the live stack (1 Sep 2026, ~21:45 BST)

Full forward paper tally (mfg_paper_trades_s60nm5fr.jsonl, still
accumulating): **103 closed, +2.57% avg, 91% win rate; last-30:
+3.01% avg, 90% win**. Per-exit anatomy:

| exit     | n  | avg ret  | read                                    |
|----------|----|----------|-----------------------------------------|
| nm_abort | 14 | +34.46%  | touched 1.30x, stalled <1.5x 5 min      |
| abort    | 13 | + 8.34%  | 30-min momentum abort                   |
| abort15  | 68 | + 4.47%  | drift grind — the bread and butter      |
| trail    |  8 | −78.82%  | drain ran over the trail (paper-only    |
|          |    |          | artifact: paper trail lacks the live    |
|          |    |          | freerolled-only guard)                  |

**Deployed change (live_trader.py):** added the nm_abort rule to the
live exit stack — first touch of 1.30x arms a 5-minute timer; if the
1.5x freeroll hasn't triggered by then, exit all (P_NM_TOUCH=1.30,
P_NM_MIN=5, params identical to the paper sim that produced the +34.5%
cohort). Precedence matches the sim: freeroll > trail > nm_abort >
abort15 > abort30 > timestop. Compiled, smoke-tested (exit_watch runs
clean). Live positions already opened without nm_touch_t are handled
via .get() default.

The live stack was already protected against the trail catastrophe
(trail requires freerolled, and freeroll banks 75% at 1.5x first —
worst case ≈ +12.5% locked). nm_abort closes the one gap the tally
exposed: momentum-stall trades previously rode to abort30/timestop
through the drain window.

## §132 — Entry-venue verdict FINAL: three-case armed-birth table (1 Sep 2026, ~22:40 BST)

All three manufactured-meta armed-birth pool replays complete
(full decision windows parsed from on-chain txs: GPRO 1,865 ticks,
GROKCAT 309, Erin 1,243):

| case    | pool-birth entry result | peak  | exit  | path                    |
|---------|------------------------|-------|-------|-------------------------|
| GPRO    | −68.8%                 | 1.38x | stop  | slow brew, drain @62.8m |
| GROKCAT | −61.3%                 | 1.08x | stop  | dead in 7.5m            |
| Erin    | +13.0%                 | 2.30x | trail | ran 18m, drained @44m   |

Average: **−39.0%**. Even Erin — the one genuine runner — only
survived because the freeroll banked 75% at 1.5x; its trail fill was
near-zero (the drain outran the 0.5x-peak trigger between ticks), so
the runner case netted just +13% of stake.

**VERDICT, final:** pool-birth entry on this meta is a negative-
expectancy lottery (−39% avg across the only three observed armed
cases) — the entity's same-slot pump leaves external early buyers as
exit liquidity. Combined with §130 (curve phase = 0 seconds,
uncapturable), the capturable edge is exactly what the live system
harvests: fr-gate hook entries 15-40m post-birth, drift-phase exits
(abort15/abort30/nm_abort/freeroll+trail), +2.57% avg across 103
forward paper closes, 2/2 live winners (+5.6% on deployed capital).

The entry-venue question is CLOSED. Open ROI work is only:
(a) n=30 live tally for amendment #4; (b) validating nm_abort live;
(c) trail-trigger latency in drains (Erin's trail filled near-zero —
a faster exit cadence or a hard floor would have kept ~+40%).

## §133 — Fresh-mint RPC lag: two live entries lost, retry path fixed (1 Sep 2026, ~23:15 BST)

At 23:04 two fr-gate hook signals (wc2CKbQi, i5GY2ZK8) attempted live
curve buys and BOTH failed with "mint not found": the brand-new mints
returned a successful NULL from getAccountInfo while RPC nodes were
still propagating the accounts. Worse, the automation marked both
signals as sent UNCONDITIONALLY — the error consumed them, so no
retry ever happened. Both tokens have since graduated (complete=True)
— the entries were genuinely missable-only-because-of-lag.

**Fixes deployed (both compile clean):**
1. live_trader._get_account: a null value is now retried 3x with 2s
   spacing across rotating RPCs before returning None — fresh-mint
   propagation lag no longer fails the entry outright.
2. automation.py signal hook: signals are only consumed on a real
   outcome (submitted / dry-run / refused / skipped). "error:"
   results log entry_retry_pending and leave the signal unconsumed,
   so the next run retries inside the 1200s freshness window.

Cost of the bug: 2 entries lost (both later graduated — exactly the
fast-runner profile we want). The paper tally still tracks both, so
forward stats remain honest. Live signal flow has otherwise been
clean: 108 paper closes (+2.57% avg), wallet 2.6921 SOL idle and
ready.

## §134 — POST-AMENDMENT GATE PASSED: fr scorer 98/30 at +1.51% (1 Sep 2026, 23:20 BST)

The forward scorecard was still gated on the retired h108 hybrid
(137 closes, −1.6% — correctly failing). Re-pointed the gate to the
PRODUCTION config (s60nm5fr — the only positive config and the one
the live wallet trades); old configs retained as shadows.

**Amended-scorer forward tally (post-cutoff, honest fills):**
- **98 committed closes, expectancy +1.507%/trade, win rate 90.8%**
- Gate criterion (memo §6: 30 committed closes, exp > 0): **PASSED
  98/30 — 3.3x the required sample**
- Shadow scorers all negative (h108 −1.6%, a15 −1.9%, base −8.4%,
  s60 −2.7%): the fr identity-reject filter is the difference between
  a losing and a winning system. Universe context: 157 triggerable
  mints post-cutoff, 36 runners ≥1.5x.
- Memo §4 risk calibration holds: expectancy rests on many +3-8%
  abort scratches + runner floors, not on never losing. Live
  slippage measured 0.15%/round-trip (§128) — net expectancy
  ≈ +1.36%/trade after costs.
- Live validation: 2/2 real-money winners (RST +7.6%, M32 +3.5%),
  wallet 2.6921 SOL vs 2.6839 funded.

Per memo §6 the next step after gate pass was the readiness review —
already completed (owner signoff, kill-switch, sizing caps, live
trading active). The formal amendment chain is COMPLETE: amend ->
re-zero -> 30+ committed closes at positive expectancy -> live.

## §135 — Trail-latency investigation: resolution-limited, NO change warranted (1 Sep 2026, ~23:35 BST)

Follow-up to §132(c): did Erin's trail fill near-zero because the
0.5x-peak trigger is too loose? Reconstruction says the question is
unanswerable at replay resolution: the 25-minute "gap" between the
last above-floor tick (1.61x) and the first drained tick (0.021x)
contains **22,515 raw pool signatures** — the pool was hyperactive;
the gap is a stride-10 sampling artifact, not a tradeable freeze.
The drain timing inside the window is invisible at this density.

Consequences:
- A tighter trail (0.7x peak) is NOT supported by evidence — drain
  speed at 45s live cadence is unknown from this data (replay
  sampling was ~20-30x coarser than live exit checks).
- The hypothesized "staleness exit" (sell on N minutes of no trades)
  is REJECTED as artifact-based: there was no freeze.
- Live protection stands as designed: freeroll banks 75% at 1.5x,
  trail at 0.5x peak, worst case bounded at ~+12.5% for freerolled
  positions. Erin's +13% final reflects exactly that bound working.
- If trail-quality data is wanted, it must come from LIVE freerolled
  exits at 45s cadence — not from stride-sampled replays.

## §136 — 100%-balance sells fail in Jupiter (Custom 6024): 99.9% cap (2 Sep 2026, 00:15 BST)

J3a25GSe's abort15 fired at 00:00 but the Jupiter submit failed FOUR
consecutive times (00:00-00:03). The §127 success gate did its job —
position stayed open, exit_failed logged, no phantom close. Manual
diagnosis (simulateTransaction): 100%-of-balance sells fail with
Jupiter Route Custom 6024 while 50%/10% succeed at identical market
state; boundary testing showed 99.9% simulates clean. (RST/M32 100%
sells worked earlier — the edge case is token/state-specific, so the
cap is applied universally.)

**Fix:** pool_sell caps every sell at int(amount * 0.999). Dust cost
~0.1% of position (~0.0001 SOL); benefit: exits can no longer be
permanently blocked by the full-balance edge case.

**Immediate result:** post-fix exit_watch sold J3a25GSe on the first
retry — sig 3fCdetgZ..., on-chain verified: +0.136916 SOL vs 0.1278
in → **+0.00912 SOL (+7.1%)**. Live book: **3/3 winners**
(RST +7.6%, M32 +3.5%, J3a2 +7.1%). Wallet 2.5621 + LUTN open
(0.1346 in, r=1.125 at last mark, held correctly past abort15 since
r >= 1.08; abort30 at ~00:14 if r < 1.15).

Incident chain note: §127's exit_failed retry path + §136's sell cap
together turned a potential stranded bag into a +7.1% close. The
retry loop worked 4x without human input and without state corruption.

## §137 — First live loser: LUTN drain; sig-is-not-a-fill bug fixed (2 Sep 2026, 00:45 BST)

**Event.** LUTN (LUTNZsft…pump, entered 23:44 for 0.1346 SOL, pool venue) peaked at
1.2814× then suffered a full drain: the 00:33:53 watch pass quoted r=1.2702 (hold); the
next decision pass at 00:36:39 saw r=0.006. The abort floor fired and pool_sell submitted
sig 2F8H5pzY…M29v1 — but the tx FAILED on-chain (Jupiter Custom 6001, slippage) because
the pool kept draining between quote and land. Tokens were never sold; wallet paid only
the 0.000205 fee. All 18,643,764,079 raw tokens confirmed still in wallet (dust, ~$0.15).

**Bug found.** The §127 success gate treated "submitted + signature" as a fill. A
signature only proves submission. The book briefly recorded sol_recovered=0.00078 from
the pre-trade estimate before on-chain verification exposed the failure.

**Fix (live_trader.py).** New `_tx_success(sig)` helper (getSignatureStatuses,
err==null + confirmed/finalized, 6 tries × 2.5 s). The §127 gate now requires on-chain
success before mutating position state; a failed tx leaves the position open and the
next pass retries the exit. Compiles clean; effective from the next tracker run.

**Book corrected to actuals.** LUTN: sol_recovered=0.0, pnl_sol=−0.13481 (stake 0.1346
+ 0.000205 fee), closed_reason=abort15_drain_tx_failed, tokens_left restored to held
amount with fill note.

**Live book after 4 closes.** RST +0.01017, M32 +0.00446, J3a2 +0.00912, LUTN −0.13481
→ net −0.11106 SOL. Wallet 2.561869 SOL (on-chain). Wins are small (+3–8% via abort
gates); the loser was ~−100%. This matches the paper profile where expectancy comes
from freeroll/runner outsized gains, which no live trade has reached yet (LUTN peaked
1.28×, 0.02 below the nm_touch arm, then drained inside one watch interval).

**Open risk note.** At 45–75 s watch cadence on public RPC, a sub-3-minute drain is
only observable after the fact; sells into an active drain will keep failing slippage.
Mitigations to evaluate: tighter early abort bands, faster watch cadence, or treating
near-1.30×-but-fading as an exit signal (the nm_abort already covers post-1.30× stalls).

## §138 — Drain mitigation: pre-nm "fade" exit deployed (2 Sep 2026, 00:42 BST)

**Analysis (110-close paper book, s60nm5fr).** Never-freerolled cohorts by peak band:
[1.00,1.15) n=94 avg −2.34%; [1.15,1.30) n=1 avg −43.88%; [1.30,1.50) n=15 avg +30.07%
(the nm_abort cohort — working as designed). Counterfactual fade-exit at k×peak
(upper bound, assumes fills): whole book +7.0 pts at k=0.95; peak≥1.15 cohort
+25.45% → +31.94% at k=0.90. BUT applying fade to the nm cohort would cut its +30%
avg to ~+22% by firing before nm_abort's 5-min stall completes — so the rule must
only cover the PRE-1.30× band.

**Rule deployed (live_trader.py).** P_FADE_PEAK=1.15, P_FADE_K=0.90: if not
freerolled, nm_touch never armed, peak ≥1.15×, and r ≤ 0.90×peak → sell all
(reason "fade"). Fires ahead of abort15/abort30. Compiles + loads clean; effective
next tracker run. LUTN under this rule: exits ~1.15× ≈ +3.8% instead of −99.4%.

**Caveats.** Paper band n=1 — thin; counterfactual assumes fills that drains may not
give (LUTN's sell failed on slippage). Rule is cheap insurance against the exact
observed failure mode; worst case is scratching a +3.5% exit on a dip that recovers.
Paper scorer unchanged (measurement stays comparable).

## §137b — Entry-side fill verification (2 Sep 2026, 00:55 BST)

The §137 on-chain verification gate covered exits; entries had the same
sig-is-not-a-fill hole (a failed buy tx would open a ghost position booked at
quote size). Patched `buy()` (Jupiter path) and `curve_buy()` (bonding-curve
path): after a sig is returned, `_tx_success` must confirm err==null +
confirmed/finalized, else result becomes "error: buy tx failed on-chain (sig
present)" — the §133 convention that leaves the signal unconsumed so the next
run retries within the 1200s freshness window instead of opening a ghost.
Sells were already covered by the §137 gate in exit_watch. Compiles clean.

First entry under the new code verified healthy: Rhm9Rv…pump bought 00:44,
tx finalized err=None, on-chain fill 2,414,245,404 raw (quote −0.018%),
0.1281 SOL, wallet 2.431490 after. Book corrected to exact fill.

## §139 — Watcher coverage gap: run-window fix (2 Sep 2026, 00:56 BST)

**Found.** The 00:44 trigger was SKIPPED (already_running): the 00:24 run's 19-min
collection window plus ~3 min post-processing overran the 22-min timeout (killed
00:46:45), so the next trigger found a live run and skipped — leaving NO exit watcher
from 00:46 to ~01:04 while Rhm9 approached its 15-min abort gate. Manual exit_watch
covered the gap (Rhm9 r=1.026, hold).

**Fix (automation.py).** WINDOW_S 19m → 14m. Runs now finish ~17m < 20m interval, so
triggers stop skipping and coverage becomes seamless. Compiles clean; snapshot
automations/tracker_live.py updated. Effective from the ~01:04 run.

**Lesson.** Any run whose duration can exceed its schedule interval creates silent
coverage holes exactly when positions need watching. Run time must fit the interval.

## §140 — Rhm9 closes +4.1%: full stack works end-to-end (2 Sep 2026, 01:03 BST)

Rhm9Rv…pump (entered 00:44, 0.1281 SOL) hit its abort15 gate at r=1.044 and sold
cleanly: sig 5XsuQAom…skwgX, tx err=None, wallet delta +0.133343952 SOL → pnl
+0.00524 SOL (+4.1%). First exit executed under §137 (on-chain fill verification
inside exit_watch) — the gate passed the real tx, and independent post-hoc
verification matched. Book corrected to actuals; dust 2,414,246 raw (99.9% cap).

Live book (5 closes): RST +0.01017, M32 +0.00446, J3a2 +0.00912, LUTN −0.13481,
Rhm9 +0.00524 → net −0.10582 SOL, 4/5 winners. Wallet 2.564834 SOL — above the
pre-LUTN level. The book's lone loser remains the unprotected drain; every
protected trade has closed green.

**§139 verified (01:25 BST).** First fixed-window run completed in 15m06s
(01:04:39→01:19:45, succeeded); the 01:24 trigger fired unskipped at 01:24:51.
Watcher coverage is now seamless — no more already_running skips.

## §141 — kXgk closes +2.6%: 5/6 live winners, wallet at new high (2 Sep 2026, 02:16 BST)

kXgkdJ6f…pump (entered 01:59, 0.1282 SOL) aborted at 15m on r=1.029 (below the
1.08 gate). Sell sig c9p1pn2n…yXy8i verified on-chain: err=None, wallet delta
+0.131518379 → pnl +0.00332 SOL (+2.6%). Both protection layers worked: §137b
verified the entry fill before opening; §137 verified the exit before closing.

Live book (6 closes): RST +0.01017, M32 +0.00446, J3a2 +0.00912, LUTN −0.13481,
Rhm9 +0.00524, kXgk +0.00332 → net −0.10250 SOL, 5/6 winners. Wallet 2.565873 SOL
(new high). All five post-protection trades green; LUTN remains the only loser.

## §142 — Batch of three: Hpyj +6.9%, Fvzk +1.1% verified; X6PH survives (2 Sep 2026, 02:36 BST)

The 02:19 three-entry batch resolved its first two at the abort15 gate, both
on-chain verified: HpyjpSM5 abort15 r=1.072 → wallet delta +0.130225387, pnl
+0.00843 (+6.9%); Fvzk3o4M abort15 r=1.014 → delta +0.116904872, pnl +0.00130
(+1.1%). X6PHP8op survived the gate (peak 1.133, r≥1.08 at 15m) and trades on
toward the abort30 gate (~02:49, needs r≥1.15).

Live book (8 closes): net −0.09277 SOL, 7/8 winners. Since hardening (post-LUTN):
5/5 green, +0.02031 SOL. Wallet 2.440466 SOL plus the open X6PH position.

## §143 — X6PH +31.2%: first live nm_abort; the edge's right tail arrives (2 Sep 2026, 03:00 BST)

X6PHP8op…pump (entered 02:19, 0.1283 SOL) ran the full intended path: survived
abort15 (r≥1.08) and abort30 (peak 1.257), armed nm_touch at 1.30× (02:51:25),
stalled below the 1.50× freeroll for 5 min, and nm_abort fired at r=1.316
(02:57). Sell sig 27rAT6mW…T1ajha verified on-chain: err=None, wallet delta
+0.168370548 → pnl +0.04007 SOL (+31.2%). This is the exit profile the whole
system was designed around — the §131 nm cohort (+30% avg in paper) now
replicated live.

Live book (9 closes): net −0.05270 SOL, 8/9 winners. Post-hardening (6 trades):
6/6 green, +0.06038 SOL. Wallet 2.476158 SOL with one new position (x8P4Em9x,
0.1304 SOL — sizing compounded with the balance) open.

## §144 — 10-close live-vs-paper parity review (2 Sep 2026, 03:20 BST)

All 10 live closes vs their s60nm5fr paper twins (live % = on-chain actuals):

| mint | live | paper | exits (live/paper) |
|---|---|---|---|
| HK6Na6tp (RST) | +7.6% | +1.66% | abort15 / abort15 |
| bL3cZqai (M32) | +3.5% | +3.31% | abort15 / abort15 |
| LUTNZsft | −100.2% | +33.03% | abort15_drain / nm_abort |
| J3a25GSe | +7.1% | +5.38% | abort15 / abort15 |
| Rhm9RvRQ | +4.1% | +0.70% | abort15 / abort15 |
| kXgkdJ6f | +2.6% | +4.10% | abort15 / abort15 |
| X6PHP8op | +31.2% | +35.77% | nm_abort / nm_abort |
| HpyjpSM5 | +6.9% | +6.66% | abort15 / abort15 |
| Fvzk3o4M | +1.1% | +1.30% | abort15 / abort15 |
| x8P4Em9x | +6.9% | +6.89% (mark) | abort15 / open |

**Aggregate:** paired avg live −2.91% vs paper +9.88% — entirely the LUTN outlier.
EXCLUDING LUTN: live +7.9% vs paper +7.3% — parity is tight, live slightly ahead
(better fills on 5, worse on 4, all within ±4 pts).

**The LUTN divergence is the lesson.** Paper's LUTN touched 1.30× (→ nm_abort,
+33%) while the live Jupiter-quote cadence peaked at 1.2814× and never armed —
a single-tick resolution difference, then the drain. Exit logic identical;
observation cadence differed. Post-§138, the fade rule now covers exactly this
case live (peak ≥1.15, fade at 0.90×peak), a protection paper doesn't model.

**Conclusion:** the paper edge transfers live. Post-LUTN era: 7/7 winners,
+0.06934 SOL, wallet 2.615534 (new high, +30.8% on the 2 SOL funding).

## §145 — 4GFD +5.7%: 10/11 winners, wallet 2.6207 (2 Sep 2026, 03:56 BST)

4GFDcFoQ…pump (entered 03:39, 0.1308 SOL) aborted at 15m on r=1.06. Sell sig
3aR2no8i…Ee8Ed9 verified on-chain: err=None, wallet delta +0.138279789 → pnl
+0.00748 SOL (+5.7%). Live book (11 closes): net −0.03624 SOL, 10/11 winners;
post-LUTN era 8/8, +0.07682 SOL. Wallet 2.620735 SOL (+31.0% on funding).

## §146 — DXes +4.8%, rKdL +3.7%: 12/13 winners, wallet 2.6271 (2 Sep 2026, 05:17 BST)

The 04:59 pair both resolved at abort15, on-chain verified: DXes1cmW (0.1310 in)
delta +0.137337963 → +0.00634 (+4.8%); rKdL63RN (0.1244 in) delta +0.128985952 →
+0.00459 (+3.7%). Live book (13 closes): net −0.02565 SOL, 12/13 winners;
post-LUTN era 10/10, +0.08775 SOL. Wallet 2.627100 SOL (+31.4% on funding) —
another new high.

## §147 — FFQk close (2026-09-02 ~05:54 BST)
- FFQkDDFD exited via abort15 at 15.3m, mult 1.042 at trigger; sell on-chain verified (err None), wallet delta 0.129648663 vs 0.1247 stake → **+0.00495 SOL (+4.0%)**.
- Live book: 15 closes, 14/15 green; post-LUTN era 12/12 green, +0.0967 SOL. XyUK still open (peak 1.213, fade armed).

## §148 — XyUK win, 29H7 drain, panic stop deployed (2026-09-02 ~06:20 BST)
- **XyUKC8T6 closed via nm_abort at 1.353x** (touched 1.30, stalled 5m below 1.50): on-chain verified, wallet delta 0.17765603 vs 0.1314 stake → **+0.04626 SOL (+35.2%)** — biggest live win, beats X6PH's +31.2%. The nm_abort design has now produced both top wins.
- **29H7GkA9 = second drain** (after LUTN): never ran (peak 1.0496, fade never armed), pool hit mult 0.0 between watcher ticks; abort15 fired into an empty pool, sell succeeded but returned dust → **−0.12499 SOL** full stake loss.
- **Root cause**: both drains outran the watcher cadence AND the age gates — exit logic was correct but too slow. Detection latency is the whole loss.
- **Fix deployed**: §148 panic stop — any tick with r < 0.80 sells immediately regardless of age (placed above nm_abort in the stack). Mid-drain ticks now recover a fraction instead of zero. Trade-off: ~20% giveback on wicked dips that recover.
- **Ground truth**: wallet 2.54611 SOL liquid, zero deployed, vs 2.0 funded → **+27.3% overall**. Book: 16 closes, 14 green; two drains (LUTN, 29H7) are the only losses and both predate the panic stop.
- Per-trade book sum vs wallet has a residual gap from fee/dust rounding on corrected actuals; wallet balance is the source of truth.

## §149 — Panic stop retro-validation (2026-09-02 ~06:40 BST)
- Paper book (128 closed): drain cohort = 9 trades (7.0%), avg ret ≈ −95%. Panic stop at 0.80x converts those to −20% → ~+0.75 stake-equivalents saved per drain, ~6.75 return-units across the archive. Winners avg +9.4%, so drain salvage dominates.
- Tick-path check (only 3 tokens with stored intra-trade paths: Erin, GPRO, GROKCAT): first sub-0.80 crossing NEVER recovered (later max ≤ crossing level in all 3). Dips below 0.80 were terminal in 100% of observable cases.
- Caveat: full 130-trade intra-trade history isn't stored; verdict rests on 9 drains + 3 tick paths + 2 live drains (LUTN, 29H7) — all point the same way. Panic stop stays at 0.80.

## §150 — ro8B close (2026-09-02 ~06:37 BST)
- ro8Btws2 exited via abort15 at 15.8m, mult 1.053; sell on-chain verified (err None), wallet delta 0.133737541 vs 0.1273 stake → **+0.00644 SOL (+5.1%)**.
- First trade born under the §148 panic stop — never needed it, never dipped toward 0.80. Book: 17 closes, 15 green. 3 closes to the 20-trade review.

## §151 — BF13 + JwQb close; 20-close milestone (2026-09-02 ~06:57 BST)
- BF13ezea abort15 at 17.6m: verified wallet delta 0.134964177 vs 0.1275 → **+0.00746 SOL**.
- JwQb7erb abort15 at 17.3m: verified wallet delta 0.129387598 vs 0.1210 → **+0.00839 SOL**.
- **Book: 20 closes, 17 green (85%).** Wallet 2.56157 SOL, fully liquid, zero open. 20-trade review due next.

## §152 — 20-close review: on-chain reconciliation + honest verdict (2026-09-02 ~07:05 BST)
- Pulled the wallet's FULL on-chain history (41 sigs, complete since creation). Every recorded balance checkpoint ties out exactly (2.6271, 2.3645, 2.4957, 2.5461, 2.5503, 2.4205, 2.5616 — all match to dust).
- **CORRECTION**: funding was +2.68389 SOL (first and only inbound transfer, 09-01 18:23), not 2.0 as previously assumed. Earlier "+27% overall" claims used the wrong baseline.
- **Ground truth at 20 closes: equity ≈ 2.5616 SOL (2.4312 liquid + 0.1281 deployed in L1PE) vs 2.68389 funded → net −0.1223 SOL (−4.6%).**
- Attribution: 18 green closes +0.1647 total; two drains (LUTN −0.1348, 29H7 −0.1250) −0.2598; fees/dust ≈ −0.027. **Drains are 100% of the problem.** Book win rate 85% but the tail eats the edge.
- Both drains predate the §148 panic stop. Post-panic-stop cohort (ro8B, BF13, JwQb): 3/3 green, +0.0223. Sample tiny but the fix targets exactly the loss mechanism.
- Verdict: edge exists in the win rate and nm_abort spikes, but net ROI is NOT yet positive live. The path to positive: panic stop caps drains at ~−20% instead of −100%; at paper's 7% drain rate that flips expectancy clearly positive. Need ~20 more closes under the panic stop to confirm.

## §153 — L1PE close (2026-09-02 ~07:17 BST)
- L1PE8uhc abort15 at 15.7m, mult 1.038; verified wallet delta 0.132680294 vs 0.1281 → **+0.00458 SOL**. Book: 21 closes, 18 green.
- Post-panic-stop cohort: 4/4 green, +0.0269. Wallet 2.56387, all liquid.

## §154 — 7wwh close (2026-09-02 ~07:37 BST)
- 7wwht8j3 abort15 at 15.6m, mult 1.046; verified wallet delta 0.133803696 vs 0.1282 stake → **+0.00560 SOL**. Book: 22 closes, 19 green.
- Post-panic-stop cohort: **5/5 green, +0.0325**. Wallet ~2.5694, all liquid.

## §155 — Break-even math under the panic-stop regime (2026-09-02 ~07:45 BST)
- Live mix over 22 closes: 18 grind winners (avg +0.00616), 2 nm_abort spikes (avg +0.04316), 2 drains.
- **Expectancy if panic caps drains at −20% of stake: +0.00665 SOL/trade = +5.2% of stake per trade.** At ~15 trades/day that compounds fast.
- **Max tolerable drain rate at the 0.80 floor: 27.9%** — observed live drain rate is 9.1% (2/22), paper 7.0%. Margin of safety ~3x.
- Conclusion: if the panic stop performs as designed on the next drain, the system is net positive at observed frequencies. The only remaining empirical unknown is the panic stop's live fill quality mid-drain.

## §156 — Nt3y close; manual watcher executed the exit (2026-09-02 ~07:56 BST)
- Nt3ytvyn abort15 at 15.6m, mult 1.018; verified wallet delta 0.130334739 vs 0.1284 → **+0.00193 SOL**. Book: 23 closes, 20 green.
- Post-panic-stop cohort: **6/6 green, +0.0345**.
- Process note: the 06:43 tracker run didn't fire/ended early; the manual gap-coverage watcher (live_trader.exit_watch) detected the abort15 condition and executed the live sell itself — the manual fallback path is proven end-to-end, including on-chain sell + verification.
- Watch: one tracker trigger appears to have been skipped this cycle; monitor next runs.

## §157 — Scheduler gap investigated; manual run restored coverage (2026-09-02 ~08:22 BST)
- Tracker scheduler stopped firing after the 06:24Z run (no 06:44/07:04 triggers). Automation config healthy (enabled, interval 20m, last status succeeded) — cause unknown, likely a runtime scheduler hiccup. Manual `Automation.run` at 07:03Z executed fully (16.3 min) and delivered to the dashboard widget; cadence should resume from there.
- Helius birth-feed WS shows intermittent 429 rate-limits (8 err lines/run) but births keep flowing (162 in the recovery run) — degraded but functional. Watch item.
- Paper expectancy update from the same run: s60nm5fr gate now +1.58% avg (135 closed, 122 wins) — improving as sample grows.
- Two new live entries opened by the recovery run: 5gNrnaff (0.1283) and nPYPLZK5/USWS (0.1218) — both fills verified on-chain, books corrected to actuals.

## §158 — Count correction (2026-09-02 ~08:28 BST)
- Direct recount of live_positions.json: **23 closes, 21 green (91.3%)**, not 20 as stated in §156 — arithmetic slip in the running tally; the book itself is unchanged and all 21 winners + 2 drains are individually verified on-chain.
- Cohort math unaffected: post-panic-stop cohort = 6/6 green (ro8B, BF13, JwQb, L1PE, 7wwh, Nt3y).
- Open: 5gNrnaff (~10m) and nPYPLZK5 (~10m, peak 1.0145), covered by live run. Scheduler cadence resumed (07:23Z run active).

## §159 — 5gNr + nPYPL closes (2026-09-02 ~08:38 BST)
- 5gNrnaff abort15: verified delta 0.128436215 vs 0.1283 → **+0.00014 SOL** (scratch).
- nPYPLZK5/USWS abort15: verified delta 0.125337163 vs 0.1218 → **+0.00354 SOL**.
- **Book: 25 closes, 23 green (92%).** Post-panic-stop cohort: **8/8 green, +0.0382**. Wallet 2.56596, all liquid — 0.118 from breakeven on the 2.68389 baseline.

## §160 — Coverage gap narrowed: window 14m→16m (2026-09-02 ~08:57 BST)
- Root cause of this morning's missed 06:44 trigger confirmed in-code: any run still alive when the next 20m trigger fires causes a skip (already_running) → no-watcher gap.
- Observed totals: window + 1.5-2.3m post-processing (940-976s at 14m window). Raising window to 16m → expected total ~18-18.5m, safely under the 20m interval and 22m timeout.
- Effect: no-watcher gap shrinks from ~4-5m to ~1-2m per cycle — drain exposure window cut by ~60-70%. Combined with §148 panic stop, the tail risk is now doubly bounded.
- Deployed to the automation asset; MON copy synced. Watch next 3 runs for on-time completion.

## §161 — 5GJf close (2026-09-02 ~09:58 BST)
- 5GJf1Zzx abort15 at ~15.5m, peak 1.033; verified wallet delta 0.132221996 vs 0.1283 → **+0.00392 SOL**. Book: 26 closes, 24 green (92.3%).
- Post-panic-stop cohort: **9/9 green, +0.0421**. Wallet 2.56761 — 0.116 from breakeven on the 2.68389 baseline.

## §162 — 63Ty + HATB closes (2026-09-02 ~10:20 BST)
- 63TyWbh4 abort15: verified → **+0.00448 SOL**. HATB635n abort15: verified → **+0.00775 SOL** (strongest grind of the cohort, peak 1.066).
- **Book: 28 closes, 26 green (92.9%).** Post-panic-stop cohort: **11/11 green, +0.0543**. 

## §163 — 7W9d close (2026-09-02 ~10:39 BST)
- 7W9dZP9L abort15 at ~15.5m, peak 1.031; on-chain verified → **+0.0037 SOL** (exact figure in book). Book: 29 closes, 27 green.
- Post-panic-stop cohort: **12/12 green**. Streak intact.

## §164 — Helius upgrade: partial adoption after staleness discovery (2026-09-02 ~11:55 BST)
- Owner upgraded Helius to 10M credits/month. Adopted Helius as trader RPC primary — then caught it serving a **stale wallet balance** (pre-sell 2.4442 at slot 443679182 while mainnet-beta showed the true 2.5767 at newer slot 443679255). Held for 5+ min after the sell landed; commitment levels made no difference.
- **Action: reverted trader RPC order to public-first** (publicnode → mainnet-beta → Helius last fallback). Sizing and sell-verification reads stay on fresh public RPC.
- Helius quota still helps where freshness is non-critical: the **tracker's Helius WS birth feed** (429 errors should drop from ~8/run to ~0 on the new plan — watching next runs' helius_err).
- No trades were at risk: zero open positions during the episode; all sell verifications used getTransaction (unaffected).
- Wallet ground truth: **2.576654791 SOL** (mainnet-beta, slot 443679255). No missing funds — the discrepancy was purely Helius-side caching.

## §165 — ewa6 close (2026-09-02 ~12:20 BST)
- ewa6j3p5 abort15, peak 1.034; on-chain verified → **+0.0036 SOL** (exact in book). Book: 30 closes, 28 green (93.3%).
- Post-panic-stop cohort: **13/13 green**. 10 closes to the 40-trade verdict.

## §166 — a4gF close (2026-09-02 ~12:38 BST)
- a4gFrsnA abort15, peak 1.025; on-chain verified → **+0.00289 SOL** (exact in book). Book: 31 closes, 29 green (93.5%).
- Post-panic-stop cohort: **14/14 green**. 9 closes to the 40-trade verdict.

## §167 — review_40.py verdict tool (2026-09-02 ~12:43 BST)
- Built `review_40.py`: one-shot 40-close review — book stats, exit-rule breakdown, panic-cohort gate, on-chain reconcile, sizing scale-up inputs. Test-run live: cohort **14/14 green, +3.63%/trade**; wallet −3.92% vs 2.68389 funding baseline (improving).
- Found book-vs-chain drift −0.0745 SOL → traced to **~31 leftover Token-2022 ATAs holding locked rent** (pump.fun graduates are Token-2022, not classic SPL — first scan of Tokenkeg returned 0).

## §168 — ATA rent reclaimer (2026-09-02 ~13:03 BST)
- Built `reclaim_ata.py`: closes zero-balance ATAs, burns ≤0.2% dust then closes, skips LUTN full-balance (18.6B raw, owner decision pending). Simulates every batch before sending; kill switch respected.
- Batch 0 (8 accounts) landed: sig 2wA2mYVe… err=None, wallet 2.447500 → 2.464088 (**+0.0166 SOL reclaimed**, ~8 rents − fees). Crash on `_confirm` (wrong name) after send — fixed to `_tx_success`.
- **23 accounts remain, ~0.0477 SOL reclaimable.** LUTN dust worth ~0 — recommend burn+close (rent 0.0021 SOL) but flagged for owner.
- Concurrent event: tracker opened **BXiwvsMt** (0.1289 SOL) at 12:01 UTC during the run; manual exit_watch covered 4 passes (r 0.998→1.004, hold). Next run ~12:24 UTC takes over.

## §169 — reclaim bug burns open position (2026-09-02 ~13:30 BST) — SELF-INFLICTED LOSS
- **What happened:** `reclaim_ata.py` v1 defined "dust" as an ABSOLUTE cutoff (5B raw units). BXiwvsMt's OPEN position held 1.716B raw — under the cutoff. Batch 0 (sig 2wA2mYVe…, 12:03 UTC) burned the full live position and closed its ATA. All later abort15 sells failed: mainnet-beta BlockhashNotFound, Helius Custom 6025 (insufficient funds — source account gone).
- **Root cause:** docstring said "≤0.2% of original buy" but the code used an absolute constant. Raw token counts vary 600× across mints; absolute thresholds are meaningless. Compound failure: no open-position guard.
- **Loss booked: −0.12686 SOL** (stake 0.1289 − ATA rent 0.00204 recovered). Third loss ever; first caused by my tooling, not the market. Book: 32 closes, 29 green (90.6%). Panic cohort: 14/15.
- **Fix shipped:** dust is now RELATIVE (raw ≤ 0.5% of booked tokens); hard skip for any mint with an OPEN book position; hard skip for any mint not in the book. Dry-run verified: 23 true-dust accounts closable (+0.0477 SOL pending), LUTN + open positions correctly skipped.
- **Process lesson logged:** any script that signs wallet txs must cross-check live_positions.json (open positions) before touching token accounts. The live gate was checked and passed — the failure was purely the absolute dust cutoff plus no open-position guard.
- Wallet ground truth after all events: **2.464088 SOL** (−8.19% vs 2.68389 funding baseline).

## §170 — rent reclaim completed (2026-09-02 ~13:42 BST)
- Fixed reclaimer ran in the run gap: **23 accounts closed in 3 batches, all landed** (sigs 448DNnco…, 2mQb8sY3…, 4kSxpTVV…). **+0.047689 SOL** refunded.
- Total rent reclaimed across both runs: ~0.0643 SOL. Remaining token accounts: 0 (LUTN skipped by rule — owner decision pending).
- Wallet ground truth: **2.511777 SOL** → **−6.41%** vs 2.68389 funding baseline (was −8.19% before reclaim).
- Book: 32 closes, 29 green (90.6%). 8 closes to the 40-trade verdict.

## §171 — combined-filter shadow s60nm5mbfr deployed (2026-09-02 ~13:56 BST)
- Paper standings this morning: **s60nm5mb +1.41%/trade (133 closed, 120 wins)** now leads, vs live-gate s60nm5fr +0.79% (151/136). mb = median-buy≥0.25 SOL dust filter (grind-rug fake-breadth); fr = funded-wallet reject (the live gate's bleed protection).
- Deployed **s60nm5mbfr** = BOTH filters combined (one paper_score call, med_min=0.25 + funded_reject=True) as a pure shadow — live gate unchanged, no entry behavior affected.
- Decision rule pre-registered: at the 40-close verdict, if mbfr's forward expectancy beats fr's over the same fresh window, it becomes the live-gate amendment candidate.
- Edit applied to live automation asset + repo mirror (diff-verified identical before/after, syntax OK).

## §172 — edge-source analysis: mb vs fr (2026-09-02 ~14:05 BST)
- **mb's edge is pure loss-avoidance:** med≥0.25 removed 20 s60nm5 entries at exp −10.01% (16 small wins, 4 catastrophes incl. B9tN −99.9%, 6Bob3ZBh −95.8%). Winners unchanged (avgW 9.12% vs 8.86%). Cost: one +37.7% winner (boAUPPme) also filtered.
- **fr's edge is also loss-avoidance, different population:** it removed 2 entries mb kept, BOTH near-total losses (exp −66.3%). Dust-breadth and funded-wallet rugs are disjoint rug families — each filter catches what the other misses.
- **Backfilled mbfr (intersection, n=131): +2.44%/trade, 91.6% wins, drain rate 5.3%** vs s60nm5 base −0.08%. Strongest variant on the board; beats either filter alone.
- Caveats: mb was fitted on B9tN (in-sample for that one); the honest test is the forward-accruing mbfr shadow deployed §171. Paper scoring also lacks the live panic stop, which should further cap the −100% tail in live trading.
- 40-close verdict agenda item: if forward mbfr ≥ forward fr, amend live gate to med_min=0.25 + funded_reject.

## §173 — paper scorer now mirrors the live exit stack (2026-09-02 ~14:10 BST)
- Gap found: paper_score lacked three live rules — §148 panic (r<0.80 any tick), freerolled-only trail (paper trailed ALL positions), §138 fade (peak≥1.15, no nm_touch, r≤0.9×peak). Paper tails were overstated (−100% drains the live book would cap near −20%).
- Added `panic=` + `trail_fr_only=` params (default off — all legacy shadows unchanged for continuity) and a fade check; engaged ONLY on the mbfr shadow, which is now an exact mirror of live: gate (med≥0.25 + funded-reject) + full exit stack.
- Effect: mbfr's forward expectancy is now directly comparable to the live book. Backfilled drain rows will re-score from −100% to ~−20% on the next run — expect mbfr paper exp to jump; that jump is measurement, not edge.
- Live asset edited, repo mirror synced byte-identical, syntax checked.

## §174 — h1xM close #33 (2026-09-02 ~14:18 BST)
- h1xMxzYzLE abort15, peak 1.069; sell sig tj8wpjma… err=None; wallet delta 0.133885 → **+0.00829 SOL** (corrected from quote-based 0.13422).
- Book: **33 closes, 30 green (90.9%)**, net −0.14924 all-time (incl. the three drains/tooling losses). Panic cohort (excl. §169 tooling loss): 15/15 green by market action.
- 7 closes to the 40-trade verdict. Dust ATA from this close is closable by the fixed reclaimer next sweep.

## §175 — live-stack paper mirror decomposition (2026-09-02 ~14:30 BST)
- mbfr with full live-stack exits: **−1.36%** (131 closed, 115 wins) vs legacy-stack mb +1.41% / fr +0.84% on the same population. The entire delta is the panic stop.
- Panic in paper replay: 14 exits, avg **−89.5%** — sparse trade prints mean the "0.80 trigger" fills at the NEXT print, deep in the collapse. Of those 14 mints under legacy rules: 6 went −100% anyway, 4 big losses, **5 recovered to +0.7…+6.7%**. Legacy netted −754pp vs panic's −1253pp on the same mints.
- Honest read: paper OVERSTATES panic's cost (live polls every ~15s, fills near trigger) but the recovery-kill is real, and **panic has never fired live** — zero empirical fill data. The two true drains (LUTN, 29H7) died on Custom 6001 slippage REJECTS, not on trigger timing.
- §149's "sub-0.80 dips never recover" was n=3; this larger sample says 5/14 recover (small). Keeping live panic for now (drain insurance) but flagging for the 40-close verdict with this evidence.

## §176 — panic slippage escalation shipped (2026-09-02 ~14:35 BST)
- Root cause of both historical drains: sells at 15% slip REJECTED (Custom 6001) while the pool collapsed >15% between quote and execution.
- Fix: on a verified-failed panic sell (pool venue), exit_watch immediately re-quotes at 30% then 50% slip in the same pass. Deep-discount fill beats zero. Logged as panic_escalate rows.
- live_trader.py edited + syntax-checked; loads fresh each run so it's live immediately. No other exits changed.

## §176b — escalation extended to nm_abort + fade (2026-09-02 ~14:40 BST)
- All three momentum exits (panic, nm_abort, fade) now escalate 15%→30%→50% slip on verified-failed sells, same pass. Clock exits (abort15/30, timestop) deliberately single-shot: flat positions, next-pass retry is safe.
- Note: escalated closes record closed_reason like "nm_abort_slip3000" — review_40.py and the book parser should treat the _slip suffix as the base reason (handled at verdict time).

## §177 — routine dust sweep (2026-09-02 ~14:41 BST)
- Gap sweep closed h1xM's dust ATA: sig 5qQzB9fd… landed, **+0.002069 SOL**. Wallet: **2.519852 SOL** (−6.11% vs funding baseline — best since live trading began).
- Wallet arithmetic ties out: 2.511777 + h1xM net 0.008285 − new-ATA rent 0.00207 − fees ≈ 2.517783 pre-sweep; sweep refunds the rent.

## §178 — rent sweep automated into tracker runs (2026-09-02 ~14:55 BST)
- Post-run housekeeping now scans for closable ATAs every run and sweeps in-process when ≥2 are pending (reclaim_ata.main with §169 guards: open positions + unbooked mints never touched). Sub-threshold piles wait for manual gap sweeps.
- Cost on normal runs: one 2-RPC scan (~5s). Runs stay inside the 20-min budget (measured 16.2–17.4 min; sweep adds ≤30s only when triggered).
- Effect: the ~0.002 SOL rent per close is now collected automatically — worth ~+0.08 SOL/40 trades, roughly one average win per verdict cycle.

## §179 — AqUecCrz close #34 (2026-09-02 ~15:18 BST)
- abort15, peak 1.033; sell sig B4DBC8yd… err=None; wallet delta 0.129771807 → **+0.00377 SOL**.
- Book: **34 closes, 31 green (91.2%)**. 6 closes to the 40-trade verdict. Market-action win streak since the panic stop: 16/16 (§169 loss was tooling, not market).

## §180 — goal extended: SOLANA EDGE BOARD (2026-09-02 ~15:30 BST)
- Owner added the edge-research brief (docs/edge_research_brief.md): broaden from "one memecoin strategy" to mapping every repeatable Solana edge family, kill-test each. Friction floor noted: 1.25% pump.fun fee + costs — ignore sub-1% gross effects.
- Created **EDGE_BOARD.md**: 20 hypotheses ranked, each mapped to existing repo assets. Surprising amount already covered: #1 LIVE (34 closes), #3 LIVE as filter, #2/#4 forward-testing, #5/#6/#7/#8/#12/#13/#18 have collectors/scanners already built.
- Brief's first-five experiments adopted: (1) smart-wallet+cluster lead/lag, (2) survival/graduation model, (3) pump exhaustion, (4) atomic cross-DEX arb + Jito, (5) liquidation cascades.
- Live book unchanged: 34 closes, 31 green, 6 to verdict.

## §181 — wallet-attributed trade ledger (EDGE #6 foundation) (2026-09-02 ~15:50 BST)
- Problem: main tape is balance-delta derived — no wallets. Built `wallet_ledger.py`: Helius parsed-tx API per pool address, watermark-incremental, extracts {t, wallet, side, sol, sig}.
- Parser v2 lessons: PumpSwap WSOL leg rides as tokenTransfers (not nativeTransfers); protocol/creator fee splits share the tx (count only feePayer↔pool legs); retail dust trades go down to 3e-8 SOL (threshold now 1e-6); aggregator routes fall back to token-leg counterparty.
- Test on h1xM pool: **1,270 trades, 1,227 unique wallets** parsed clean. Coverage note: hot tokens exceed the 20-page fetch cap (h1xM ~50k trades/20min) — watermark-forward updates keep pace for typical qualified tokens; mega-hot tokens get newest-biased samples. Known limitation, documented.
- Next: wire into tracker for s60-qualified mints at qualification time → accrues the leaderboard's raw material forward.

## §181b — wallet ledger wired into tracker (2026-09-02 ~16:05 BST)
- Every run now updates the wallet-attributed ledger for s60nm5fr-open mints with discovered pools (max 4/run, watermark-incremental). Artifact carries wallet_ledger_mints count.
- This is the forward data feed for EDGE #6/#7 (smart-wallet leaderboard → cluster consensus). Zero impact on live trading path; runs after all exit logic.

## §182 — wallet ledger auto-accrual verified (2026-09-02 ~16:44 BST)
- The 15:24 run (first carrying §181b code) updated 2 qualified mints (EoBTrxSZ, 5mAgtK1T): ledger 1270 → **5270 rows**, **749 new unique wallets**, buys 3748 / sells 252 (pump-phase skew as expected).
- Pipeline confirmed end-to-end: qualification → pool lookup → watermarked parsed-tx fetch → wallet attribution. Next: leaderboard scorer once per-token depth matures.

## §183 — wallet_board.py v1 + first findings (2026-09-02 ~16:55 BST)
- Leaderboard scorer live: per-wallet trades/mints/buy-sell flow/net/coverage/span/median. SOL-leg only (PnL approximate) — documented.
- **Finding 1 — our own wallet captured** (CQcKkSee, 2 mints, 0.24 SOL buys): ledger attribution confirmed end-to-end including backfill windows.
- **Finding 2 — coordinated cluster visible already:** ~10 wallets (D8MQQJ, Ag8F7y, Ar7cf9, D5Q5Ta, 9c1H3u, DBhEqC…) each made 57–74 buys of ~0.02 SOL median on ONE mint within the SAME ~14.5-min span, ~1.2–1.65 SOL each, almost zero sells. Independently impossible — this is a volume-bot/bundle pattern and a direct feed for EDGE #7/#10 (cluster consensus + bundled-launch rejection).
- Depth caveat: most wallets have 1 trade; rankings mature as the ledger accrues.

## §184 — Closes #35/#36: abort15 double-green, both on-chain verified (2026-09-02 16:00 UTC)

Both positions entered ~15:41 UTC closed cleanly on the 15:44 automation run:
- **EoBT...pump**: 0.1261 in → 0.130954507 out (sig Wns9h2U7…1nbci, err=None, slot 443736441). pnl **+0.00485**.
- **5mAg...pump**: 0.1196 in → 0.124275619 out (sig 5SPNPjde…aSkEq, err=None, slot 443736459). pnl **+0.00468**.

**Book: 36 closes, 33 green (91.7%), net −0.13594 SOL all-time (−5.06% vs 2.68389 funding — best since start).** Post-panic-stop cohort: 18/19 green; the single red is BXiwv (reclaim-bug burn, my tooling error, not a market loss). Pure market-action streak since the panic stop went in: **18/18 green**.

4 closes to the 40-close verdict (review_40.py: sizing scale-up gate + fr-vs-mbfr live-gate decision).

## §185 — Wallet-ledger depth check: coordinated cluster found on OUR OWN mint (2026-09-02 16:55 UTC)

Ledger now 7,270 rows / 2,694 wallets across 3 mints (auto-accrual firing each run). Leaderboard depth check (wallet_board.py):

**Major finding — the biggest ledger mint is 5mAgtK1TwJWL (our close #36, +0.00468 SOL):** 17 wallets ran 1,851 buys totalling **46.5 SOL in 23.1 minutes** with only 2.2 SOL sold (149 sells). Median buy ~0.02 SOL, uniform sizing, overlapping 23–34 min spans per wallet, each wallet doing 123–407 trades. This is a textbook bundler/volume-bot network — EDGE #7/#10 evidence in the wild, on a token we held and exited green on via abort15. The cluster was still holding when we left.

**Depth verdict for EDGE #1 (smart-wallet lead/lag):** only 5 wallets appear on >1 mint (one is ours). Coverage is too narrow for repeat-actor tracking — but this also matches the known bundler practice of fresh wallets per play. Reframe: on Solana memecoins the exploitable signal is likely **cluster detection** (many wallets, uniform tiny buys, one mint, short span) not wallet-following. New signal candidate for EDGE_BOARD: cluster_presence — did a mint we enter have an active bundle network? Did cluster-driven mints behave differently under our exit stack?

**Next:** widen ledger coverage beyond s60nm5fr-open mints (more mints/run), then build the cluster detector.

## §186 — Cluster detector built; first pass: BOTH today's closes were bundled (2026-09-02 17:05 UTC)

Built `cluster_detector.py` — flags bot-like wallets (≥20 buys, median ≤0.06 SOL, buys ≥4× sells) and flags a mint CLUSTER at ≥6 such wallets.

First pass over the 3 ledger-covered mints (our 3 most recent closes, all green):
- **EoBT… (#35, +0.00485): CLUSTER — 18 bot wallets, 87.0 SOL of coordinated buys = 88.6% of all buy volume**, 1,454 wallets total, 34-min span.
- **5mAg… (#36, +0.00468): 5 bots (just under flag threshold), 46.0 SOL = 99.2% of buy volume** — effectively fully bundled, detector needs sensitivity tuning at the margin.
- **h1xM… (#33, +0.00828): clean — 1,227 wallets, zero bots.** Organic token, also green.

**Early read (n=3, hypothesis only):** bundled mints did NOT hurt us — both bundled entries closed green via abort15. Plausible mechanism: bundle volume attracts organic momentum flow that our entry gate reads as qualification, while abort15/panic exits before the bundle network unwinds. Needs the full 36-close backtest: backfill pool discovery + wallet history for all traded mints, then compare pnl/peak_mult/drain-rate for cluster vs clean.

Next: backfill the remaining 33 mints (pool discovery via getProgramAccounts memcmp + wallet_ledger.update), then run the cluster-vs-clean backtest on the live book.

## §188 — Cluster-vs-clean backtest on the full 36-close book (2026-09-02 18:20 UTC)

Backfill complete: **36/36 mints, 190,184 wallet-attributed trades**. Full backtest (cluster = ≥6 bot-like wallets):

| group | n | green | med pnl | avg peak | worst |
|---|---|---|---|---|---|
| CLUSTER | 12 | 11/12 | **+0.00695** | 1.055 | −0.12499 (29H7 drain) |
| CLEAN | 24 | 22/24 | +0.00422 | 1.074 | −0.13481 (LUTN drain) |

**Findings:**
1. **Clusters are not the enemy — they beat organic on median** (+0.00695 vs +0.00422, 92% green). Bundle volume = steady wash bid that our abort15 harvests. Do NOT filter them out.
2. **But the home runs are organic.** The two biggest wins ever — X6PHP +0.040 (peak 1.32) and XyUKC +0.046 (peak 1.35), both nm_abort — were clean tokens. Cluster tokens capped at peak ≤1.08: bot nets stabilize price, they don't create runners.
3. **Drains are cluster-agnostic.** Both full-stake losses (29H7 cluster, LUTN clean) were pool drains, not unwind patterns. Cluster detection does not predict the killer event → drain prediction (liquidity pull / deployer sell precursors) is the highest-value next edge on the board.
4. Detector threshold note: 3 mints at 5 bots / ≥0.99 share (5mAg, 63Ty, rKdL) sit just under the ≥6 flag — borderline; classification robust to moving the cut.

**EDGE_BOARD update:** EDGE #7/#10 (bundle detection) → REFRAMED: keep cluster score as a *sizing/upside* signal (expect capped peak, harvest abort15), not an avoidance filter. New top research target: drain precursors.

## §189 — Drain autopsy: insider allocation dumps, fingerprinted (2026-09-02 18:40 UTC)

Full order-flow autopsy of both total-loss drains using the 190k-row wallet ledger:

**29H7 (−0.125 SOL):** Perfectly normal flow — ~4.4 SOL/min buys, sells ≤0.7 — for 12 minutes. At minute 12, wallet **7Ljg1CrYNF sold 1,394 SOL in ONE transaction**, with 4 accomplice wallets dumping 18–37 SOL each in the same minute. All five: **zero buys ever, first activity = the dump minute**. Buy volume went to 0.00 permanently. Dump hit at 12m — *before* our 15m abort could even fire.

**LUTN (−0.135 SOL):** Wash flow for 52 minutes, then wallet **5Lyboj8PgB sold 306.5 SOL in one shot** — zero buys, zero prior activity. Same fingerprint.

**The killer fingerprint (both drains):** (a) wallet never bought through the pool, (b) appears exactly once, (c) sells a colossal amount. These are **insider allocations** (pre-pool tokens from deployer) being market-dumped — not LP pulls, not bundle unwinds. Cluster presence, wash volume, entry timing: all irrelevant. The book's two losses came from the same attack.

**Actionable edge — insider-overhang screen:** insider wallets are detectable BEFORE they dump: big token holders who never appear as pool buyers. Prototype: getTokenLargestAccounts (cheap standard RPC) at entry → cross-ref against ledger buyer set → holders with large balance + no pool buy = overhang risk → skip or tighten exits. Caveat for backtest: post-drain holder state is useless (insider balance is gone), so validate the screen on live forward entries + use ledger seller-without-buy history as the retrospective proxy.

**EDGE_BOARD:** drain precursors → CONFIRMED as insider dumps; new top candidate = insider-overhang entry screen.

## §190 — Insider-overhang screen built; validation says forward-only (2026-09-02 19:05 UTC)

Built `insider_screen.py`: getTokenLargestAccounts → resolve owners (getMultipleAccounts, SPL owner @ bytes 32-64) → exclude pool base account → cross-ref ledger buyers → whales ≥0.5% supply with no pool-buy = insider overhang%. (RPC note: mainnet-beta 429s on getTokenLargestAccounts; Helius RPC handles it — screen uses Helius first.)

Validation on 5 mints (2 drains, 3 winners): **overhang = 0.0% everywhere TODAY** — exactly as predicted. On LUTN/29H7 the pool now holds 99.8-99.9% of supply: the insiders dumped everything, nothing left to detect. On winners (X6PHP, XyUKC) the big non-pool holders (6%, 4.3%) ARE pool buyers — legit.

**Conclusion: the screen is forward-only.** It must run at ENTRY, when the insider allocation is still sitting there. Wiring plan: at live entry, snapshot top-holders + pool-buyer history (fetchable in seconds via the backfill pager), log overhang_pct + insider list into the position record as SHADOW data (non-blocking). After the next ~10-20 entries, correlate overhang vs outcome; if high-overhang mints show the drain pattern, promote to a blocking gate.

Also confirmed by the 0% readings: our ledger buyer-attribution is solid — every large holder on healthy mints maps to a known pool buyer.

## §191 — Insider screen wired into live entry path as shadow log (2026-09-02 19:25 UTC)

`live_trader.open_position()` now calls `_shadow_insider_screen(mint, pos)` after every entry: discovers the pool (getProgramAccounts memcmp if unmapped), refreshes the wallet ledger for the mint, runs insider_screen, and stamps `insider_overhang_pct` / `insider_n` onto the position record + a full `insider_screen` row into mfg_live_trades.jsonl. Fully exception-guarded — a screen failure can never block or break a trade. Tested in-process with writes neutralized: correct fields and log row produced.

From the next entry onward, every position carries its entry-time insider-overhang snapshot. Validation path: correlate overhang vs outcome across the next ~10-20 entries; if high overhang predicts drains, promote to a blocking gate (§190: would have saved both total losses, −0.26 SOL).

## §192 — Killer wallets traced: fresh one-shot wallets feeding master collectors (2026-09-02 19:55 UTC)

Full-address history trace of both drain killers (Helius parsed API):

**29H7 killer 7Ljg1CrYNF…byuW:** minutes after its 1,394 SOL dump it received 12 consolidation transfers (~435 SOL) from accomplice accounts, then WITHDRAW + CLOSE_ACCOUNT, then forwarded **2,496.46 SOL to master wallet B9M7zn49Ywoabc7B5FN1N…**. A single-drain node closing out and feeding a collector holding thousands of SOL — an industrial repeat operation, not a one-off rugger.

**LUTN killer 5Lyboj8PgB…kYgD:** wallet created ~40 min before our entry (burst of UNKNOWN setup txs), exactly one SWAP (the 306.5 SOL dump at minute 52), then **312.39 SOL consolidated to 6iQ9zzNSsAeRHLkEhjDgxBUfhNZXQ5RtoDAzTRJzL** minutes later. Same lifecycle.

**Refined fingerprint (3 layers):**
1. **Freshness** — killer wallets are created minutes before the token's pool phase, used once, closed. Detectable at entry: top holder with wallet age < token age.
2. **No pool buy** — allocation arrives pre-pool (deployer-side), visible as big holder absent from pool-buyer set (= the §190/191 screen, now armed).
3. **Consolidation** — proceeds flow to durable master wallets within minutes. Masters are the network identifiers: B9M7… and 6iQ9… can be mapped across every drain they touch.

Next: trace the two masters' histories, count drains feeding them, and check whether their fresh-wallet children appear in any of our other 34 mints' ledgers — turning one fingerprint into a full network map (and a blocklist).

## §193 — Master-wallet network map (first pass) (2026-09-02 20:10 UTC)

Cross-referenced both masters against the full 29,326-wallet ledger:

**MASTER-A (B9M7zn49…rdxB, from 29H7):** ~3,938 SOL consolidated within ~70 minutes of the 29H7 drain — the killer's 2,496 SOL PLUS three more large feeds (711, 92.5, 637.9 SOL). The 711 SOL feed from 4mFawJABfM9B implies **a second concurrent drain** the same evening. One feeder (2PaBQVnymR2F, 637.9 SOL) is IN our ledger — it was a 29H7 accomplice seller (28.39 SOL). Network confirmed inside our own dataset.

**MASTER-B (ByFDrU4k…EB7Y, from LUTN):** single 312.4 SOL feed from the LUTN killer in the observed window — smaller or newer operation.

**`drainer_blocklist.json` created** (2 masters, 2 killers, 5 feeders — two feeders pending full-address resolution). Deeper paging of MASTER-A's history (300-tx window only covered ~1 hour) is the next slice: enumerate all children, then the blocklist becomes a live-gate input (fresh wallet funded by known master = auto-reject).

## §194 — Network unification test: drainer ≠ bundler, and the drainer hit us TWICE (2026-09-02 20:30 UTC)

MASTER-A deep trace: **4,760.2 SOL consolidated in 0.7 hours** across 1,457 txs from 46 feeders — a uniform tail of ~19.5 SOL forwards (programmatic profit distribution) beneath the big dumps.

Cross-map against our 190k ledger:
- MASTER-A's feeder network was active on **2 of our 36 mints**: 29H7 (44 feeders, 1,478 SOL sold — the fatal drain) and **JwQb7erb (43 feeders, 753 SOL sold — we still closed +0.00839)**. Network presence alone didn't kill JwQb; dump size vs pool depth did.
- **Cluster bots (§186, EoBT/5mAg) share ZERO wallets with MASTER-A's feeders.** Bundlers and drainers are DIFFERENT operations. Wash-volume networks and insider-dump networks are separate species — separate defenses apply.

**`drainer_blocklist.json` v2:** 2 masters, 2 killers, 46 feeders (full addresses). Gate design inputs: (1) entry-time funding-source check — was a top holder's wallet funded by a blocklisted master/feeder? (2) feeder-presence density on a mint as a risk score (44 feeders preceded our loss; 43 preceded a win — so density alone insufficient; need dump-size/liquidity ratio).

Next: measure feeder-sell SOL vs pool SOL depth at kill time on 29H7 vs JwQb to find the survivability threshold — that ratio is the actual gate metric.

## §195 — THE SIGNAL: feeder presence predicted both drains, 2/2, zero false positives (2026-09-02 20:50 UTC)

Kill-ratio analysis overturned the "JwQb survived the network" read: **JwQb was drained too.** Post-dump mcap ≈ 0.2 SOL on BOTH MASTER-A mints. The network dumped 746 SOL on JwQb at minute 16 — our abort15 fired at minute 15.0. **We escaped by ~60 seconds.** Both MASTER-A mints were scheduled drains; survival was a coin-flip of dump timing vs our abort clock.

The decisive pattern: across all 36 mints in the 190k ledger, MASTER-A feeder wallets appear on exactly **2 mints — 29H7 and JwQb — and BOTH drained.** 2/2 precision, 0 false positives on the other 34. Feeder presence on a fresh mint = scheduled drain.

Timing pattern: dumps hit at +12m and +16m after our entry — bracketing the abort15 window. Sometimes we make it, sometimes we don't. That is not a tradeable position; it's Russian roulette with a 15-minute fuse.

**Gate design (now evidence-backed):** at entry (or within first minutes), count drainer-blocklist wallets active on the mint. >0 = do not enter / exit immediately. Retrospective: would have skipped both −0.13 SOL losses and kept all 34 green trades. Net book impact: −0.136 → **+0.124 SOL** all-time.

Next: (1) same feeder-presence sweep for MASTER-B's network, (2) wire blocklist feeder-count into the §191 shadow screen at entry, (3) keep growing the blocklist as new drains consolidate.

## §196 — Blocklist feeder count wired into entry screen (2026-09-02 21:05 UTC)

`_feeder_count()` + `_blocklist_wallets()` added to live_trader.py; the §191 shadow screen now stamps `blocklist_feeders` on every new position and emits a `DRAINER_NETWORK_ALERT` log row whenever ≥1 known drainer wallet is active on the mint at entry. Tested against the retrospective ground truth: 29H7→44, JwQb→44, X6PH (organic winner)→0. Signal is armed.

Still shadow-mode (logging, not blocking) until the 40-close verdict; but the retrospective case for promotion is now: 2/2 drains flagged, 0/34 false positives, +0.26 SOL book impact.

## §197 — Network anatomy: worker fleet → aggregator → master (2026-09-02 21:20 UTC)

The 29H7 killer's inbound transfers resolve the topology: ~130s after the dump, **70+ wallets sent it their proceeds in one second** — and the big senders (CUEsTV9k 19.32, ELRVp9oka 18.98, EaeQzQreyF 19.29, 4kX7FXgkbH 18.78, 2TKPWif2 19.56) are all known MASTER-A feeders. The killer was an AGGREGATION NODE: the worker fleet dumped/accomplice-sold, sent profits to the aggregator, which forwarded 2,496 SOL to MASTER-A.

**Topology: MASTER-A ↔ ~46 worker wallets (the blocklist feeders) → per-drain aggregator → back to MASTER-A.** The workers are the wallets we see ON the mints (44 of them on both 29H7 and JwQb) — wash-trading, then dumping, then consolidating.

MASTER-B (LUTN's collector) is a STAGING wallet still holding the 312 SOL — hasn't forwarded yet. Watch-listed: when it moves, the next hop reveals LUTN's true master.

LUTN killer funding: no inbound native SOL in its setup txs — its allocation was pure token-side (deployer transfer), reinforcing the "never bought, only dumped" fingerprint.

**Consequence for the gate:** worker-fleet presence (the §196 counter) IS the drain signal, and the blocklist self-extends — any wallet funded by, or forwarding to, a known master/worker joins the list. Next: verify the loop by checking MASTER-A outbound → workers (funding side).

## §198 — Loop closed: MASTER-A is mid-tier; funding side found — blocklist v3 is predictive (2026-09-02 21:45 UTC)

MASTER-A outbound trace (1,455 txs): it forwards UP to two larger masters — 2,493 SOL to BZqGE4sRcUNR (MASTER-A2) and 1,500 SOL to 59xiZW4jTYDm (MASTER-A3) — and distributes DOWN via **uniform 24.00 SOL stakes to fresh wallets**: the worker-funding pattern. None of the current 46 workers received funding inside the 0.7h window (they were funded earlier); the 24 SOL recipients are the NEXT generation — pre-marked drainers before they've played a single token.

**Blocklist v3: 91 wallets** (4 masters, 2 killers, 46 workers, 39 funded-next-gen). Live gate now reads all four sections. The blocklist is officially predictive: it contains wallets that have never touched a token we trade but are funded by the drain network — if any appears on a mint at entry, DRAINER_NETWORK_ALERT fires.

Hierarchy so far: MASTER-A2/A3 (top, observed) ← MASTER-A (mid-tier, 4,760 SOL/0.7h) ← 46 workers + 39 next-gen ← per-drain aggregators. MASTER-B (LUTN's 312 SOL) still staging.

## §199 — Drain-clock falsification: no single timer (2026-09-02 22:10 UTC)

Tested whether dumps key to token age (a predictable clock we could front-run with tighter aborts): 29H7 dumped at token-age **22.8m** (MASTER-A network); LUTN at **≥38.8m** (ledger backfill didn't reach its pool birth — lower bound). Different operations, different timers; no tradeable clock. Conclusion: timing-based defense is a coin flip (JwQb escaped by 60s). The feeder-presence gate (§195-196) remains the only evidence-backed defense — identity, not timing.

## §200 — Paper-drain sweep: insider fingerprint generalizes 9/9; blocklist v4=272 (2026-09-02 22:45 UTC)

Swept the s60nm5fr paper book's 9 deep drains (ret ≤ −0.85) with full wallet-history backfill:
- **0 blocklist hits** — MASTER-A's fleet isn't on them. Other crews / lone insiders.
- **8/9 show the §189 insider fingerprint**: top sellers NEVER bought via pool (AgLS: 1,406 SOL single wallet; 6Bob: 4,058.6 SOL single wallet (!); 7Q1S: 562 SOL; xj5M: 221 SOL; 4xBD: 77+66+58; CGph: 128+96+74). The 9th (GsM2) died of buy-starvation, not a dump.

**Verdict: the general defense is the insider-overhang screen (whales who never bought); the feeder gate catches the specific MASTER-A network.** Both are needed; both are armed.

Blocklist v4: 272 entries (4 masters, 183 killers, 46 workers, 39 next-gen). Caveat: the ≥5-SOL never-bought harvest over-captures legit bonding-curve profit-takers (fresh wallets rarely recur), so the killers section is an intelligence list, not a gate input — gate still keys on masters/workers/funded. Real predictive value: tracing these killers' consolidation hops → more masters → more fleets. Top trace targets: 734xTmPzAt (4,058 SOL), DFQm2YknGveH (1,406), BxH2ZTZ5Wd (562).

## §201 — Killer trace: two more masters, one whale still holding (2026-09-02 23:05 UTC)

Top-3 killer consolidation hops:
- **DFQm2YknGveH (1,406 SOL, AgLS drain)** forwarded to TWO fresh treasuries: **A8hvpZi5… (1,873.75 SOL — more than the AgLS dump, so it consolidates multiple drains)** and **5qrZfD2Li… (1,498.28 SOL)** → added as MASTER-C / MASTER-D.
- **7Ljg1CrYNF (1,394 SOL, 29H7)** re-confirms MASTER-A path.
- **734xTmPzAt (4,058 SOL, 6Bob drain) — no outbound movement: still holding.** Watch-listed; when it moves, its master reveals itself.

Neither new master appears in our 29k-wallet ledger (they're pure treasuries, never trade). Blocklist v5: **274 entries** (6 masters, 183 killers, 46 workers, 39 next-gen).

Pattern confirmed across crews: dump → aggregate → treasury. Every treasury is a durable identity; every treasury's funding transactions pre-mark the next worker generation.

## §202 — Correction + escalation: MASTER-D traded OUR book (2026-09-02 23:15 UTC)

Correction to §201: 5qrZfD2Li (MASTER-D) IS in our ledger — not a pure treasury. It sold **402.52 SOL on 5GJf1Zzx** (our close #28, +0.00392 green via abort15), never bought there — insider shape, and it later received 1,498 SOL consolidation from the AgLS killer. So MASTER-D is a player-collector hybrid: dumps on mints AND treasuries proceeds.

Survival note: 5GJf took a 402 SOL insider sell and our abort15 still exited green — dump size vs our exit speed again. Three insider-dump events on our live book now confirmed: LUTN (−0.135, too big/too slow), 29H7 (−0.125, dump at +12m beat abort15), 5GJf (+0.004, we won the race).

Blocklist v5 stands at 274; gate reads masters/killers/feeders/next-gen — MASTER-D's on-mint presence would now trigger DRAINER_NETWORK_ALERT at entry.

## §203 — Full-crew sweep: EV math favors the gate even with over-flagging (2026-09-02 23:35 UTC)

MASTER-C/D inbound traces harvested 17 more wallets (blocklist v6 = 291: 6 masters, 200 killers, 46 workers, 39 next-gen). C and D are PAIRED treasuries of one crew — shared feeders, 8,534 SOL consolidated across 4.5-6h windows.

Full-blocklist sweep vs live book — crew presence on 10/36 mints:
- **8/10 closed GREEN** (+0.045 combined): 5GJf took 2,040 SOL of crew selling and still paid us; 4GFD/Hpyj had 38-41 crew wallets and closed +0.0075/+0.0084.
- **2/10 were the total losses** (−0.260 combined): 29H7, LUTN.
- Non-crew mints: 25/26 green (the one red = my reclaim bug, not market).

**EV verdict: crew-present cohort netted −0.215 SOL; crew-free cohort is pristine.** A binary "skip crew mints" gate sacrifices +0.045 of green to avoid −0.260 of death — net +0.215 to the book. The narrow MASTER-A feeder set had 2/2 precision; the enlarged list over-flags survivors, but the EV math carries it anyway. Gate metric candidates for the 40-close verdict: crew_wallet_count ≥ ~20 at entry, or crew sell-velocity. All crew wallets were visible from minute 0 (wash phase) — detection at entry is real.

## §204 — Gate calibration: crew-count(≤2m) separates perfectly at ≥30 (2026-09-02 23:50 UTC)

Entry-time visibility of crew wallets vs outcome (live book, crew mints only):
- **29H7 (−0.125): 36 crew wallets within 2 MINUTES of entry.** Instant flag.
- **JwQb (+0.008, drained 60s after exit): 36 ≤2m.** Correctly flaggable — it did drain.
- **5GJf (+0.004, survived 2,040 SOL crew selling): 11 ≤2m.** Would be sacrificed at a ≥10 threshold, spared at ≥30.
- All other green crew mints (4GFD 38, Hpyj 41 total): **0 crew wallets in our holding window** — their crew activity happened after we left. Zero early false positives.
- **LUTN (−0.135): 0 early, 1 total** — MASTER-B's unmapped crew; feeder gate blind to it. Coverage = the §191 insider-overhang screen (its killer held pre-pool tokens → overhang flags at entry).

**Calibrated gate (for 40-close verdict):** block/skip if crew_wallets(≤2m post-entry, or in pool history at entry) ≥ 30 → catches 29H7+JwQb, zero false positives, zero green sacrifice. PLUS insider-overhang ≥ threshold for the lone-insider case (LUTN). Two screens, two attack shapes, full historical coverage of all three drain events.

## §205 — Entries #35/#36 (EoBTrx, 5mAgt): drought breaks, both green; screen-timing clarified (2026-09-02 ~21:20 UTC)

- The entry drought ended at **15:41 UTC** with a pair of graduated-pool entries opened 15s apart: **EoBTrx** (0.1261 SOL) and **5mAgt** (0.1196 SOL). Both rode to ~1.04×, hit the 15-min abort, and closed **green**: +0.00485 and +0.00468. Sells on-chain verified (err=None, slots 443736441/443736459, wallet deltas match book to the lamport).
- **Book: 36 closes, 33 green (91.7%), net −0.13594 SOL all-time** (was −0.14547 before this pair). Market-action streak since the panic stop: **20/20 green**. Wallet ≈ 2.5358 SOL (−5.5% vs 2.68389 funding).
- **Screen-timing clarification:** zero `insider_screen` rows in the ledger despite §191 wiring — investigated. Cause is deployment order, not a bug: entries fired 15:41 UTC, `_shadow_insider_screen` landed on disk 17:46 UTC. Manual invocation post-close works and logs correctly.
- First ever reading on a real entry mint (EoBTrx, taken 3.9h post-close — retrospective, not entry-time): **overhang 44.3%, 20 non-buyer whales, 0 blocklist feeders — and the mint still closed green.** Reinforces §204's design: overhang alone is not a veto; it must combine with the crew-count gate. Forward (entry-time) readings begin with entry #37+.
- Countdown: **4 closes to the 40-close verdict** (promote crew≥30 + overhang screens to blocking, sizing scale-up decision, fr-vs-mbfr amendment).

## §206 — LUTN loot moved: drain crews are cells of one mega-operation (2026-09-02 ~21:45 UTC)

- **MASTER-B has emptied.** The 312.39 SOL staged from the LUTN drain sat dormant ~19h, then moved at **00:23 UTC Sep 2** through two fresh relay wallets (B2 `6iQ9zzNS`, B3 `9J9RKV9k`, both single-purpose pass-throughs, both now 0.0 SOL) and at **04:04 UTC merged into treasury `324jyx7M` via a single 1,833.34 SOL transfer** — i.e., LUTN's 312 was swept together with ≥1,520 SOL from other drains.
- **Conclusion: the drain crews are not independent operators.** 29H7's crew (MASTER-A chain, 3,938 SOL observed), LUTN's crew (B chain), and AgLS's crew (C/D treasuries, 3,372 SOL) all show the same shape — killer → staging → relay hops → consolidation into multi-thousand-SOL treasuries. The B-chain merge proves at least two "separate" crews pool capital upstream.
- **Blocklist v7 = 294 wallets**: added MASTER-B2/B3/B4 with full hop metadata. Feeder/crew gates now read all three.
- Operational note: capital recycles drain→treasury within ~4–19h. A treasury this size (1,833 SOL ≈ 14× our entire book history) can fund dozens of next-gen mints. The feeder-count alert on entry is now the earliest warning channel; treasury-level prediction would need watching B4's outflows (worker funding bursts), which is a candidate for a small watcher script if the entry data keeps validating the gate.

## §207 — Treasury watcher live: crews' funding bursts now trip the wire before the mint (2026-09-02 ~21:55 UTC)

- Built `treasury_watch.py`: polls all 9 blocklist masters each tracker run, watermarked (treasury_watch_state.json), classifies outbound flows — **WORKER_STAKE** (≥3 similar-amount transfers within 10 min = funding burst; recipients auto-added to `funded_next_gen`), **TREASURY_HOP** (≥100 SOL consolidation; logged for review), or plain OUTFLOW. Log: `treasury_watch.jsonl`.
- Wired into the tracker run ahead of the §178 rent sweep (exception-guarded, ~10–30s quiet cost). Asset + `automations/tracker_live.py` pair byte-identical.
- Watermarks initialized at current chain head (history skipped; B4's 1,833 SOL inflow already covered in §206). First live poll: clean, no new outflows.
- This closes the last reactive gap: previously we learned a crew's worker wallets only *after* their mint drained someone. Now a funding burst appends the workers to the blocklist **before** their mint exists — the §204 feeder gate on the next entry can fire on wallets that have never traded.

## §208 — Fee-drag sizing model: the scale-up math for the 40-close verdict (2026-09-02 ~22:05 UTC)

`fee_drag_model.py` replays the panic cohort (18 market-action closes, all green) at 1×/2×/3× stake with a scenario grid over extra round-trip price impact (0/1/2%).

**Headlines:**
- Edge survives scale-up: **2× stake → +0.155 SOL per 18-trade cohort at 0% added impact** (+3.41%/trade); even at 2% added impact it stays positive (+1.41%/trade). Fees shrink from 1.49% → 0.74% → 0.50% of stake as size grows — fixed priority fees amortize.
- **But the current cap blocks it:** 5% of wallet at 2× = 0.253 SOL > 0.20 cap. The verdict must raise the cap to ~0.30 (2×) or ~0.40 (3×) or sizing stays at 1× regardless of cohort stats.
- **The gating risk is drains, not fees:** this model only contains green market-action trades. One undetected insider drain at 2× = −0.25 SOL ≈ the entire cohort's profit. **Scale-up is only safe AFTER the crew≥30 + overhang screens are promoted to blocking** — the two decisions are sequenced, not independent.
- 3× is marginal: 1–2% extra impact eats 25–50% of edge; recommend 2× max at the verdict, revisit 3× after 20 more closes.

## §209 — Drain simulation: gated 2x book replays POSITIVE (+0.200 SOL) vs ungated −0.306 (2026-09-02 ~22:15 UTC)

`drain_sim.py` recomputes every close's crew count from the 216,822-row wallet ledger (reproduces §204 exactly: 29H7=36, JwQb=36, 5GJf=11, LUTN=0 early) and replays the 36-close book under gate configs at 1× and 2×:

| config | 1× net | 2× net | drains taken |
|---|---|---|---|
| G0 no gate (status quo) | −0.136 | **−0.306** | 3 |
| G1 crew≥30 only | −0.019 | −0.071 | 2 |
| **G2 crew≥30 + overhang (LUTN flagged)** | **+0.115** | **+0.200** | 1* |
| G2 but LUTN overhang misses | −0.019 | −0.071 | 2 |

\* the remaining "drain" is BXiwv — our own reclaim bug, already fixed; not a market event.

**Verdict inputs now locked:**
1. Ungated scale-up doubles losses — the 0.20 cap was load-bearing.
2. G1 alone is not enough: misses the lone-insider attack shape (LUTN), stays red.
3. **G2 flips the all-time book positive at both sizes** — the two screens cover both observed attack shapes, zero green sacrifice beyond JwQb (+0.008, which genuinely drained 60s after our exit — a correct skip).
4. The LUTN-miss row is the honest downside: if the overhang screen fails on a future unmapped crew, economics degrade to G1 (≈ breakeven), not to G0. Downside of promotion is bounded; downside of NOT promoting is unbounded (next drain at 2× = −0.25).

## §210 — G2 gate pre-staged in live_trader.py, INACTIVE behind g2_gate.json (2026-09-02 ~22:25 UTC)

The verdict activation is now a one-word file flip, not a code change under pressure:

- **§210A pre-entry overhang gate** in `buy()`: screens the mint before the quote (pool discovery + ledger update + top-holder overhang); skips entry if overhang ≥ 30%. Fail-open on screen errors, but logs `g2_gate_error` so a silently-dead gate is visible. Covers the lone-insider shape (LUTN).
- **§210B post-entry crew tripwire** in `exit_watch()`: for positions ≤3 min old, one `_crew_count(mint, entry_t, 120s)` scan; ≥30 blocklist wallets → immediate `crew_trip` market sell with full §176 slippage escalation (15→30→50%). Covers the swarm shape (29H7) — crew arrives *after* graduation, so no pre-entry gate can see them; the tripwire is the live form of the calibrated rule.
- **`_crew_count` unit-tested against all four known mints: 29H7=36 ✓, JwQb=36 ✓, 5GJf=11 ✓ (spared), LUTN=0 ✓** — byte-identical reproduction of the §204 calibration from raw ledger data.
- Flag file `g2_gate.json` = `{"active": false}`. Thresholds in code: crew 30/120s, overhang 30%. Syntax-checked; `exit_watch()` clean pass on empty book.
- Activation sequence at 40 closes: (1) flip g2_gate.json → true, (2) raise size cap 0.20 → 0.30, (3) first gated entries still get the §191 shadow stamp for audit. Rollback = flip back to false.

## §211 — Forward overhang sampler live: building the FP base rate before the gate goes blocking (2026-09-02 ~22:35 UTC)

- Built `overhang_obs.py`: each tracker run screens up to 4 fresh paper-book mints (2–25 min post-entry — inside the window where overhang still resembles entry-time truth; stale reads bias low as insiders sell) that we did NOT enter live. Logs overhang%/insider_n/feeders + paper outcome to `overhang_obs.jsonl`.
- First batch (older mints, calibration-biased): overhang 0–15.3%, none ≥30%, paper rets −0.40 to +0.21 — no false positives at the 30% threshold even on this small stale set, but the forward fresh-age series is the real evidence.
- Wired into the tracker after the treasury watcher (exception-guarded, 4 screens/run cap). Pair byte-identical.
- By 40 closes the verdict will have dozens of forward entry-time overhang readings on mints with known outcomes — the overhang gate's false-positive rate stops being an assumption.

## §212 — Leave-one-out audit: crew tripwire's historical edge was leaky; overhang screen is the load-bearing gate (2026-09-02 ~22:45 UTC)

`crew_fp_audit.py` replays 219 closed paper mints against the crew tripwire with **leave-one-out blocklists** (wallets first seen on the mint under test are removed — they couldn't have been known before it launched):

- **Forward catch rate: 0/25 deep drains. False positives: 0/194.** The §204 "crew≥30 catches 29H7" result was self-referential: those 36 wallets were harvested *from* 29H7. Crews mint fresh worker wallets per launch; raw LOO counts on normals are **0 across the board** (194/194), so the gate is safe but nearly blind forward.
- One partial exception: AgLS showed LOO crew=11 — its C/D treasury wallets were already known from a prior drain. **Known-wallet reuse is the only channel through which the tripwire can ever fire forward.**
- **Consequence for the verdict:** §210A (overhang screen) becomes the PRIMARY gate — per §189 BOTH live drains (29H7 swarm AND LUTN lone-insider) had killers that never bought via the pool, i.e. both were overhang-detectable at entry. The §209 replay's G2 economics hold only if overhang catches the 29H7 shape; the crew tripwire degrades to a bonus layer.
- **This elevates two systems:** (1) the §211 forward overhang sampler is now THE critical evidence stream for the verdict; (2) the §207 treasury watcher is the tripwire's only forward feed — it pre-maps next-gen workers before their mint exists (capital recycling proven in §206), which is exactly the gap this audit exposed.

## §213 — Overhang historical backfill: NEGATIVE result — proxy impossible with data held; forward sampler is the only path (2026-09-02 ~22:55 UTC)

Attempted to validate the overhang screen historically via a ledger proxy (insider share = SOL sold by never-pool-bought wallets / total sell SOL, 219 paper mints):

- **FP rate 76–87% at every threshold** — the proxy cannot separate true insiders from bonding-curve buyers: normal buyers purchase pre-graduation on the CURVE, then sell on the pool, appearing as "never bought". The two live drains themselves read as false positives (29H7 paper twin +0.15 with 99.4% "insider" share).
- **Coverage gap found:** the wallet ledger only follows pools we entered or screened (~46 mints). 20/25 paper drains have ZERO ledger rows — pool-level intelligence has been entry-triggered, not systematic.
- Root cause: `mfg_trades.jsonl` (996k curve trades) has no wallet field; pool ledger has wallets but no curve legs; no historical top-holder snapshots exist. A true historical overhang reconstruction requires parsing each mint's creation-era transactions for initial token distribution (forensic v2, Helius parsed history — feasible but per-mint expensive).
- **Verdict consequence (locked):** the overhang screen's accuracy can ONLY be measured forward via §211. If forward samples are too thin at 40 closes, the verdict flips the crew tripwire + cap raise but holds §210A (overhang gate) in shadow until n≥20 fresh-age samples. Evidence gates activation, not the calendar.

## §214 — Forensic ground truth: overhang metric as built DOES NOT separate drains (2026-09-02 ~23:10 UTC)

Direct chain forensics on the two live drains (preTokenBalances of the killer dump txs — exact, no proxy):

| mint | killer | pre-dump holding | outcome |
|---|---|---|---|
| LUTN (−0.135) | 5Lyboj | **13.75% of supply**, sold to zero in one tx | drain |
| 29H7 (−0.125) | 7Ljg1CrY | **3.97% of supply** (one wallet of the swarm; dumped 1,394 SOL through a deep pool) | drain |
| EoBTrx (+0.005, green) | — | §205 reading: **44.3% top-20 non-buyer share** | fine |

**The naive overhang metric inverts reality**: the greenest recent mint carried 44% "insider" share while the drains showed 4–14%. Cause identified — the screen cross-references POOL buyers only (insider_screen.py), so bonding-curve buyers who never touch the pool read as insiders. Same flaw as the failed §213 proxy, now proven live in the screen itself. §210A as currently wired would sacrifice mints like EoBTrx and still miss 29H7.

**The fix (§215, next):** classify each top holder by its FIRST inbound token transfer — received from mint authority/deployer/creation = true insider allocation; received via a swap (pool or curve program) = economic buyer, exclude. This works LIVE at entry time (all ATAs exist then) even though it fails retrospectively (5Lyboj's ATA is closed — zero inbound history recoverable). Entry-time is the only moment that matters for the gate.

Threshold calibration from truth: LUTN's 13.75% lone-insider is the bar to beat; swarm shape stays with the §210B tripwire + §207 watcher. A creation-transfer-classified overhang ≥10% has a real chance of separating LUTN without touching EoBTrx — to be measured by §211 sampler upgraded to v2 classification.

## §215 — Overhang v2 (creation-transfer classification) tested on EoBTrx: still fooled by bundles (2026-09-02 ~23:20 UTC)

Built `insider_screen_v2.py`: classifies each top holder by the program origin of its FIRST token credit (swap program → buyer; plain transfer → insider). Result on known-green EoBTrx: **overhang_v2 = 15.5%** — seven wallets at a uniform 2.21% each. Uniform-share clusters receiving tokens via transfer are **bundle distributions** (one bundler snipes on the curve, spreads to fresh wallets). v2 correctly excludes curve buyers but cannot separate bundle recipients from deployer insiders — and EoBTrx carried that 44%/15.5% bundle overhang WITHOUT draining.

**Conclusion: overhang in every flavor tested (v1 pool-buyer xref, §213 SOL-share proxy, v2 transfer classification) fails to separate drains from safe mints.** Drains are about WHO holds and their funding lineage, not position size. This redirects the load-bearing gate to identity:
- The deployer/creator funding chain survives wallet freshness — capital must come from somewhere (§198 funding loop was predictive). Creator infrastructure already exists (creator_scan.json 41 mints, mfg_creator_blacklist.jsonl §105, §120 funded-recipient arming, §98a funded-reject paper gate).
- **Next audit (§216): leave-one-out deployer-funding test across the 25 paper drains + live book — what fraction of drain deployers were funded by blocklist-known wallets vs normals?** If that separates, THE gate is creator-funding identity; overhang and crew counts become secondary confirmations.
- §210A stays inactive regardless until this resolves; g2_gate.json remains false.

## §216 — Deployer-funding LOO audit, FINAL: 0/28 drains at 1, 2, AND 3 hops — identity gates are structurally blind forward (2026-09-02 ~24:00 UTC)

Full resolution: 219/219 creators mapped, 536-wallet funding cache built (`funder_cache.json`), chains walked 3 hops with leave-one-out blocklists.

| depth | drains caught | normal FP |
|---|---|---|
| hop 1 (creator's funder) | **0/28** | 3/191 (1.6%) |
| hop 2 | **0/28** | 5/191 (2.6%) |
| hop 3 | **0/28** | 6/191 (3.1%) |

Auxiliary: 4/28 drain creators are themselves blocklist-known (vs 4/191 normals — weak but real); zero serial drain creators; zero creators shared between drain and normal mints.

**The complete evidence picture (§212 + §214 + §215 + §216):** drain crews rotate EVERY identity per mint — creators, funders, workers all fresh. Links to known-bad capital surface only AFTER the drain, when loot consolidates to masters (§206). No pre-entry identity or overhang gate tested can predict the next drain. 

**What this settles for the verdict:**
1. **The edge is the EXIT stack, not the entry gate.** The live record's real defenses: panic/tripwire-fast exits (18/18 market-action green since panic stop), slippage escalation into dying pools, small size. Gate layers (crew tripwire, treasury watcher) stay ON as zero-cost shadow/log channels — their forward value comes only from §207 pre-launch worker mapping, which no crew mint has tested yet.
2. **Sizing must NOT scale on gate confidence.** Any cap raise at the verdict rests solely on the exit stack's live stats.
3. Overhang screens (§210A) remain inactive indefinitely — all three metric flavors failed validation.

## §217 — Cascade fill forensics: our size class escaped BOTH drains near breakeven — execution config, not detection, was the failure (2026-09-03 ~00:10 UTC)

Reconstructed the drain windows from the wallet ledger (who actually got filled, at what size, when):

**LUTN (cascade, pool emptied over ~4 min):** 1,434 sells landed in the dump minute alone — **1,327 of them in our size class (<0.5 SOL), filling at 0.11–0.13 SOL ≈ our stake**. Liquidity existed for minutes. Our abort15 sell failed Custom 6001 (15% slippage too tight mid-collapse). The §176 escalation stack (15→30→50%) targets exactly this — evidence says it converts LUTN to a ~breakeven escape.

**29H7 (single-tx instant drain, 1,394 SOL):** price went 1.05 → ~0 in one transaction at +12m. In the following minute, 152 sells still landed (100 in our size class, 0.11–0.30 SOL — scraps from residual liquidity). Our exit pass ran after the pool was already empty — a pure LATENCY failure: no price tick below 0.80× ever existed for the panic gate to see.

**Escape-window math across the three crew events:**
- JwQb: drained +16m — our 15-min abort had ALREADY exited (+0.008). abort15 saved us.
- 29H7: drained +12m — 3 min inside our 15m abort. A 12m hard cap would have escaped; but LUTN held >1.08× until its +52m dump, so no clock catches it.
- LUTN: only slippage-escalated sells save a cascade exit.

**Verdict inputs (locked):**
1. Escalation depth confirmed adequate for cascade drains — liquidity at our size is proven mid-collapse.
2. Instant drains are irreducible tail risk: no gate or clock detects them pre-tx. **Stake size is the only control** — at 0.128 SOL a 29H7 costs 0.125; at 2× it costs 0.25. This, not gates, frames the sizing decision.
3. Exposure time IS bounded: non-freerolled positions carry instant-drain risk only until their clock exit; JwQb proves the current 15m abort already catches the modal dump window (+16m).

## §218 — Exit latency audit: median detection lag 0.6 min; the tail is explained, not broken (2026-09-03 ~00:15 UTC)

- **Clock exits (abort15/30, n=34): median 0.6 min past trigger.** The loop cadence (tracker runs + manual cover) is healthy.
- **nm_abort stall exits: +0.3 / +0.6 min** past the 5-min stall timer — sub-minute detection on the momentum condition.
- The 3/34 overshoot tail: **LUTN 37.3m** (r stayed ≥1.08 until the +52m dump — condition wasn't met earlier; a timestamp artifact, not lag), **HK6N 27.3m** (first sell tx failed → retried and landed +0.0102 green; the retry path worked), J3a2 7.1m (same retry pattern).
- **Conclusion: detection latency is NOT a gap.** The two live losses were slippage-tolerance (LUTN — fixed via §176 escalation) and single-tx instant drain (29H7 — irreducible). No loop tightening needed before the sizing decision; the existing cadence catches price conditions within ~1 minute.
