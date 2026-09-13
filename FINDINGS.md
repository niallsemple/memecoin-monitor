
## 2026-09-13 capacity branch falsified (deep SOL-USDC)
Ran capacity_pnl.py on 5rCf1DM8 ($5.1M TVL) and HTvjzsfX ($360k) with live snapshot data.
Result: IL drag >> fee capture at EVERY size (0.1 -> 500 SOL), both pools, 1h and 6h windows.
- 5rCf1DM8 1h: pool fees 1.42 SOL/h, SOL +0.48% -> at 50 SOL: +0.0014 fees vs -0.120 IL = -0.119 net
- HTvjzsfX 6h: at 50 SOL: -0.189 net
Fee/TVL velocity (~0.003%/h on position at 0.1% share) cannot outrun any SOL price drift.
Scaling up does NOT fix the 0.05-scale problem: IL scales linearly, fixed costs were never the dominant term.
Condition for viability: fee velocity/TVL must exceed price drift per unit time — a regime detector
should watch this ratio. Branch CLOSED pending regime change.
