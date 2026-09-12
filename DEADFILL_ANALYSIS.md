# Dead-Fill Analysis — 2026-09-12 23:35 UTC

Hypothesis: dead fills (fees ≈ 0, −0.001 friction loss) are pools whose flow
dies right after entry → abort trigger on first-60s prot_fee delta.

## Result: FALSIFIED

- Dead fills (n=7): median first-60s pool fee flow **0.050 SOL** — HIGHER
  than payers (n=11, median 0.005 SOL).
- Abort thresholds kill 0-2/7 dead fills while sacrificing 5/11 payers.
- Dead fills are not dead pools. The pool pays; our bins aren't the active
  bin when it does. In-range fraction at snapshot time ≈ 0 for nearly all
  trades, winners included — fee capture happens in bursts we mostly miss
  (64s snapshot cadence also undercounts brief visits).

## Reframe

The leak is PLACEMENT, not pool selection: 3 bins of coverage in a market
whose price wanders 10+ bins within minutes. Money is there; our bins aren't.

Levers that attack placement:
1. Wider ranges (w7 A/B running)
2. Repositioning: re-center range on price when drift ≥ threshold; costs
   ~0.0005 SOL/tx per move but multiplies in-range time. Needs a sim on
   snapshot paths (next slice).

Note: w7 log row GbrDAq3R life=81808s is a state artifact from the variant's
first run (stale entry_t from copied state file); excluded from stats here.

## Addendum: burst clustering (2026-09-13 00:55 UTC)

8,080 snapshot intervals: P(burst | burst within prior 5min) = 70.3% vs
P(burst | none) = 34.7% — 2.0x lift. Bursts cluster; the post-vacuum entry
premise is NOT falsified. Misses come from bursts landing at price bins our
fixed ranges don't cover (placement), not from burst flow stopping.
Supports the repo (follow-the-price) arm as the theoretically correct fix.
