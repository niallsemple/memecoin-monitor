Yes. After going deeper, I think there is a more fundamental problem than “we haven't found the right memecoin signal yet.”

## The biggest thing you're missing

We have mainly been trying to model:

**observable token behaviour → future price**

I think the real system needs to model:

**cause → participant → intent → transaction → execution → observation → attention → reaction → price**

By the time we're measuring volume, holder growth, smart-wallet buys, transaction velocity and price acceleration, **the information that caused those things has already entered the system**.

The next generation of DARWIN should therefore be an **information-flow model of Solana**, not merely a memecoin predictor.

And my research today turned up several things that materially change how I'd build it.

---

## 1. Some of the activity we're training on isn't organic at all

This is more serious than I initially realised.

Pump.fun now has **Mayhem Mode**. In Auto mode, Pump explicitly says its agent has a *self-exciting trade cadence*: more user trading can cause more agent activity. It randomly buys and sells in varying sizes. In Manual mode, the creator decides when to trigger the agent transaction. ([Pump][1])

Mayhem tokens also have a different supply structure: 2 billion tokens rather than the normal 1 billion, with 1 billion allocated to the trading bot. Crucially, the bot's transactions **don't pay Pump platform or creator fees**. ([Pump][2])

Imagine what that does to our features.

We observe:

`transactions accelerating`
`volume accelerating`
`dip being absorbed`
`activity responding to activity`

and conclude:

**ORGANIC MOMENTUM.**

But part of what we're measuring can literally be an automated platform mechanism designed to generate volatility.

There's more. Pump's Tokenized Agents can perform **hourly automated buyback-and-burn transactions**, funded by assets sent to the Agent Deposit Address. ([Pump][3])

So the first thing DARWIN needs is something we haven't discussed much:

### A Mechanism Registry

Every observation needs labels such as:

`STANDARD_PUMP`

`MAYHEM_AUTO`

`MAYHEM_MANUAL`

`AGENT_TOKEN`

`CASHBACK`

`CTO`

`CHARITY`

`SOL_PAIR`

`USDC_PAIR`

`BONDING_CURVE`

`CANONICAL_PUMPSWAP`

`NON_CANONICAL_POOL`

Without this, we're potentially combining **different species of market** into one training set.

---

# 2. We're probably missing the market *before* the blockchain history

This could be the biggest technical limitation of all.

Historical Solana data tells us what landed and in what order.

It does **not** reconstruct exactly:

> **When would our particular trading system have learned about this transaction?**

That's completely different.

Current Solana infrastructure now exposes an observation ladder. Helius' new preconfirmations are emitted when a leader executes a transaction, **before it has been turned into shreds and propagated through the network**. Raw shreds come afterwards, and ordinary processed/RPC observation later still. Preconfirmation coverage is not complete, so later feeds are still required as fallback. ([Helius][4])

This means the same strategy needs to be tested as:

$$
EV(signal \mid observation\ layer)
$$

For example:

`confirmed data → -3% EV`

`processed → -1%`

`shreds → +1%`

`preconfirmation → +5%`

Or the reverse.

We don't know.

### Historical backtesting alone cannot answer this correctly.

We need to start accumulating a **live forensic tape**.

Every event should have at least two times:

**CHAIN TIME** — where it occurred.

**OUR OBSERVATION TIME** — when DARWIN actually received it.

And preferably:

`preconf_receive_ns`

`shred_receive_ns`

`websocket_receive_ns`

`parse_complete_ns`

`feature_complete_ns`

`decision_ns`

`tx_constructed_ns`

`tx_sent_ns`

`leader_received/estimated`

`landed_slot`

`actual_fill`

That produces something we haven't had before:

## an honest replay of what DARWIN actually knew.

And there is a very current infrastructure issue here. Jito says ShredStream is being completely shut down on **September 5, 2026 — today** — and recommends migration to DoubleZero Edge for shred access. ([Jito Labs Documentation][5])

So I would audit our data transport now, even before another model experiment.

---

# 3. “Profitable wallet” may be the wrong unit of analysis

This one could undermine quite a lot of wallet research.

We've generally considered:

$$
WalletPnL = Selling - Buying - Costs
$$

But participants can make money in other ways.

Pump creators receive part of every trade's fees. On the bonding curve that's currently **0.30% of each transaction**, while the creator portion of canonical PumpSwap fees can rise as high as **0.95%** in some market-cap tiers. ([Pump][6])

Pump also now supports CTOs that can redirect control of creator fees, while Cashback Coins can redirect some or all creator fees back to eligible users. ([Pump][7])

And at the infrastructure level, transactions can even generate **MEV rebates**. Helius, for example, offers an opt-in backrun auction that returns 50% of the resulting MEV to the user's rebate address. ([Helius][8])

Therefore:

**swap P&L ≠ economic P&L.**

A creator might never dump their token and still monetise enormously through fees.

A wallet could appear mediocre while belonging to an economic entity earning creator revenue somewhere else.

A participant could trade almost break-even because their real economics come from another cash flow.

So replace:

### Wallet Intelligence

with:

# Economic Entity Intelligence

DARWIN should attempt to reconstruct:

$$
EconomicPnL =
TradingPnL
+ CreatorFees
+ Rebates
+ Cashback
+ OtherTokenFlows
- NetworkCosts
- Tips
- InfrastructureCosts
$$

across a probable wallet cluster.

That may completely reorder which actors we consider “smart money.”

---

# 4. Our backtests may be violating the market's own physics

Pump's bonding curve is a constant-product AMM. Every buy changes its reserves and raises the subsequent price; every sell changes them in the other direction, and price impact increases with transaction size. ([Pump][9])

Therefore this backtest:

> Historical price = X
> DARWIN buys 3 SOL at X
> Continue replaying historical prices.

isn't really valid.

**Our transaction would have changed X.**

More importantly, subsequent participants would have encountered a different curve state.

We need two levels of replay.

**Mechanical counterfactual:** insert our hypothetical transaction into the exact AMM reserves and recompute subsequent fills mechanically.

**Behavioural uncertainty:** acknowledge that once we've changed the state, we cannot know whether all subsequent humans/bots would have behaved identically.

That means the metric we've been using in many strategy searches — MFE — needs upgrading to:

# Realisable MFE

Not:

> “The chart subsequently went +32%.”

But:

> “Given a 1-SOL position, actual curve depth, our entry impact, fees, realistic latency and the liquidity available during the move, how much of that +32% could actually have been extracted?”

That's a much harder test.

But it's the only number we care about.

---

# 5. We're tracking addresses when we should be fingerprinting actors

There is now external academic evidence supporting exactly the direction we discussed.

A July 2026 study examined **586 Solana bot GitHub repositories, 200 identified bot addresses and more than 44 million on-chain transactions**. The researchers found observable differences in on-chain behaviour and execution fingerprints across bot categories. ([arXiv][10])

That suggests the next wallet system shouldn't primarily ask:

> Is wallet `ABC...xyz` profitable?

It should ask:

> **What actor family generated this transaction?**

Imagine DARWIN learns:

`address changes`

but:

`transaction construction`

`instruction sequence`

`CU behaviour`

`priority behaviour`

`trade-size distribution`

`timing`

`funding pattern`

`holding period`

`co-occurring actors`

all remain recognisable.

Then twenty addresses may collapse into:

### ACTOR_CLUSTER_147 — momentum bot family.

Now we can study something far more interesting:

$$
P(Actor_B\ arrives\ next \mid Actor_A,state)
$$

Instead of trying to predict price directly.

DARWIN might eventually learn:

> When Actor 17 enters and Actor 31 remains after the first sell, Actor 9 appears within 15 seconds 68% of the time.

And perhaps Actor 9's arrival causes the expansion.

Then we can potentially position **before the actor we're currently copying**.

That's the progression I want:

`copy wallet`

→ `understand wallet`

→ `identify strategy family`

→ `predict strategy-family behaviour`

→ **predict their next action.**

---

# 6. We're missing *attention placement*

Look at Pump.fun itself today.

Its Explore interface isn't simply a chronological list. It exposes categories including **Movers, Mayhem, New, Charities, Live, Market Cap, Agents, Oldest and Last Trade**. ([Pump][11])

This means the thing we're trying to predict — buying — could partly be caused by **where a coin becomes visible to humans**.

The causal chain could be:

`activity increases`

→ **Pump ranking changes**

→ token appears prominently on Movers

→ thousands more users see it

→ buyers arrive

→ volume rises

→ DARWIN sees volume acceleration

We then conclude:

> volume acceleration predicts returns.

It might.

But we've missed the intermediate mechanism:

# visibility.

That's potentially a better signal because it occurs closer to the cause.

We should record the platform surfaces continuously:

`rank on Movers`

`rank on New`

`rank on Mayhem`

`Live status`

`Agent status`

`Market Cap rank`

`number of positions moved`

`time entered visibility zone`

`time left visibility zone`

Then run event studies around **rank transitions**.

This isn't just Pump either.

A complete memecoin model should eventually understand:

**on-chain capital + terminal visibility + Pump visibility + social attention + narrative competition.**

---

# 7. We're looking for smooth patterns when structural discontinuities may be much easier

This may be an important new DARWIN philosophy.

Instead of mining endless patterns, hunt for places where the **rules mechanically change**.

Pump gives us several.

Graduation automatically transitions a token from the bonding curve to PumpSwap. ([Pump][9])

Canonical PumpSwap transaction fees change at explicit market-cap thresholds, from 1.25% at the smallest tier progressively down to 0.30% for sufficiently large SOL-paired coins. ([Pump][6])

Mayhem operates only during a specific early lifecycle and then ends/burns remaining bot-controlled supply. ([Pump][2])

Tokenized agents conduct buybacks hourly. ([Pump][3])

Those give us natural event boundaries.

Instead of:

> Find any combination of 100 indicators that predicts +20%.

test:

$$
Return(t-30s,t+30s)
$$

around:

**fee-tier crossing**

**graduation**

**Mayhem termination**

**agent buyback**

**visibility-rank crossing**

**CTO change**

These are much less arbitrary hypotheses.

And they have an actual mechanism behind them.

---

# 8. Execution competition isn't simply “the Solana network is busy”

It's even more local than that.

Jito currently runs parallel auctions roughly every **50 ms**. Transactions/bundles whose read/write locks intersect compete in the same local auction; non-conflicting transactions can effectively compete separately. Ordering within an auction depends partly on tip efficiency relative to requested compute. ([Jito Labs Documentation][12])

Solana itself also includes write-lock costs and compute requirements in scheduling priority. ([Solana][13])

So a global metric like:

`network congestion = HIGH`

is too coarse.

We need:

### opportunity-specific contention.

For the exact curve/pool we're trading:

`how many competing tx?`

`which accounts locked?`

`priority-fee distribution?`

`Jito-tip distribution?`

`number of competing bot families?`

`landing probability at our bid?`

`expected cost of moving one execution percentile faster?`

Then we can solve another problem:

$$
OptimalFee =
argmax_f[P(land|f)\times EV(fill)-f]
$$

Instead of blindly overpaying for priority.

Execution itself becomes an ML problem.

---

# 9. We may be measuring the wrong target

This is another issue I would change immediately.

Don't primarily predict:

`future return`

or even:

`will this be a winner?`

Predict:

$$
P(+20\%\ before-8\%\ |\ information_t)
$$

and:

$$
P(+50\%\ before-15\%)
$$

and:

$$
P(exit\ liquidity\ remains\ sufficient\ when\ target\ hit)
$$

and:

$$
P(high\ quality\ actor\ arrives\ next)
$$

and:

$$
P(token\ reaches\ higher\ visibility\ state)
$$

These are individually learnable subproblems.

Then the trading decision becomes the output of several models rather than one magical classifier.

---

# 10. There is evidence that “avoid the garbage” is an easier ML task

A very recent August 2026 research paper assembled **6.4 million Solana tokens over seven months**. It found that conventional gradient boosting could robustly identify potential rug pulls from just the **first five minutes of trading data**, and combining Pump.fun and Raydium data improved cross-platform generalisation. ([arXiv][14])

That's important for us.

If predicting the extraordinary winners remains incredibly difficult but predicting catastrophic garbage is comparatively tractable, DARWIN should exploit the asymmetry.

Don't build:

**Winner Predictor**

first.

Build:

**Rug probability**

→ **manufactured-activity probability**

→ **creator/entity-risk probability**

→ **dead-market probability**

→ **execution-risk probability**

→ **only then rank survivors.**

Perhaps the tradeable problem is:

100,000 coins
→ 10,000 non-obvious scams
→ 2,000 structurally sound
→ 300 genuine attention
→ 30 exceptional momentum
→ **3 trade candidates**

rather than asking a model to identify the 3 directly from 100,000.

---

# 11. Every historical year now needs a market-version label

This is easily missed.

Pump's current market contains Mayhem, dynamic fee tiers, USDC pairs, Agents, cashback and other mechanics that weren't necessarily present throughout the historical dataset. ([Pump][2])

Therefore mixing everything together can create both false positives **and false negatives**.

A strategy could genuinely work in the current microstructure but appear useless because we're averaging it against a previous market design.

DARWIN needs:

`PROTOCOL_EPOCH`

on every observation.

Then we test:

$$
Edge_{2025}
\neq
Edge_{2026}
$$

rather than assuming stationarity.

This could partly explain why we're struggling to extract something repeatable.

---

# 12. One experiment will tell us where to spend our effort

This is probably the experiment I'd run before almost anything else.

## VALUE OF INFORMATION

Build models incrementally.

| Information set             | Question                                       |
| --------------------------- | ---------------------------------------------- |
| Price only                  | Is basic price action useful?                  |
| + Trades                    | Does raw flow add information?                 |
| + Wallets                   | Does identity add anything?                    |
| + Entity clustering         | Does actor identity add anything?              |
| + Funding graph             | Does genealogy add anything?                   |
| + Platform mechanism        | Does Mayhem/Agent/etc. matter?                 |
| + Pump visibility           | Does discoverability add anything?             |
| + Global memecoin state     | Does relative attention matter?                |
| + Earliest transaction feed | Does latency add anything?                     |
| + Execution model           | Is the statistical edge actually captureable?  |
| + Social/narrative          | Does off-chain information improve it further? |

For each step measure **incremental out-of-sample net EV**, not just AUC or classification accuracy.

This answers:

> **Where does the information actually live?**

If adding wallet graphs changes nothing, stop spending engineering effort there.

If Pump visibility increases performance dramatically, attack that.

If preconfirmations make the difference, we're playing a latency game.

If nothing improves until social information enters, the blockchain is downstream of the edge.

That one experiment could save months.

---

# What I now think DARWIN should become

Not a memecoin trading bot.

### A Solana observatory.

It continuously reconstructs four things:

**Market state** — what is happening?

**Actor state** — who is doing it?

**Information state** — who could know about it at this moment?

**Execution state** — can we capture it economically?

Then the trading system sits **on top** of that.

The LLM shouldn't be the predictor. It should interrogate the observatory, generate hypotheses, explain strange model behaviour and design falsification tests.

Specialised models handle the actual numerical tasks.

---

## The architecture I would build next

At the centre is a single event tape:

`event_id`
`observer_timestamp_ns`
`source/feed`
`slot`
`transaction index`
`token`
`curve/pool`
`raw transaction`
`buy/sell`
`size`
`actor/address`
`entity cluster`
`actor fingerprint`
`reserve state before`
`reserve state after`
`price impact`
`priority fee`
`Jito tip`
`CU requested/used`
`account lock set`
`mechanism type`
`Mayhem/Agent/CTO/etc.`
`Pump visibility state`
`global cohort state`

Then five separate learners estimate:

**TOXICITY**
Probability this opportunity should never be touched.

**STATE TRANSITION**
Probability of expansion/distribution/death/graduation next.

**ACTOR ARRIVAL**
Probability of important participant types appearing next.

**FIRST PASSAGE**
Probability target occurs before stop within time horizon.

**EXECUTION**
Probability/cost of actually capturing the predicted movement.

Finally:

$$
TradeEV =
P(capture)
\times
ExpectedRealisedPayoff
-
Fees
-
Impact
-
FailureCost
$$

And DARWIN has explicit permission to output:

# NO TRADE.

---

## My current diagnosis

I don't think you're missing **one secret indicator**.

I think we're missing an upstream layer.

We've been studying:

> **What successful memecoins look like.**

The deeper question is:

> **What process causes a successful memecoin to start looking like that in the first place?**

That pushes us upstream toward **platform mechanics, attention placement, economic entities, actor families, transaction propagation and execution contention**.

That's where I'd put the research budget now.

And there is an uncomfortable but valuable possible conclusion at the end of this: after building this properly we may discover that predicting memecoin direction is still not economically exploitable. If so, we'll know *why*. At that point, the same observatory can search for structural opportunities such as cross-venue price correction, post-trade arbitrage/backrunning, fee-boundary effects and execution alpha rather than continuing to manufacture increasingly complex “moon predictors.” The fact that current infrastructure explicitly pays rebates from backrun arbitrage shows that value exists in that post-trade correction layer; the question is whether we can capture enough of it ourselves. ([Helius][8])

**The single thing I'd do next is build the live forensic event tape + Value-of-Information experiment.** Without those two pieces, I think we risk doing increasingly sophisticated research on incomplete or contaminated observations.

I can also monitor Pump.fun/Solana mechanism and infrastructure changes so the research model doesn't silently become obsolete when the market rules change.

[1]: https://pump.fun/mayhem?utm_source=chatgpt.com "Mayhem Mode | Pump"
[2]: https://pump.fun/docs/mayhem-mode-disclaimer?utm_source=chatgpt.com "Mayhem Mode Disclaimer | Pump"
[3]: https://pump.fun/docs/tokenized-agent-disclaimer?utm_source=chatgpt.com "Tokenized Agent Disclaimer | Pump"
[4]: https://www.helius.dev/blog/solana-preconfirmations?utm_source=chatgpt.com "What are Preconfirmations (Preconfs) on Solana?"
[5]: https://docs.jito.wtf/lowlatencytxnfeed/?utm_source=chatgpt.com "➤ Low Latency Block Updates (Shredstream) — Jito Labs Documentation - High Performance Solana Infrastructure"
[6]: https://pump.fun/docs/fees?include-nsfw=true&utm_source=chatgpt.com "Pump.fun fees | Pump"
[7]: https://pump.fun/docs/terms-and-conditions?_rsc=1s8ba&utm_source=chatgpt.com "Terms and Conditions | Pump"
[8]: https://www.helius.dev/docs/sending-transactions/backrun-rebates?utm_source=chatgpt.com "Earn SOL Rebates from Your Transactions - Helius Docs"
[9]: https://pump.fun/docs/bonding-curve?utm_source=chatgpt.com "The Pump.fun bonding curve | Pump"
[10]: https://arxiv.org/abs/2607.28424?utm_source=chatgpt.com "Demystifying Solana Bots: From GitHub Blueprints to On-Chain Fingerprints"
[11]: https://pump.fun/explore?coins_sort=last_trade_timestamp&utm_source=chatgpt.com "Explore | Pump"
[12]: https://docs.jito.wtf/lowlatencytxnsend/?utm_source=chatgpt.com "⚡ Low Latency Transaction Send — Jito Labs Documentation - High Performance Solana Infrastructure"
[13]: https://solana.com/docs/core/fees/fee-structure?utm_source=chatgpt.com "Fee Structure | Solana"
[14]: https://arxiv.org/abs/2608.20271?utm_source=chatgpt.com "Catching the Rug: Early Prediction of Fraudulent Memecoins on Solana via Machine Learning"
