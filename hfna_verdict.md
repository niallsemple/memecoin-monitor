# HFNA go/no-go verdict — 28 paper trades

- record: 9W/19L, bankroll 1.0587 (restated to lpMult=9.0; pre-calibration figure was inflated by PROTO_MULT=20)
- **expectancy: +2.10%/window** (gate: >+2%)
- median: -0.85%/window
- ex-burst expectancy: -0.77%/window (n=26)
- bursts (>+10%): 2/28, Wilson 95% CI [2%, 23%]

## Visit split

| cohort | n | avg net/window | wins |
|---|---|---|---|
| first visit | 12 | -2.08% | 3 |
| repeat (prior entry) | 16 | +5.22% | 6 |

## Per-pool

- nBXytBBf: 5 trades, +15.5%/win, total +0.0777 SOL
- GbrDAq3R: 5 trades, +3.6%/win, total +0.0182 SOL
- 5Z6frpb4: 1 trades, +3.2%/win, total +0.0032 SOL
- 5h1GmqcC: 1 trades, +0.9%/win, total +0.0009 SOL
- EEkVx3wi: 1 trades, -1.0%/win, total -0.0010 SOL
- 5e1UHN6p: 1 trades, -1.0%/win, total -0.0010 SOL
- 9NdiyGft: 2 trades, -0.6%/win, total -0.0013 SOL
- BcAaxXZZ: 2 trades, -0.7%/win, total -0.0013 SOL
- 6e4ewHhG: 2 trades, -1.0%/win, total -0.0020 SOL
- DCh6beah: 1 trades, -3.2%/win, total -0.0032 SOL
- FpP5SnzB: 3 trades, -2.5%/win, total -0.0076 SOL
- 7VKhbFtk: 4 trades, -6.0%/win, total -0.0240 SOL

## Verdict

**GO** — expectancy +2.10% > 2% gate. Live micro-pilot design authorized for review (0.1 SOL real, guardian-wrapped).

Repeat-visit filter SUPPORTED: repeat +5.22% vs first -2.08%.
