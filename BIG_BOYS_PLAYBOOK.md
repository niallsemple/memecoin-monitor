# HOW THE BIG BOYS DO IT — 10 replication plays
**Darwin Labs AI · 28 Aug 2026 · built on REPORT.md §1–§46 evidence + current 2026 market meta**

The 23-hour forward test just proved retail-side pattern trading is dead for us
(verdict B). This document asks the next question: **who is actually extracting
the money, and which of their mechanisms can we realistically replicate?**

The common denominator across all ten: the pros either **are the event**
(insider launches, MM campaigns, call channels) or **sell risk to the event**
(infra, fees, tips, boosts, data). Almost none of them make money the way we
tried to — by predicting which token pumps from the outside.

---

## 1. Slot-zero migration sniping (infrastructure parity)

**How they do it:** When a pump.fun bonding curve completes and migrates to
PumpSwap, top bots land their buy in the *same slot* (slot 0). The stack:
Yellowstone gRPC on co-located bare metal, pre-built transaction templates,
multi-relay Jito submission (NY/Frankfurt/Tokyo/Amsterdam + Astralane +
Lil-JIT in parallel), dynamic tip calibration. End-to-end <50 ms. Slot 0 vs
slot 2 is a 20–60% upside difference. Jito now runs 95%+ of stake; tips are
60%+ of all priority fees.

**Reality check:** ~200+ bots compete on a typical launch; only ~10–15% run
profitably. Amateur path = 430–680 ms (guaranteed loser). Production path =
~$2.65 effective cost/win vs ~$7.75 amateur.

**Our version:** Rent co-lo RPC (Frankfurt/Ashburn), subscribe to bonding-curve
accounts via gRPC, pre-build templates at ~80% curve completion, multi-relay
with simulateBundle before every paid tip. We already know *what* to filter
for (our audit pipeline) — this adds the *speed* layer.

**Cost:** ~£400–1,500/mo infra + dev time. **Edge type:** mechanical,
crowded, decays. **Kill criteria:** if our landed-slot distribution isn't
>50% slot-0/slot-1 in the first 500 paper attempts, stop — we'd be the exit
liquidity.

## 2. Insider-launch forensics (join the bundle, don't fight it)

> **TESTED 28 Aug 2026 (REPORT.md §47): NULL.** Fresh-wallet birth bundles are
> absent from both cohorts (winners 1/21, losers 2/20 with ≥2 fresh early
> buyers; median fresh_share 0.0 both). The 2024-era fingerprint is extinct —
> pros use aged, pre-funded wallets now. Superseded by the indexer-grade
> aged-farm variant (playbook-2 #2).

**How they do it:** The real winners aren't sniping other people's launches —
they *are* the launch. Deployer funds 20–100 fresh wallets from a common
source, bundles 30–80% of supply in the birth slot, then distributes. The
"cluster" we spent 24h hunting was one such entity mid-rotation.

**Our version:** We already built the detection (`cluster_tag.py`,
funding-tree analysis, 385+ trustworthy tags live). Flip it from *follow*
to *screen*: at birth, compute bundle-% (supply bought in slot 0–1 by
freshly-funded wallets). High bundle + wallets NOT distributing after 30 min =
insider conviction; that's the rideable case. High bundle + immediate
dribble-out = exit-liquidity trap; blacklist the funding source forever.

**Cost:** near-zero marginal — extends existing pipeline. **Edge type:**
informational, defensive-first. **Kill criteria:** if "held bundle" cohort
doesn't beat the 2.6% touch-rate baseline forward, drop it.

## 3. Smart-money copy-trading with provenance gates

**How they do it:** GMGN/Axiom/BullX copy-trading follows leaderboard wallets.
The pros' refinement: they don't copy *PnL* — they copy *role*. A wallet that
seeds at birth is signal; the same wallet buying +200m post-peak is the
dump (our §42: the entity now late-chases — anyone dumb-copying it forward
lost money).

**Our version:** Our forensic layer is genuinely differentiated: we cluster by
funding tree and tag *role at time of trade* (birth-seed vs late-chase).
Copy only birth-seed events from wallets with verified multi-token win
records, with the §44 momentum + liquidity gates on top. Nobody selling
copy-trading does provenance gating.

**Cost:** existing infra + websocket upgrade. **Edge type:** behavioral,
moderate. **Kill criteria:** pre-registered: ≥20 copy signals, must beat
66% hit-2× — same bar v6 failed; hold the line.

## 4. Market-maker campaign detection (ride the manufactured pump)

**How they do it:** Volume-bot services run 2,000–19,000 maker wallets at
70/30 buy/sell ratios to push tokens onto Dexscreener trending in 4–8h
($1–5k per session). It's manufactured — but it's *scheduled* manufactured
flow, and scheduled flow is predictable.

**Our version:** Our loser-scan found wallet recurrence 1.24/token = ambient
sniper noise. An organized MM campaign has the opposite fingerprint: aged
wallets, batched/multi-hop swaps, sustained cadence, buy-biased ratio.
Detect campaign *start* on an otherwise-dead token, enter small, exit into
the trending-page arrival (the campaign's advertised endpoint), never hold
past cadence stop.

**Cost:** analysis dev only. **Edge type:** event-driven. **Kill criteria:**
this is riding a pump the operator can end at will — hard stop at campaign
cadence break, no exceptions; paper-prove cadence-detection first.

## 5. Dexscreener boost/trending front-run

**How they do it:** Boosts are paid visibility (lightning-bolt badges);
trending score ≈ volume × unique holders × liquidity. Insiders accumulate
*before* buying the boost, then sell into the attention wave the boost
creates.

**Our version:** Monitor tokens with rising organic metrics (holder growth,
unique-buyer ratio — we track these) but flat price: the pre-boost
accumulation profile. Enter on boost-badge appearance or paid-socials update,
exit mechanically within the attention window (hours, not days).

**Cost:** Dexscreener API + existing pipeline. **Edge type:** event-driven
front-run. **Kill criteria:** if post-boost median move < boost cost
amortized, the trade is negative-EV — measure 30 events before trading.

## 6. Call-channel / KOL ignition trading (the §45 answer)

**How they do it:** Our biggest open question — what ignited 4978aTN9 at
09:00Z after 45 min flat — is almost certainly an external call (Telegram
channel, boost, KOL post). The pros don't predict ignition; they *are* the
ignition, or they're in the channel getting the call seconds early.

**Our version:** The 19% no-momentum tail (2/13 forward touches ran late) is
exactly where external ignition lives. Build an ignition monitor: subscribe
to the major call channels + boost events + holder-count acceleration. When
ignition fires on a token that already passed our audit + cluster screens,
enter with the loose-trail variant (the §46 post-window research item).
We're not the caller; we're the fastest *informed* follower.

**Cost:** channel subscriptions (~£100–300/mo for alpha groups) + dev.
**Edge type:** speed-relative-to-retail. **Kill criteria:** if median
entry is >3 min post-ignition, skip — the move is already priced.

## 7. Meteora DLMM fee farming on survivors (sell risk, don't take it)

**How they do it:** While degens swing on direction, pros park concentrated
liquidity in DLMM bins on tokens that survived the first hour and farm the
churn — fees on every buy AND sell, both directions of everyone else's
emotions.

**Our version:** Our §6/§7 survival filter (audit PASS + ≥80% floor at +40m)
is exactly the survivorship screen LP farming needs. Open DLMM positions
only on survivors, tight bins around current price, harvest fees, exit at
first distribution fingerprint (§2/§45 cluster forensics). Matches verdict
B's defensive character — this is income, not punting.

**Cost:** capital-efficient at small size; impermanent loss is the risk.
**Edge type:** structural/defensive. **Kill criteria:** IL > fees over any
rolling week → stop; this is the lowest-variance play on the list.

## 8. Graduation backruns and JIT liquidity (small-searcher MEV)

**How they do it:** Not all MEV is sandwiches. The deterministic, legible
events — bonding-curve completions, PumpSwap pool creations — create
backrun and just-in-time-liquidity opportunities every few minutes.
Jito bundles make them atomic; jitodontfront accounts protect them.

**Our version:** Same infra as play #1 but aimed at events, not races:
provide JIT liquidity to the graduation pool in the birth slot, or backrun
the migration arb. Lower competition than slot-0 sniping because most bots
chase the headline trade, not the plumbing.

**Cost:** shares play #1's infra. **Edge type:** mechanical, steadier than
sniping. **Kill criteria:** revert rate >10% or tip share >70% of realized
profit = the strategy is a charity, stop.

## 9. The deployer playbook (be the house) — analysis only

**How they do it:** The biggest EV in the ecosystem belongs to the full-stack
launcher: deploy token + bundle supply + volume bot + boost + KOL package.
Pump.fun itself made $700M+ in fees. A competent launch operation with
£10–50k can manufacture a trending token on demand.

**Our position:** This is where the money is, and we are not doing it.
Unlicensed market-manipulation-as-a-service (wash volume, undisclosed
insider bundles, paid undisclosed promotion) carries real UK legal exposure
(FCA financial-promotion regime, fraud by false representation). Logged here
so the map is complete — **the correct use of this knowledge is detection,
not participation**: every technique in this section is a fingerprint our
pipeline can catch.

**Cost:** N/A — excluded. **Edge type:** N/A. **Kill criteria:** permanently
killed; detection-only.

## 10. Sell the shovels (monetize what we proved)

**How they do it:** The most reliable big-boy businesses never touch
directional risk: RPC providers, bot platforms (~1%/trade on BullX/Banana),
call channels (£100s/mo per subscriber), volume services, Dexscreener itself.
They sell picks in the gold rush.

**Our version:** We just built and *validated* something with proven
informational content: a live cluster-forensics pipeline that tagged 500
tokens, caught an entity mid-rotation, and — the hard part — *correctly
refused to trade for 498 consecutive evaluations* while every unfiltered
book lost money. That is a product: insider-cluster alerts, bundle-%
scores, funding-tree blacklists, exit-liquidity warnings. Deliver via the
existing Pattern Lab dashboard → Telegram alert bot → subscription.

**Cost:** packaging only. **Edge type:** zero market risk, monetizes the one
asset we definitively proved. **Kill criteria:** if the alert feed's
forward informational value decays (touch rate stays 2.6%), sunset it
honestly.

---

## Synthesis — where this leaves us

| Play | Capital | Latency bar | Edge type | Our readiness |
|---|---|---|---|---|
| 1. Slot-zero sniping | £££ | <50 ms | mechanical, crowded | need infra build |
| 2. Insider forensics | £ | minutes | informational | **90% built** |
| 3. Provenance copy-trading | ££ | seconds | behavioral | **80% built** |
| 4. MM campaign riding | ££ | minutes | event-driven | needs detector |
| 5. Boost front-run | £ | hours | event-driven | needs boost feed |
| 6. Ignition following | ££ | <3 min | speed-relative | needs channel feed |
| 7. DLMM fee farming | ££ | none | structural | **ready now** |
| 8. Graduation MEV | £££ | <50 ms | mechanical | shares play 1 |
| 9. Deployer | — | — | **excluded (legal)** | detection-only |
| 10. Sell shovels | £ | none | zero market risk | **ready now** |

The two ready-now plays (7, 10) are both *defensive monetization* — they fit
verdict B. The highest-upside feasible plays (2, 3) extend what we already
built. The latency plays (1, 8) are the only true "big boy table" entries —
they cost real money and should only be attempted after a paper latency
benchmark, never before.
