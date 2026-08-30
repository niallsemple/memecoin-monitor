# TEN MORE PLAYS + WHERE TO GO NEXT
**Darwin Labs AI · 28 Aug 2026 · follow-up to BIG_BOYS_PLAYBOOK.md after the
§47 null (fresh-wallet bundle fingerprint is extinct — pros age wallets now)**

Selection rule for this list: every play must (a) attack a mechanism the pros
actually use, (b) be testable with data we can genuinely obtain, and
(c) carry a pre-registered kill criterion. No astrology.

---

## 1. Bonding-curve momentum scalping (the pre-graduation arena)

**Mechanism:** Inside the pump.fun bonding curve — *before* graduation — the
latency bar drops from milliseconds to seconds, and the curve's price math is
deterministic (known reserves → known price). Pros scalp curve velocity:
accelerating buy flow + rising unique buyers = graduation-bound; stalling
curve = dead. Only ~1% graduate, so the filter IS the trade.

**Our version:** Stream curve state via gRPC (or poll at 2–5s), compute
velocity features (buys/min, unique buyers/min, curve %/min), enter curves
crossing 60–80% with acceleration, exit into the graduation event or on
velocity break. No slot-0 race needed — the decision window is minutes.

**Test:** replay against our 500-tag live dataset (we have minute-scale
history). **Kill:** if velocity-at-60% doesn't separate graduates forward, stop.

## 2. Aged-wallet farm mapping (indexer-grade bundle detection)

**Mechanism:** §47 proved bundles no longer use fresh wallets. Volume/MM
services advertise "aged, funded wallets" — inventory funded weeks ahead.
The bundle signature moved from wallet age to *shared funding age + shared
funder + synchronized dormancy*.

**Our version:** this needs full wallet history, which paginated RPC can't
cheaply give. Rent indexer access (SolanaFM, HelloMoon, or BigQuery's public
Solana dataset) and map: wallets dormant 1–8 weeks that wake simultaneously
at a token's birth, clustered by original funder. That cluster IS the modern
bundle — detectable before distribution starts.

**Test:** rebuild the §47 cohort comparison with indexer data.
**Kill:** if aged-cluster presence still doesn't separate winners, the
bundle-follow thesis dies permanently and we keep detection-only value.

## 3. Serial-deployer tracking (creator reputation)

**Mechanism:** Repeat launchers have measurable hit rates. A deployer whose
last two tokens ran 10× gets front-run on their third by everyone watching —
and the deployer knows it. Creator address → outcome history is public;
GMGN surfaces it; almost nobody systematizes it.

**Our version:** extend the pipeline to record every token's creator address
(already in the feed), build creator → outcome base rates from our 500-token
live sample, and alert when a top-decile creator launches. This is the
cleanest "follow the proven winner" trade left, and it survives entity
rotation because reputation attaches to the deployer, not the buyer cluster.

**Test:** historical creator→outcome table from state.json (zero new data
cost). **Kill:** if top-creator forward hit rate ≤ base rate, drop.

## 4. Social-velocity leading indicator

**Mechanism:** Trending rank weighs holders/volume, but the *leading* signal
is off-chain: X mention velocity, Telegram join rate, dexscreener page
interaction. KOL-driven pumps (our §45 igniter) show social acceleration
minutes before on-chain volume.

**Our version:** lightweight scraper/API for X search counts + TG member
counts on audit-passed tokens; alert when social velocity crosses threshold
while price is still flat. Pairs with playbook-1 play #6 (ignition
following) — this is its detection layer.

**Test:** can we timestamp social spikes vs the 4978aTN9 09:00Z ignition
retrospectively? **Kill:** if social spikes lag price, the signal is
decoration, not edge.

## 5. Migration price-dislocation capture

**Mechanism:** At graduation, the bonding curve's terminal price and the
first PumpSwap AMM prints routinely dislocate. The slot-0 bots fight over
the *first* print; the dislocation between curve-implied price and early AMM
quotes persists for seconds-to-minutes — a slower, less crowded window.

**Our version:** monitor graduations (deterministic on-chain event), compute
curve-terminal vs AMM-implied price, take the convergence trade when the gap
exceeds fees + slippage. Seconds-scale, not milliseconds.

**Test:** measure gap distribution across 100 recent graduations.
**Kill:** median gap < 2× round-trip cost.

## 6. Meta-rotation positioning (narrative lifecycle)

**Mechanism:** Memecoin capital rotates through narrative metas (animals →
AI → politics → celebrity…). Pros position in the *next* meta's early
launches when the current meta saturates — saturation is measurable: falling
median peak, rising launch count, shortening attention span.

**Our version:** NLP-cluster names/descriptions on our new-pairs feed
(already ingested), track per-meta launch count + median peak + median
time-to-peak daily. The rotation signal is meta-level, not token-level —
which sidesteps every per-token noise problem we hit in §1–§46.

**Test:** reconstruct meta stats for the past week from state.json.
**Kill:** if meta medians don't lead token-level outcomes, drop.

## 7. Sniper-dump wick buying (mechanical seller exploitation)

**Mechanism:** Thousands of sniper bots exit at fixed rules (+50%, +100%,
or +N minutes). Their synchronized mechanical selling creates predictable
wick-downs at +5–15 min on tokens whose organic demand is real. Pros with
patience buy the bot-exit wick from the bots.

**Our version:** from our minute-scale history, identify the wick pattern
(sharp −25–40% print on flat holder growth, immediate absorption), enter on
absorption confirmation, exit into the second leg. Our audit gates filter
out tokens where the wick is just death.

**Test:** wick→recovery base rate on the 500-tag sample.
**Kill:** recovery rate < 50% after audit+holder filters.

## 8. Funding-rate capture on memecoin perps

**Mechanism:** Once a memecoin gets a perp market, degenerate longs pay
funding to shorts. Structural, direction-neutral: long spot + short perp,
harvest funding. This is how desks extract yield from the casino without
picking winners.

**Our version:** monitor new perp listings of surviving memecoins, enter
basis position when funding > threshold, exit on funding flip. Lowest-
variance play on either list after DLMM farming.

**Test:** funding-rate history on recent memecoin perps (Drift/Hyperliquid
data). **Kill:** funding < borrow+fee drag on average.

## 9. Liquidation-cluster fishing

**Mechanism:** On memecoin perps, leverage clusters at obvious levels.
Whales push price into liquidation cascades; resting bids below the cluster
catch the cascade wick — a known, structural fill.

**Our version:** open-interest + liquidation-map monitoring on listed
memecoin perps; resting limit orders below dense clusters with tight
invalidation. No prediction needed — the liquidations are pre-committed.

**Test:** cascade frequency/depth stats on the top 10 memecoin perps.
**Kill:** fills average slippage beyond the wick (catching knives).

## 10. Audit-latency arbitrage (flag propagation timing)

**Mechanism:** RugCheck/GoPlus flags propagate to aggregators and bot
blacklists with minutes of lag. When a token gets flagged, the dump follows
the *propagation*, not the flag. Everyone holding gets exit warnings at
different times; the informed exit first.

**Our version:** we already run both audit engines live. Track flag-state
changes per token on a fast poll; the instant a held/tracked token flips
flagged, exit before aggregator propagation — or, productized, sell the
flag-flip alert (feeds playbook-1 play #10). Pure latency value from
infrastructure we already own.

**Test:** measure flag-flip → price-impact lag on historical flagged tokens.
**Kill:** lag < our poll interval (no propagation window exists).

---

# WHERE TO GO NEXT — the decision map

**Tier 1 — start this week (zero/minimal build, fit verdict B):**
1. **DLMM fee farming pilot** (playbook-1 #7): small capital, survivors only,
   measures itself in a week. The only play that pays us while we research.
2. **Serial-deployer tracking** (#3 above): free — pure reanalysis of
   state.json. If top creators show real base rates, this becomes the primary
   signal feed.
3. **Shovels MVP** (playbook-1 #10): cluster tags + flag-flip alerts as a
   Telegram bot. Monetizes proven infrastructure; zero market risk.

**Tier 2 — two-week builds (extend current stack):**
4. **Bonding-curve momentum replay** (#1): backtest against our own
   500-token minute-scale history — the data is already on disk.
5. **Social-velocity layer** (#4): detection layer for the ignition trade.
6. **Sniper-wick study** (#7): pattern stats from existing history.

**Tier 3 — spend money only after Tier 1/2 evidence:**
7. **Indexer subscription** → aged-farm mapping (#2): the real fix for the
   §47 null. ~£100–400/mo. Only if deployer tracking (#3) shows provenance
   signals matter.
8. **Latency benchmark** → slot-0/MEV (playbook-1 #1/#8, #5 above): rent
   co-lo for one month, measure our landed-slot distribution on paper.
   If we're not landing slot 0–1 on >50% of attempts, we never pay to race.

**Permanently excluded:** being the deployer (playbook-1 #9) — UK legal
exposure. Detection-only, forever.

**The honest meta-lesson from 48 hours of research:** every per-token
prediction edge we tested died forward (H10 cascade, momentum spray,
behavioral gates, bundle fingerprint). Every *structural* play survived
scrutiny (defensive gating, fee farming, shovels, provenance tracking).
Trade structure, not prediction.
