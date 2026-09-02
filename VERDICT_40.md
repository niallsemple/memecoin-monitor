# 40-CLOSE VERDICT — Live Memecoin Book

**Status: ARMED — awaiting closes #37–#40 (currently 36).**
Fill the `[_]` fields from `python3 review_40.py` + `python3 drain_sim.py` at 40 closes. Every rule below was pre-agreed from evidence; no re-analysis at decision time.

---

## 1. Book state at 40 (from review_40.py)

- Closes: [_]  Green: [_] ([_]%)  Net: [_] SOL  Expectancy/trade: [_]%
- On-chain wallet: [_] SOL vs funding 2.68389 → [_]% | residual after fees/rent: [_] (must be "plausible")
- Panic cohort (market-action only): [_] closes, [_]% green, [_]%/trade

**Go/no-go for ANY change:** market-action cohort ≥ 20 closes AND ≥ 85% green AND worst ≥ −25% of stake (BXiwv −0.127 was infra, excluded per §218-standard). If NO-GO: hold everything, accumulate 20 more closes.

## 2. Decisions (pre-committed)

### 2.1 Entry gates — DO NOT ACTIVATE as blocking. (Evidence: §212, §214, §215, §216)
- Crew tripwire (§210B): forward catch 0/25 LOO. Keep **shadow/log** — its only forward channel is §207 watcher pre-mapping.
- Overhang gate (§210A): **dead on evidence** — all three metric flavors fail (naive inverts: LUTN 13.75% drain vs EoBTrx 44.3% green; v2 bundle-fooled). `g2_gate.json` stays `false`. Revisit ONLY if §211 forward samples (n≥20 fresh-age) show separation.
- Deployer-funding gate: 0/28 at 3 hops — not built, not planned.

### 2.2 Sizing (evidence: §208 fee model, §217 cascade forensics)
- Instant drains are irreducible; stake size is the only control (§217.2).
- Rule: scale to **2× (cap 0.20 → 0.30)** ONLY IF market-action cohort clears §1 gate AND at least 1 panic/nm/fade exit has demonstrated the §176 escalation path live (a verified escalated fill). Otherwise hold 1× and re-review at 60 closes.
- Never 3× before 60 closes (§208: impact eats 25–50% of edge).

### 2.3 Exit stack — no changes (evidence: §217, §218)
- Latency median 0.6m — adequate. abort15 covers modal dump window (JwQb proof).
- Watch: first live freeroll (1.5×) has never fired; first live panic has never fired. If a panic fires and fails WITHOUT escalation working → halt scale-up, fix first.

## 3. Flip sequence (only if §1 GO + §2.2 conditions met)

1. `python3 review_40.py` → paste into REPORT.md §219.
2. `python3 drain_sim.py` → confirm gated replay still positive.
3. Edit `live_trader.py`: `MAX_POS_SOL`/`cap` 0.20 → 0.30. (Sizing stays 5% of balance; cap raise is the only change.)
4. `g2_gate.json` stays `false`. Shadow screens keep stamping entries.
5. Commit "§219 verdict: [decision]", push, announce to owner.

## 4. Evidence index

| Claim | Where |
|---|---|
| Crew gate leaky forward (0/25) | §212 crew_fp_audit.py |
| Overhang fails all flavors | §213 backfill, §214 forensics, §215 v2 bundles |
| Deployer funding blind (0/28, 3 hops) | §216 deployer_funding_hop2.json |
| Cascade fills exist at our size | §217 (1,327 LUTN fills) |
| Instant drain = size-controlled tail | §217.2 |
| Exit latency healthy (0.6m median) | §218 |
| 2× economics positive if green rate holds | §208 fee_drag_model.py |
| Gated replay +0.200 vs ungated −0.306 (historical, leaky crew component — treat as overhang-only + tripwire-bonus) | §209 drain_sim.py |
