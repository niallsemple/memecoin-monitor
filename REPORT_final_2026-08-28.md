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
