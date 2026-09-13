#!/usr/bin/env python3
"""Hold-time NetEdge(t) analyzer.

For every live trade with a fee_curve event (15s accrual series
[secs_since_entry, activeBin, feeY]), compute at horizons
15/30/60/120/180/300s:
  - feeY accrued (scaled to SOL via position size when known)
  - in-range flag (activeBin inside [low, high])
  - marginal accrual rate over the last interval (feeY/s)
  - NetEdge(t) = accrued_fees_SOL - fixed_costs - IL_proxy(t)

fixed_costs = tx fees + position rent (~0.043 SOL entry, refunded on close,
so true fixed = tx fees + any ATA rent not reclaimed). IL_proxy uses the
bin_snapshots price path when available; else marks "n/a".

Purpose (mandate item 3): decide whether exits should tighten (fees
front-loaded -> shorter holds) or loosen (fees linear -> hold longer).
Needs 3+ fee_curve trades for any signal; prints per-trade table regardless.
"""
import json, os, bisect

BASE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(BASE, "hfna_live.jsonl")
SNAPS = os.path.join(BASE, "bin_snapshots.jsonl")
HORIZONS = [15, 30, 60, 120, 180, 300]
TX_COST = 0.00003   # post-compression estimate: 2 lean txs
RENT_NET = 0.0015   # position+ATA rent not always fully reclaimed (empirical)
SIZE_SOL = 0.1

def load():
    enters, exits, curves, pnls = {}, {}, {}, {}
    for line in open(LOG):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        k = d.get("kind")
        if k == "live_enter":
            enters.setdefault(d["pool"], []).append(d)
        elif k == "live_exit":
            exits.setdefault(d["pool"], []).append(d)
        elif k == "fee_curve":
            curves.setdefault(d["pool"], []).append(d)
        elif k == "real_pnl":
            pnls.setdefault(d["pool"], []).append(d)
    return enters, exits, curves, pnls

def load_prices(pool, t0, t1):
    """(t, price) series for the pool's active bin from snapshots."""
    pts = []
    try:
        for line in open(SNAPS):
            if pool[:12] not in line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("pool") == pool and t0 - 60 <= d["t"] <= t1 + 60:
                ab = d["active_bin"]
                pr = next((b["price"] for b in d.get("bins", []) if b["binId"] == ab), None)
                if pr:
                    pts.append((d["t"], pr))
    except FileNotFoundError:
        pass
    return sorted(pts)

def il_proxy(p_entry, p_t):
    """IL of a full-range-ish short LP approximated as sqrt price ratio loss."""
    if not p_entry or not p_t:
        return None
    r = p_t / p_entry
    if r <= 0:
        return None
    import math
    return 2 * math.sqrt(r) / (1 + r) - 1  # negative = loss vs hold

def main():
    enters, exits, curves, pnls = load()
    n = 0
    print(f"fee_curve trades found: {sum(len(v) for v in curves.values())}\n")
    for pool, clist in curves.items():
        for c in clist:
            cands = [e for e in enters.get(pool, []) if e["t"] <= c["t"]]
            ent = max(cands, key=lambda e: e["t"]) if cands else None  # latest entry
            pnl = next((p for p in pnls.get(pool, []) if abs(p["t"] - c["t"]) < 120), None)
            if not ent:
                continue
            n += 1
            curve = c["curve"]
            ts = [pt[0] for pt in curve]
            horizons = [h for h in HORIZONS if ts and h <= ts[-1]]
            if ts and ts[-1] > HORIZONS[-1]:
                horizons += [ts[-1]]  # always report the tail point
            low, high = ent.get("bins", [None, None])
            prices = load_prices(pool, ent["t"], ent["t"] + (ts[-1] if ts else 0))
            p_entry = prices[0][1] if prices else None
            print(f"{pool[:8]}  entry {ent['t']:.0f}  bins [{low},{high}]  "
                  f"curve pts {len(curve)}  pnl {pnl['real_pnl']:+.6f}" if pnl else "")
            print(f"  {'t':>5} {'feeY':>10} {'rate/s':>10} {'inRng':>6} {'ILproxy':>9} {'NetEdge':>10}")
            prev_fee = prev_t = 0.0
            for h in horizons:
                i = bisect.bisect_right(ts, h) - 1
                if i < 0:
                    continue
                s, ab, fee = curve[i]
                rate = (fee - prev_fee) / max(1e-9, s - prev_t) if i > 0 else fee / max(s, 1)
                inrng = (low is not None and low <= ab <= high)
                p_t = None
                if prices:
                    j = bisect.bisect_right([p[0] for p in prices], ent["t"] + s) - 1
                    if j >= 0:
                        p_t = prices[j][1]
                il = il_proxy(p_entry, p_t)
                il_sol = (il * SIZE_SOL) if il is not None else None
                net = fee - TX_COST - RENT_NET - (il_sol or 0)
                print(f"  {s:>5.0f} {fee:>10.7f} {rate:>10.2e} "
                      f"{str(inrng):>6} {('%+.4f' % il) if il is not None else 'n/a':>9} {net:>+10.6f}")
                prev_fee, prev_t = fee, s
            print()
    if n < 3:
        print(f"NOTE: only {n} fee_curve trade(s) — need 3+ before any hold-time verdict.")

if __name__ == "__main__":
    main()
