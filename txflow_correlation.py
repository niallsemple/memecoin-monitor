#!/usr/bin/env python3
"""txflow_correlation.py — test whether paper dead fills were low-tx windows.

Joins closed trades from the three HFNA paper arms against txflow.jsonl
(claim-immune swap counts per pool per ~60s poll). If dead fills show LOW
swap counts, placement theory weakens (pool really was quiet). If dead fills
show NORMAL/HIGH swap counts, bursts were happening but landing outside our
bins -> placement is confirmed as the leak, weight shifts to the repo arm.

Also reports entry-time swaps_5m per trade as a candidate entry precondition.

Usage: python3 txflow_correlation.py
"""
import json, statistics
from pathlib import Path

ARMS = ["hfna_paper.jsonl", "hfna_paper_w7.jsonl", "hfna_paper_repo.jsonl"]
DEAD_EPS = 1e-9


def load_txflow():
    rows = {}
    p = Path("txflow.jsonl")
    if not p.exists():
        return rows
    for line in p.read_text().splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows.setdefault(r["pool"], []).append(r)
    for v in rows.values():
        v.sort(key=lambda r: r["t"])
    return rows


def window_stats(flow_rows, t0, t1):
    win = [r for r in flow_rows if t0 - 30 <= r["t"] <= t1 + 30]
    if not win:
        return None
    s5 = [r["swaps_5m"] for r in win]
    return {
        "n": len(win),
        "mean5": statistics.mean(s5),
        "max5": max(s5),
        "zero_frac": sum(1 for x in s5 if x == 0) / len(s5),
    }


def entry_swaps(flow_rows, t0):
    pre = [r for r in flow_rows if r["t"] <= t0 + 5]
    return pre[-1]["swaps_5m"] if pre else None


def main():
    flow = load_txflow()
    trades = []
    for arm in ARMS:
        p = Path(arm)
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "entry_t" not in r or "fees" not in r:
                continue
            r["arm"] = arm.replace("hfna_paper", "3bin").replace(".jsonl", "").replace("_", "")
            trades.append(r)
    trades.sort(key=lambda r: r["t"])

    covered, dead, paid = [], [], []
    print(f"{'arm':6} {'pool':8} {'dead':4} {'net':>9} {'mean5':>7} {'max5':>6} {'entry5':>7}")
    for tr in trades:
        fr = flow.get(tr["pool"])
        if not fr:
            continue
        ws = window_stats(fr, tr["entry_t"], tr["t"])
        if not ws:
            continue  # trade predates txflow history
        is_dead = abs(tr["fees"]) < DEAD_EPS
        e5 = entry_swaps(fr, tr["entry_t"])
        rec = {**ws, "dead": is_dead, "net": tr["net"], "entry5": e5}
        covered.append(rec)
        (dead if is_dead else paid).append(rec)
        print(f"{tr['arm']:6} {tr['pool'][:8]:8} {str(is_dead):4} {tr['net']:>9.5f} "
              f"{ws['mean5']:>7.1f} {ws['max5']:>6} {e5 if e5 is not None else '-':>7}")

    print(f"\ncoverage: {len(covered)}/{len(trades)} trades overlap txflow history")
    if len(covered) < 8:
        print("VERDICT: not enough overlap yet — keep collecting")
        return

    def summ(name, grp):
        if not grp:
            print(f"{name}: none")
            return
        m5 = [g["mean5"] for g in grp]
        x5 = [g["max5"] for g in grp]
        e5 = [g["entry5"] for g in grp if g["entry5"] is not None]
        print(f"{name}: n={len(grp)} mean5 med={statistics.median(m5):.1f} "
              f"max5 med={statistics.median(x5):.0f} zero_frac={statistics.mean(g['zero_frac'] for g in grp):.2f}"
              + (f" entry5 med={statistics.median(e5):.0f}" if e5 else ""))

    summ("DEAD", dead)
    summ("PAID", paid)

    if dead and paid:
        d_med = statistics.median(g["mean5"] for g in dead)
        p_med = statistics.median(g["mean5"] for g in paid)
        if d_med >= 0.7 * p_med:
            print("\nVERDICT: dead fills had comparable swap flow -> PLACEMENT is the leak "
                  "(bursts landing outside our bins); put weight on repo arm")
        else:
            print("\nVERDICT: dead fills were genuinely quiet windows -> entry timing, "
                  "not placement; test entry5 precondition")
        # crude entry5 threshold sweep
        all_e = [(g["entry5"], g["net"], g["dead"]) for g in covered if g["entry5"] is not None]
        if len(all_e) >= 8:
            best = None
            for th in sorted({e for e, _, _ in all_e}):
                kept = [(n, d) for e, n, d in all_e if e >= th]
                if len(kept) < 4:
                    continue
                exp = statistics.mean(n for n, _ in kept)
                dr = sum(1 for _, d in kept if d) / len(kept)
                if best is None or exp > best[1]:
                    best = (th, exp, dr, len(kept))
            if best:
                print(f"best entry5 threshold: >={best[0]} -> exp {best[1]:+.5f}/trade, "
                      f"dead rate {best[2]:.0%}, n={best[3]}")


if __name__ == "__main__":
    main()
