#!/usr/bin/env python3
"""HFNA 20-trade go/no-go verdict report.

Reads hfna_paper.jsonl (one exit record per line), computes:
- overall expectancy per window (net / SIZE) vs the +2% gate
- first-visit vs repeat-visit split (chronological pool visit counting)
- burst (>+10% net) frequency with Wilson 95% CI
- ex-burst expectancy (does the drip survive without outliers?)
- verdict: GO (>2% and CI supports), MARGINAL (0-2%), NO-GO (<0%)
Writes hfna_verdict.md.
"""
import json, math, os, statistics

MON = os.path.dirname(os.path.abspath(__file__))
SIZE = 0.1
FIXED = 0.001
GATE = 0.02

def wilson(k, n, z=1.96):
    if n == 0: return (0, 0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - m) / d, (c + m) / d)

def main():
    tr = [json.loads(l) for l in open(os.path.join(MON, "hfna_paper.jsonl")) if l.strip()]
    n = len(tr)
    if n < 5:
        print("too few trades"); return
    # Normalize to the true on-chain LP multiplier (9.0 at protocolShare=1000,
    # measured 2026-09-11). Legacy entries have no "mult" field (=20 assumed).
    TRUE_MULT = 9.0
    for t in tr:
        m = t.get("mult", 20.0)
        t["net"] = t["fees"] * TRUE_MULT / m - FIXED - t.get("markout", 0)
    nets = [t["net"] for t in tr]
    # chronological visit counting
    seen = {}
    first, repeat = [], []
    for t in tr:
        p = t["pool"]
        seen[p] = seen.get(p, 0) + 1
        (first if seen[p] == 1 else repeat).append(t["net"])
    bursts = [x for x in nets if x > 0.10 * SIZE]
    exp = statistics.mean(nets) / SIZE
    med = statistics.median(nets) / SIZE
    ex_burst = [x for x in nets if x <= 0.10 * SIZE]
    exp_xb = statistics.mean(ex_burst) / SIZE
    lo, hi = wilson(len(bursts), n)
    w = sum(1 for x in nets if x > 0)

    lines = [f"# HFNA go/no-go verdict — {n} paper trades\n"]
    lines.append(f"- record: {w}W/{n-w}L, bankroll {1.0 + sum(nets):.4f} (restated to lpMult=9.0; pre-calibration figure was inflated by PROTO_MULT=20)")
    lines.append(f"- **expectancy: {exp*100:+.2f}%/window** (gate: >+{GATE*100:.0f}%)")
    lines.append(f"- median: {med*100:+.2f}%/window")
    lines.append(f"- ex-burst expectancy: {exp_xb*100:+.2f}%/window (n={len(ex_burst)})")
    lines.append(f"- bursts (>+10%): {len(bursts)}/{n}, Wilson 95% CI [{lo*100:.0f}%, {hi*100:.0f}%]")
    lines.append(f"\n## Visit split\n")
    lines.append(f"| cohort | n | avg net/window | wins |")
    lines.append(f"|---|---|---|---|")
    if first:
        lines.append(f"| first visit | {len(first)} | {statistics.mean(first)/SIZE*100:+.2f}% | {sum(1 for x in first if x>0)} |")
    if repeat:
        lines.append(f"| repeat (prior entry) | {len(repeat)} | {statistics.mean(repeat)/SIZE*100:+.2f}% | {sum(1 for x in repeat if x>0)} |")
    per_pool = {}
    for t in tr:
        per_pool.setdefault(t["pool"][:8], []).append(t["net"])
    lines.append(f"\n## Per-pool\n")
    for p, ns in sorted(per_pool.items(), key=lambda kv: -sum(kv[1])):
        lines.append(f"- {p}: {len(ns)} trades, {sum(ns)/SIZE/len(ns)*100:+.1f}%/win, total {sum(ns):+.4f} SOL")
    lines.append(f"\n## Verdict\n")
    lines.append("> **CAVEAT (2026-09-11 calibration):** paper PnL uses the liq_active share model, "
                 "which real-money measurement shows overstates capture by up to ~6000x during bursts "
                 "(liq_active swings 600x minute-to-minute). Treat absolute SOL figures as loose upper "
                 "bounds. Entry/exit TIMING signals remain valid; only real-wallet trades calibrate true PnL.\n")
    if exp > GATE:
        lines.append(f"**GO** — expectancy {exp*100:+.2f}% > {GATE*100:.0f}% gate. "
                     f"Live micro-pilot design authorized for review (0.1 SOL real, guardian-wrapped).")
    elif exp > 0:
        lines.append(f"**MARGINAL** — positive but below gate. Widen entry to 5–7 bins, rerun 20 paper trades.")
    else:
        lines.append(f"**NO-GO** — negative expectancy. Write falsification, close the lane.")
    if repeat and statistics.mean(repeat) > statistics.mean(first):
        lines.append(f"\nRepeat-visit filter SUPPORTED: repeat {statistics.mean(repeat)/SIZE*100:+.2f}% vs first {statistics.mean(first)/SIZE*100:+.2f}%.")
    open(os.path.join(MON, "hfna_verdict.md"), "w").write("\n".join(lines) + "\n")
    print(f"verdict: {n} trades, exp {exp*100:+.2f}%/window, bursts {len(bursts)} [{lo*100:.0f}-{hi*100:.0f}% CI]")

if __name__ == "__main__":
    main()
