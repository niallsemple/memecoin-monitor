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
