# HFNA Live Micro-Pilot — Design Doc (v1, post-verdict)

**Basis:** `hfna_verdict.md` — 20 paper trades, +9.03%/window expectancy,
repeat-visit cohort +20.48%/window (7W/2L), first-visit −0.33% (2W/9L).
All profit came from 3 pools: nBXytBBf, GbrDAq3R, 5Z6frpb4.

## Pilot rules (hard constraints)

1. **Watchlist-only entry.** A pool qualifies after ≥1 documented positive
   HFNA exit with **net ≥ +5%** (a scratch like +0.2% does NOT qualify —
   the edge is bursts, not dust). Current watchlist:
   - `nBXytBBfKLhj6teXarAv8rk6WNgUFBMyybUFRkuK7ad` (KNOTS-SOL) — 4/4, +0.1424 SOL total
   - `GbrDAq3RjcVWeroLDUwmnuQ8N5xaaKj2Rk2dJDg64CLY` — 4/4, +0.0583 SOL total
   - `5Z6frpb4WyqNZqUxj8VN6gnwUZ6gVmpgzaseK2z3sDcB` — 1/1, +0.0084 SOL total
   A pool is REMOVED after 2 consecutive losing exits (7VKhbFtk pattern: 0/3).
2. **Entry gates (unchanged from paper):** vacuum (liq_active ≤60% of 300s ago)
   + settled (bin drift ≤5 over adaptive window) + elevation ≥1.5×
   + flow gate (Δprot_fee_y ≥500k lamports / 600s).
3. **Size:** 0.1 SOL, Y-only, bins [ab−2, ab]. One position at a time.
4. **Exits (unchanged):** refill (>1.5× trough), stall (300s no fee progress),
   tripwire (ab < low−1, immediate), timeout 1800s.
5. **Guardian wrapper:** post-exit sweep to SOL-only every time; position rent
   recovered on close; STOP_LIVE_TRADING file honored.
6. **Circuit breaker:** 3 consecutive real losses OR bankroll −15% from pilot
   start → pilot halts, report, no restart without review.

## Cost budget (from hfna_cost_model.md, measured)

- Entry+exit tx: ~0.001 SOL unrecoverable
- Position rent: 0.057 SOL recoverable on close
- Break-even: 1% per window; watchlist cohort averaged +20.5%.

## What would falsify the pilot

- Watchlist pools stop bursting (refill without fees 3× in a row across pools)
  → burst regime ended, stand down.
- Live slippage/landing latency turns paper wins into losses — the paper model
  assumes entry at snapshot time; real landing lag is ~1–5s. First 3 live
  trades are the calibration: if live capture <50% of paper-equivalent fees,
  halt and reassess.

## Status: DRAFT — awaiting owner sign-off before first live entry.
