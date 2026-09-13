#!/usr/bin/env python3
"""Gate calibration sweep over realized paper trades.

For each paper arm log, bucket trades by entry elevation (elev) and
entry_swaps5 (tx5 tape strength), then report what each candidate gate
would have kept / dropped and the net effect.

Gates swept: elev in [1.5, 2, 2.5, 3, 4, 5, 6]  x  tx5 in [0, 75, 150, 300, 600]
Out-of-sample honesty: this is realized trade filtering only — no
counterfactual re-simulation of skipped windows (those need the snapshot
replay; noted in output).
"""
import json, os, glob

BASE = os.path.dirname(os.path.abspath(__file__))
ARMS = {
    "base":   "hfna_paper.jsonl",
    "w7":     "hfna_paper_w7.jsonl",
    "repo":   "hfna_paper_repo.jsonl",
    "flow":   "hfna_paper_flow.jsonl",
    "reflow": "hfna_paper_reflow.jsonl",
    "thin":   "hfna_paper_thin.jsonl",
}
ELEVS = [1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0]
TX5S  = [0, 75, 150, 300, 600]

def load(fn):
    rows = []
    p = os.path.join(BASE, fn)
    if not os.path.exists(p):
        return rows
    for line in open(p):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "net" in d and "elev" in d:
            rows.append(d)
    return rows

def stats(trs):
    if not trs:
        return None
    net = sum(t["net"] for t in trs)
    wins = sum(1 for t in trs if t["net"] > 0)
    return len(trs), net, net / len(trs), wins / len(trs)

def main():
    all_tr = []
    per_arm = {}
    for arm, fn in ARMS.items():
        trs = load(fn)
        per_arm[arm] = trs
        all_tr += [(arm, t) for t in trs]
    print(f"total realized paper trades: {len(all_tr)}\n")

    print("== elevation gate sweep (tx5 unfiltered) ==")
    print(f"{'gate':>5} {'n':>4} {'kept%':>6} {'net':>10} {'mean':>10} {'win%':>6}")
    n_all = len(all_tr)
    for g in ELEVS:
        keep = [t for _, t in all_tr if t["elev"] >= g]
        s = stats(keep)
        if s:
            print(f"{g:>5} {s[0]:>4} {100*s[0]/n_all:>5.0f}% {s[1]:>+10.6f} {s[2]:>+10.6f} {100*s[3]:>5.0f}%")

    print("\n== tx5 tape gate sweep (elev unfiltered) ==")
    print(f"{'gate':>5} {'n':>4} {'kept%':>6} {'net':>10} {'mean':>10} {'win%':>6}")
    for g in TX5S:
        keep = [t for _, t in all_tr if t.get("entry_swaps5", 0) >= g]
        s = stats(keep)
        if s:
            print(f"{g:>5} {s[0]:>4} {100*s[0]/n_all:>5.0f}% {s[1]:>+10.6f} {s[2]:>+10.6f} {100*s[3]:>5.0f}%")

    print("\n== combined: elev>=2.0 AND tx5>=T ==")
    print(f"{'tx5':>5} {'n':>4} {'net':>10} {'mean':>10} {'win%':>6}")
    for g in TX5S:
        keep = [t for _, t in all_tr if t["elev"] >= 2.0 and t.get("entry_swaps5", 0) >= g]
        s = stats(keep)
        if s:
            print(f"{g:>5} {s[0]:>4} {s[1]:>+10.6f} {s[2]:>+10.6f} {100*s[3]:>5.0f}%")

    print("\n== per-arm at current live gates (elev>=2, tx5>=75) ==")
    for arm, trs in per_arm.items():
        keep = [t for t in trs if t["elev"] >= 2.0 and t.get("entry_swaps5", 0) >= 75]
        s = stats(keep)
        all_s = stats(trs)
        if s and all_s:
            print(f"{arm:>7}: kept {s[0]:>3}/{all_s[0]:<3} net {s[1]:>+10.6f} (all {all_s[1]:>+10.6f})  win {100*s[3]:.0f}%")

    print("\nnote: skipped-window counterfactuals need snapshot replay (separate pass)")

if __name__ == "__main__":
    main()
