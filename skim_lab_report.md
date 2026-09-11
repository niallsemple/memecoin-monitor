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
