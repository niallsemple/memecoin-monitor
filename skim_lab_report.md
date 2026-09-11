# Skim Lab — LP fee-density window falsification (hourly scale)
- history: 305 pools, bursts found: 1329
- burst def: interval fee velocity ≥ 3× pool median and ≥ $5/min
## Window shape
- fee half-life after burst: p25=2322m median=4684m p75=7220m (n=1301)
- LP crowding (+50% TVL): p25=17666m median=49043m p75=89524m (n=204)
- bursts where fee window outlived crowding: 1273/1329 (96%)
## Toxicity
- 2h price markout after burst: p25=-2.9% median=0.0% p75=2.0% (n=1322)
- bursts with < -10% markout (toxic): 175/1322 (13%)
- Q (|dprice%| per $10k traded): median=0.44 p75=3.37
## Verdict (hourly scale)
PASS: fee windows systematically outlive LP crowding — a skim window exists at hourly scale.
Note: pool-level TVL is a coarse proxy for active-bin liquidity; ~2h median cadence cannot see 30s-5min windows. A dense bin-level collector is the next build if this passes.

## v2 — burst-triggered crowding, first cut (2026-09-12, bin_snapshots 2.6h, 11 pools)

Method: inflow event = liq within ±10 bins grows ≥25% vs 5min earlier. 17 events found.

| Metric | Value |
|---|---|
| Inflow size | median **+43%** in 5 min, p90 +95% |
| Incumbent dilution | median fee share drops to **70%** within 5 min of event |
| Persistence | 68% of inflow remains at 30 min; **97% at 60 min** — crowding is sticky |
| Concentration | active-bin liq growth +39% ≈ pm10 growth — inflow spreads across range, not sniping the active bin |

Implications:
- Quoted fee yields overstate realizable yield during hot windows: an incumbent should
  haircut quotes by ~30% for crowding, and the crowd does NOT leave within the hour.
- Inflows being range-wide (not active-bin snipes) means wide-band positions get diluted
  just as much as tight ones — width buys IL protection, not fee-share protection.
- Series is young (2.6h, liquidity-only). Next: join with fee-velocity spikes once the
  collector has more hours, to confirm inflows actually chase bursts (vs random drift).

## vacuum_lab — post-sweep liquidity vacuums (memo #37 idea 7), first cut (2026-09-12)

Signal: liq_active <= 60% of 5min-ago value. **136 events across 8 pools in 2.6h** — vacuums are frequent, not rare.

| Metric | Value |
|---|---|
| Depth | median collapse to **21%** of prior active liquidity |
| Refill (crowding half-life) | median **140s** to double from trough |
| Failure to refill | 15/136 (11%) never doubled within window |
| Post-vacuum price | active bin drifts median 22 bins over next 5 min — price still moving |

Caveat: liq_active conflates LP exits with price crossing into naturally thin bins —
but for fee-per-unit-liquidity the distinction doesn't matter: thin active liquidity
is thin, and swaps crossing it pay the same elevated per-unit fee either way.

Strategy consequence (memo #37's HFNA window): the vacuum is real and lasts minutes,
but bin drift shows price is usually still moving when it forms. Entry must wait for
bin drift to flatten (price convergence) — exactly the memo's "do nothing during the
move" rule. A live implementation needs: vacuum trigger + bin-drift-flat gate +
dynamic-fee-elevated check, then seconds-scale entry/exit.

## hfna_scan — full HFNA state (vacuum + price settled), first measurement (2026-09-12)

Gate: vacuum (liq_active <= 60% of 5min ago) then settlement (active bin within +-5
over an adaptive ~8min window; per-pool sampling is ~155s so fixed 60s was sub-cadence).

| Metric | Value |
|---|---|
| Vacuums that settle into HFNA windows | **134/140 (96%)** |
| Settle lag | median **0s** (flat under the wider gate), p90 238s |
| Window duration | median **757s (~12.6 min)**, max 3627s |
| Frequency | **~51 windows/hour across just 11 tracked pools** |

Read: HFNA windows are abundant and long enough for unhurried entry/exit — scarcity
was never the constraint. The unmeasured third leg is **fee elevation at window open**
(dynamic fee still high when price settles?). Next: bin_collector records pool dynamic
fee per snapshot (volatility accumulator / variable-fee rate from LbPair) so hfna_scan
can score windows by fee level, and the strategy question becomes which windows pay
enough per capital-second to clear tx+rent costs.
