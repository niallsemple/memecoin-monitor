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
