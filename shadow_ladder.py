#!/usr/bin/env python3
"""Shadow size x hold-time ladder for live trades.

For every completed live trade with a fee_curve, compute the full matrix:
  rows: candidate sizes 0.005..0.10 SOL
  cols: hold horizons 15/30/45/60/90/120/180/300s (+ measured tail)
  cell: NetEdge = feeY(t) scaled for size (dilution vs pre-entry bin liq)
        - IL_proxy(t) scaled for size - EXEC_COST (0.00002, verified probe#4)

IL proxy: sqrt-ratio IL on the snapshot price path, scaled linearly by size.
Fee scaling: share = size/(liq+size) relative to the actual position's share.

Usage: python3 shadow_ladder.py [n]   (n = how many recent trades, default 3)
"""
import json, os, math, bisect, sys

BASE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(BASE, "hfna_live.jsonl")
SNAPS = os.path.join(BASE, "bin_snapshots.jsonl")
SIZES = [0.005, 0.01, 0.02, 0.03, 0.04, 0.05, 0.075, 0.10]
HOLDS = [15, 30, 45, 60, 90, 120, 180, 300]
EXEC_COST = 0.00002  # probe #4 wallet-verified lifecycle cost

def load_trades():
    enters, curves, pnls = {}, {}, {}
    for line in open(LOG):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        k = d.get("kind")
        if k == "live_enter":
            enters.setdefault(d["pool"], []).append(d)
        elif k == "fee_curve":
            curves.setdefault(d["pool"], []).append(d)
        elif k == "real_pnl":
            pnls.setdefault(d["pool"], []).append(d)
    out = []
    for pool, cl in curves.items():
        for c in cl:
            ents = [e for e in enters.get(pool, []) if e["t"] <= c["t"]]
            if not ents:
                continue
            ent = max(ents, key=lambda e: e["t"])
            pnl = next((p for p in pnls.get(pool, []) if abs(p["t"] - c["t"]) < 120), None)
            out.append({"pool": pool, "enter": ent, "curve": c, "pnl": pnl})
    return sorted(out, key=lambda x: x["curve"]["t"])

def price_path(pool, t0, t1):
    pts = []
    try:
        for line in open(SNAPS):
            if pool[:12] not in line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("pool") == pool and t0 - 60 <= d["t"] <= t1 + 120:
                ab = d["active_bin"]
                pr = next((b["price"] for b in d.get("bins", []) if b["binId"] == ab), None)
                if pr:
                    pts.append((d["t"], pr, d.get("liq_active", 0) / 1e9))
    except FileNotFoundError:
        pass
    return sorted(pts)

def il_ratio(p0, p1):
    if not p0 or not p1 or p0 <= 0:
        return 0.0
    r = p1 / p0
    return 2 * math.sqrt(r) / (1 + r) - 1  # <= 0

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    trades = load_trades()[-n:]
    if not trades:
        print("no fee_curve trades yet"); return
    for tr in trades:
        ent, curve, pnl = tr["enter"], tr["curve"], tr["pnl"]
        pool = tr["pool"]
        # actual position size: entry wallet diff unknown here; use 0.1 (pilot)
        actual = 0.1
        c = curve["curve"]
        ts = [p[0] for p in c]
        prices = price_path(pool, ent["t"], ent["t"] + (ts[-1] if ts else 300))
        if not prices:
            print(f"{pool[:8]}: no price path"); continue
        p0 = prices[0][1]
        liq0 = prices[0][2]
        holds = [h for h in HOLDS if ts and h <= ts[-1]] + ([ts[-1]] if ts and ts[-1] > HOLDS[-1] else [])
        print(f"\n=== {pool[:8]} entry {ent['t']:.0f} bins {ent.get('bins')} "
              f"liq_active {liq0:.3f} SOL  realized pnl {pnl['real_pnl']:+.6f}" if pnl else "")
        hdr = "size\\hold " + " ".join(f"{h:>8.0f}" for h in holds)
        print(hdr)
        for s in SIZES:
            ref_share = actual / (liq0 + actual)
            our_share = s / (liq0 + s)
            fscale = our_share / ref_share if ref_share > 0 else 1
            row = []
            for h in holds:
                i = bisect.bisect_right(ts, h) - 1
                if i < 0:
                    row.append(float("nan")); continue
                feeY = c[i][2] * fscale
                j = bisect.bisect_right([p[0] for p in prices], ent["t"] + c[i][0]) - 1
                il = il_ratio(p0, prices[j][1]) * s if j >= 0 else 0.0
                row.append(feeY + il - EXEC_COST)
            print(f"{s:>9.3f} " + " ".join(f"{v:>+8.5f}" for v in row))
        # best cell
        best = (-1e9, None, None)
        for s in SIZES:
            ref_share = actual / (liq0 + actual); our_share = s / (liq0 + s)
            fscale = our_share / ref_share if ref_share > 0 else 1
            for h in holds:
                i = bisect.bisect_right(ts, h) - 1
                if i < 0: continue
                feeY = c[i][2] * fscale
                j = bisect.bisect_right([p[0] for p in prices], ent["t"] + c[i][0]) - 1
                il = il_ratio(p0, prices[j][1]) * s if j >= 0 else 0.0
                v = feeY + il - EXEC_COST
                if v > best[0]: best = (v, s, h)
        print(f"best cell: size={best[1]} hold={best[2]:.0f}s net={best[0]:+.6f}")

if __name__ == "__main__":
    main()
