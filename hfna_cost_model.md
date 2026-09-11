# HFNA micro-pilot — cost model & go/no-go (memo #37 lane)

Measured inputs (this project's own data, 2026-09-12):
- Windows: ~51/hr across 11 tracked pools; median duration 12.6 min
- Fee elevation at window open: median 4.9x reference (~24x variable-fee multiplier), 89% >= 1.5x
- Crowding refill: median 140s to double from trough (inflows then stick ~1h)
- Reference capture rate: KNOTS wide arm earned 0.032 SOL/hr on 0.77 SOL (4.2%/hr)
  while its accumulator ran ~5x reference — a TIGHT range captures a much larger
  share of active-bin fees per SOL deployed than a 56-bin-wide band.

## Entry design that avoids the two biggest costs

**Y-only (pure SOL) deposit into bins at/just-below the settled active bin.**
- No token-X purchase -> no swap fee (2%+ pool fee), no X inventory, no IL beyond
  bin drift, no sweep problem at exit (position already ~all SOL).
- Consistent with first-touch rent rule: only enter pools whose bin arrays already
  exist (established pools — our tracked universe qualifies).
- Exit = remove liquidity + close position -> rent recovered.

## Costs per window trade (Meteora DLMM)

| Item | Cost | Notes |
|---|---|---|
| Open position rent | 0.057 SOL | **recoverable on close** (owner-gated, F1-proven) |
| add_liquidity tx | ~0.0002 SOL | base + modest priority |
| remove+close tx | ~0.0002 SOL | |
| Bin-array first-touch | 0 | gated OUT by rule (never first LP into fresh range) |
| Swap fee | 0 | Y-only entry, no swap |
| **Unrecoverable total** | **~0.0004-0.001 SOL** | |

## Break-even

Fixed cost ~0.001 SOL. On a 0.1 SOL deployment, break-even = 1% fee capture in-window.
KNOTS measured 4.2%/hour as a WIDE band during 5x elevation; a 3-5 bin tight position
at the active bin during 5-25x elevation should capture multiples of that per hour.
Windows last median 12.6 min -> required capture ~1% in ~13 min.

Go/no-go measurable quantity per window (computable from bin snapshots):
  capture = (our_liq / liq_active_at_settle) x fee_rate x window_volume
The missing empirical piece is **window_volume** (swap volume during the 12.6min
settled window) — derivable from cum_fees deltas if we snapshot pool cum-fees per
round. bin_collector upgrade: record pool total fees (protocol + lp) per snapshot.

## Risk gates (inherited from live lanes)
- Settle gate: bin drift <= 5 over adaptive window before entry (measured: 96% settle)
- Elevation gate: vol_accum/vol_ref >= 1.5 at entry (89% of windows pass)
- Abort: active bin moves >3 bins from entry -> pull (tripwire pattern from surf pilot)
- Size: 0.1 SOL first pilot trades, scale only on data
- Max concurrent: 1 (rent lockup bounded at ~0.057 SOL)

## Decision
Pilot is CHEAP to paper: all inputs observable from bin_snapshots + one extra
cum-fees field. Build paper HFNA trader first; live only if paper shows >2% net
per window across >= 20 windows.
