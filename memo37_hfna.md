Yes. After digging into the actual mechanics, I think there are several more interesting possibilities than simply finding a high-fee pool and trying to enter faster.

The objective I would set is:

$$
\boxed{\text{Maximise net LP income per capital-second}}
$$

rather than APR. None of the ideas below require taking another LP's assets or bypassing ownership checks; they exploit **how the protocols legitimately price, route and reward liquidity**.

1. **Adaptive-fee “aftershock” harvesting — strongest idea.** A violent move increases the volatility accumulator and therefore the swap fee. The obvious thing is to LP during the move; I think that's wrong because that's when adverse selection is greatest. Instead, wait until the pool price has reconverged with external fair value and directional flow has died, but enter **before the protocol's volatility memory has fully decayed**. Orca explicitly retains volatility state through a filter/decay mechanism rather than immediately resetting it. ([Orca Documentation][1]) The state we're hunting is essentially:

   $$
   \text{high fee}+\text{low price error}+\text{low directional flow}+\text{high turnover}
   $$

   That's a potentially beautiful LP state: **yesterday's danger is still determining today's fee.**

2. **Scheduled fee-cliff harvesting.** Meteora DAMM v2 can have completely deterministic fee decay: the fee drops at known time intervals, linearly or exponentially. ([Meteora Documentation][2]) That lets us predict when a previously expensive pool suddenly becomes attractive to Jupiter/aggregator routing. Rather than harvesting the *highest fee*, we'd estimate:

   $$
   \frac{\text{new routed volume}\times\text{new fee rate}}
   {\text{active liquidity}}
   $$

   immediately after every scheduled reduction. There may be a sweet spot where the fee falls from, say, 2% to 1%, causing routed volume to increase 10× while existing LP capital barely changes. We would enter immediately before that routing transition and exit when competing liquidity catches up. This is effectively **arbitraging the LP market's reaction time to a known protocol event**.

3. **Raydium “first-flow” LP.** Raydium CPMM contains a very interesting documented behaviour: swaps are rejected before `open_time`, but **deposits are allowed before `open_time`**. ([Raydium Docs][3]) That means we don't have to race other LPs after trading begins. For carefully screened launches, we can preload liquidity while trading is impossible, be present for the first legitimate routed flow, then leave very quickly. The research question becomes whether the first 5/10/30/60 seconds produce enough fees to overcome the extraordinary launch-token inventory risk. I would never blindly do this on random tokens, but structurally it is unusual.

4. **Turn Meteora limit orders into paid market making.** This one is much better than I initially realised. Meteora's DLMM limit orders don't merely fill at selected bins: when they contribute to a swap, **they participate in fee flow**. Meteora currently says 50% of the applicable limit-order portion goes to limit-order participants under the program's fee split. ([Meteora Documentation][4]) So instead of depositing conventional LP liquidity, we build ladders of prices where we are already willing to buy or sell. If filled, we get our desired execution **plus fee income**. It is closer to earning a maker rebate than traditional LPing.

5. **Quote-token-only fee harvesting.** Meteora has another unusual mechanism: `OnlyY` mode can make fees accrue entirely in token Y — including when Y is the output side — and limit-order liquidity can participate. ([Meteora Documentation][5]) Imagine X is speculative and Y is USDC or SOL. We could construct positions primarily to acquire/dispose of X while deliberately accumulating our fee edge in Y. It doesn't eliminate inventory risk, but it prevents the fee stream itself continually turning into the volatile asset. I would specifically scan for **OnlyY + elevated dynamic fee + two-sided turnover + low active liquidity**.

6. **Tail-bin “shock absorber” positions.** Don't LP at the current price at all. Put single-sided liquidity several bins/ticks away from fair value. It does nothing in normal conditions. A large displacement must reach us before capital becomes active, and by that point adaptive/dynamic fees may also have risen sharply. Orca's variable fee has a squared relationship with its volatility accumulator, while Meteora distributes fees specifically to bins crossed by swaps. ([Orca Documentation][1]) We effectively say: *I'll absorb forced/aggressive flow, but only at a price and fee large enough to compensate me.* After a fill, hedge/recycle the acquired inventory instead of leaving it as an LP position.

7. **Post-sweep liquidity-vacuum harvesting.** A large swap can move the active price outside many concentrated positions. Suddenly the pool has very little active liquidity. Most LP bots then rebalance to the new area. Our signal isn't therefore “volume is rising”; it's:

   $$
   \frac{L_{\text{active,t}}}{L_{\text{active,t-1}}}\ll1
   $$

   We wait for external price and AMM price to converge, then fill that temporary liquidity vacuum. Exit as soon as active liquidity recovers. Raydium exposes active CLMM liquidity directly, and its fee-growth accounting distributes each step's LP fees over the active \(L\), meaning lower active liquidity mechanically increases the fee captured per unit of our liquidity for the same swap. ([Raydium Docs][6]) This leads to a new metric I'd call **LP crowding half-life**: how many seconds after a liquidity collapse before active liquidity doubles again?

8. **Reward-density sniping rather than APR farming.** Meteora DLMM mining rewards are streamed to liquidity in the active/crossed bins and your share is proportional to your share of eligible liquidity. It can distribute across up to 15 crossed bins during v2 swap flow. ([Meteora Documentation][7]) So forget displayed farm APR. Monitor:

   $$
   \text{reward \$ / sec}/\text{eligible active \$}
   $$

   An incentivised pool can temporarily lose most of its active liquidity while reward emission stays constant. Entering during those windows could produce extreme **reward per capital-second**, especially on relatively correlated pairs. Importantly, there is no magical reward backlog when active liquidity is zero — Meteora explicitly says those rewards aren't retroactively paid to new LPs. ([Meteora Documentation][7])

9. **Cross-AMM LP arbitrage.** This may ultimately be the biggest strategy. Don't arbitrage SOL price between Orca/Raydium/Meteora; arbitrage **the price paid for liquidity**. For the same pair calculate continuously:

   $$
   Y_v =
   \frac{\text{actual routed volume}_v
   \times\text{LP fee}_v+\text{rewards}_v}
   {\text{active liquidity}_v}
   -
   \text{expected markout}_v
   $$

   Then capital moves between venues whenever expected yield per capital-second separates sufficiently to cover relocation costs. Dynamic fees, liquidity vacuums and Meteora scheduled fee changes should generate these dislocations continuously. This is basically **smart order routing, but for LP capital instead of trades**.

10. **Build a “hot grid” rather than opening positions after signals.** This isn't an alpha by itself, but it may turn marginal ideas above into profitable ones. Maintain already-created position infrastructure around price and inject/remove liquidity from the required range when the signal occurs. On Raydium, initialized tick-array accounts persist even after liquidity leaves them, meaning subsequent use avoids recreating those arrays. ([Raydium Docs][6]) Raydium is also preparing first-class CLMM limit orders, single-token fee modes and dynamic fees, although importantly its current docs still mark those capabilities as an **unreleased CLMM update**, so I wouldn't assume they're live until we verify deployment. ([Raydium Docs][8])

### The one state I think we should obsess over

After thinking through all of those, there's a recurring state I hadn't appreciated enough before:

> **High protocol fee + price already correct + little active liquidity.**

Call it the **High-Fee No-Arbitrage Window**.

Normally:

**high fee → high volatility → LP gets hurt.**

But for a brief period after the volatility:

**high fee → price aligned → volatility subsiding → LP competition still low.**

That separation between **the protocol's memory of volatility** and **current actual adverse-selection risk** may be the cleanest structural edge here.

I would build a scanner whose primary variable is therefore:

$$
HFNA =
\frac{
E[\text{next 30s fees}]
}{
L_{\text{active}}
}
-
E[\text{30s markout}]
$$

and calculate it across **every adaptive/dynamic pool on Orca, Meteora and eventually Raydium**.

### And I would combine three of the ideas

The version I'd most like to test isn't one strategy in isolation.

**Fee-memory + liquidity-vacuum + tail-bin limit order.**

A violent move occurs. We **do nothing during it**.

External price stabilises. AMM price catches up. Dynamic fee remains elevated. Existing LPs have been knocked out of range. We then insert extremely concentrated liquidity/fee-bearing limit orders at or just outside fair value.

We collect the expensive post-event turnover.

As soon as either:

`dynamic_fee ↓`
`active_liquidity ↑`
`price/reference divergence ↑`
`flow imbalance ↑`

we remove it.

Potential exposure could be **seconds rather than hours**.

That's much closer to HFT market making than yield farming.

### How I'd judge whether we've actually found something

Don't report APR. Don't even report ROI first.

Measure:

$$
\boxed{
\text{Net \$ per £1,000 per second exposed}
}
$$

with:

$$
\text{Net}
=
\text{LP fees}
+\text{rewards}
+\text{maker/limit fees}
-\text{markout}
-\text{inventory loss}
-\text{hedging}
-\text{transactions}
-\text{priority/Jito costs}
$$

Solana transaction economics matter because repeated position changes can turn a small gross advantage negative; priority fees are based on requested compute limits, so execution needs to be tightly optimised as well. ([Solana][9])

If I had to allocate research effort **right now**, I'd put most of it into **Adaptive-Fee Aftershock**, then **Meteora Scheduled Routing Cliffs**, then **Meteora Fee-Bearing Limit Orders**, with **Raydium Pre-Open First Flow** as the high-risk experimental arm.

Those feel materially different from the LP strategies everybody else is staring at. The next breakthrough probably isn't “find a better pool”; it's **identify a protocol state in which Solana temporarily overpays somebody willing to supply liquidity for a few seconds**.

[1]: https://docs.orca.so/developers/architecture/whirlpool-fees?utm_source=chatgpt.com "Understanding Whirlpool Fees - Orca Documentation"
[2]: https://docs.meteora.ag/core-products/damm-v2/fees/time-scheduler "DAMM v2 Time Scheduler - Meteora Documentation"
[3]: https://docs.raydium.io/products/cpmm/accounts?utm_source=chatgpt.com "CPMM accounts - Raydium Docs"
[4]: https://docs.meteora.ag/core-products/dlmm/limit-order "DLMM Limit Order - Meteora Documentation"
[5]: https://docs.meteora.ag/core-products/dlmm/collect-fee-mode "DLMM Collect Fee Mode - Meteora Documentation"
[6]: https://docs.raydium.io/products/clmm/accounts?utm_source=chatgpt.com "CLMM accounts - Raydium Docs"
[7]: https://docs.meteora.ag/core-products/dlmm/liquidity-mining "DLMM Liquidity Mining - Meteora Documentation"
[8]: https://docs.raydium.io/reference/changelog?utm_source=chatgpt.com "Changelog - Raydium Docs"
[9]: https://solana.com/docs/core/fees/fee-structure?utm_source=chatgpt.com "Fee Structure | Solana"
