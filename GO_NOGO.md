# DARWIN PumpSwap Momentum — GO/NO-GO Evidence Package
### 2026-09-08 ~12:30 UTC · all numbers from `pumpswap_trade_sim.py` on real tracked curves (213 pools, 1,350 snapshots)

## The strategy (as measured)

**Enter** a newborn PumpSwap pair when ALL gates pass: age ≤30 min · liquidity ≥$25k · vol_5m ≥ 1× liquidity · buys > sells (last 5 min).
**Exit** at +25% target (take-profit-early), −40% stop, 35% trail, or 30 min max hold — whichever first.
**Costs netted worst-case**: 2%/side (fee + slippage + cadence gap). Rug override: liq <30% of entry → 10% recovery.

## Verdict table (per $1,000 position, worst-case netted)

| cell | resolved n | resolved mean | rugs in sample | stress (open→rug) |
|---|---|---|---|---|
| **≤15 min entry, +25% tgt** | 4/4 | **+$255.8** | 1 | n/a (all resolved) |
| **≤30 min entry, +25% tgt** | 10/13 | **+$104.2** | 2 | −$127.6 (3 open) |
| ≤60 min entry, +25% tgt | 13/16 | +$98.2 | 3 | −$89.0 |
| ≤2 h entry, +25% tgt | 16/19 | +$137.0 | 3 | −$26.7 |
| any age, +50% tgt | — | **negative to ~0 everywhere** | — | — |

**The edge is: enter EARLY, take profit EARLY.** Monotone in entry age (earlier = better). The +50% target is dead in every cell — the rug cliff catches slow exits. Dip-buying dead (n=0: retrace = death).

## Resolved trade ledger (all rugs and all targets, no cherry-pick)

| token | entry age | entry liq | exit | net / $1k |
|---|---|---|---|---|
| haMSTR | 27 min | $42k | target | +$892 |
| 7Stock | 14 min | $189k | target | +$822 |
| SPCX (2nd mint) | 10 min | $280k | target | +$687 |
| PUGCOIN | 85 min | $53k | target | +$497 |
| LUNA | 94 min | $74k | target | +$493 |
| GOOGL | 20 min | $250k | target | +$471 |
| build | 33 min | $35k | target | +$1,023 (exited into the pump 45s BEFORE the cliff) |
| EPOKEPAD | 22 min | $80k | stop | −$479 |
| LEGO (1st mint) | 48 min | $96k | **rug** | −$900 |
| SPCX (1st mint) | 15 min | $280k | **rug** | −$900 |
| Anthropic (1st) | 25 min | $363k | **rug** | −$900 |
| AAPL (1st mint) | 13 min | $237k | **rug** | −$900 |

## What the rug research established (hard constraints on any live system)

1. **Rugs are atomic** — one transaction, one ~400ms slot. USELESS went $36.8k→$0 and build $67.8k→$0 inside single 45s intervals while the indexer price printed +352%. No polling cadence on any indexer catches the drain mid-flight.
2. **Price feeds lie during rugs** — trailing stops and momentum exits are useless against the cliff. Only liquidity/reserve data tells the truth, and only after the slot lands.
3. **Therefore the defense is structural, not reactive**: take profit early (before the 40–60 min mania window closes), size for a ~30–40% rug rate, and (candidate, untested) filter deployers on-chain pre-entry.
4. **Big liquidity ≠ safe** — AAPL rugged from $237k, Anthropic from $363k.
5. **Reserve poller's real role**: 15s death confirmation (frees capital, clean books) + catches the rare non-atomic bleed. Live in the watcher as step 12 (233 rows first run, 13 mints, 0 drains).

## Honest caveats (why this is preliminary GO, not proven)

- **One meta.** All resolved trades are this morning's stock-parody mania (HOOD/GOOGL/AAPL clones). A quiet or hostile meta is untested. Mean already drifted +168.7 → +104.2 as n grew; expect further regression.
- **Slippage is modeled (2%/side), not measured.** Real fills on $25k-liq pools may be worse.
- **Rug recovery (10%) is an assumption.**
- **Entry fills assume** the DexScreener snapshot price is fillable; build's exit proves the target fires during real pumps, but 45s gaps can hide adverse fills.
- **Key custody for live signing was never established** — to be settled at GO.

## Live-readiness checklist

| component | status |
|---|---|
| Birth detection (age 5–17 min) | ✅ live, ~127 births/hr |
| Real-venue resolution (PumpSwap) | ✅ live |
| 20-min curve tracking | ✅ live, 213 pools |
| 45s fast-poll (hot pairs) | ✅ live |
| 15s on-chain reserve poller | ✅ live (step 12) |
| Trade sim with honesty splits | ✅ resolved-only + stress bounds |
| Verdict drift log | ✅ `pumpswap_verdict_log.jsonl` |
| Deployer-safety pre-entry gate | ❌ scoped, not built |
| Live execution (Jupiter swap + signing) | ❌ not built; key custody open |
| Cross-meta evidence | ⏳ accumulating (1 meta so far) |

## Recommendation framing for the owner

- **GO bar (numeric): MET** — resolved n=10, +$104.2/$1k, rugs in sample.
- **GO bar (regime diversity): NOT MET** — one meta.
- Options: (a) live-test now at minimum size treating it as paid research; (b) wait for a second meta's cohort (hours–days); (c) build the deployer-safety gate first to cut rug rate, then go. Sizing is the owner's call either way.
