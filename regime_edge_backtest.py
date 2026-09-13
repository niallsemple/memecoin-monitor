#!/usr/bin/env python3
"""regime_edge_backtest.py — replay regime_edge ratio over full snapshot history.

For each tracked pool, slide a 1h trailing window over bin_snapshots.jsonl and
compute the same edge_ratio as regime_edge.py (fee_rate/h vs IL rate/h).
Find windows where ratio >= EDGE_MIN sustained >= SUSTAIN consecutive snapshots
(the detector's FAVORABLE condition), then score a hypothetical position entered
at window start, exited at window end:

  fees  = pool LP fees over hold * our share of active-bin liquidity
  IL    = |drift|/2 * size        (same proxy as capacity_pnl)
  fixed = 0.0002 SOL              (measured probe overhead: tx + swap legs)

Usage: python3 regime_edge_backtest.py [size_sol]
"""
import json, os, sys, time

BASE = os.path.dirname(os.path.abspath(__file__))
SNAPS = os.path.join(BASE, "bin_snapshots.jsonl")
POOLS = os.path.join(BASE, "capacity_pools.json")
EDGE_MIN = float(os.environ.get("BT_EDGE_MIN", "1.5"))
SUSTAIN = int(os.environ.get("BT_SUSTAIN", "3"))
FIXED = 0.0002
LP_MULT = 9.0
LOOKBACK_S = 3600

sys.path.insert(0, BASE)
from capacity_watch import fees_sol, sol_price_ref, STABLES  # noqa: E402


def price_of(d):
    return next((bn["price"] for bn in d.get("bins", [])
                 if bn["binId"] == d["active_bin"]), None)


def main():
    size = float(sys.argv[1]) if len(sys.argv) > 1 else 0.05
    pools = {p["addr"]: p for p in json.load(open(POOLS))["pools"]}
    series = {a: [] for a in pools}
    with open(SNAPS) as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("pool") in series:
                series[d["pool"]].append(d)
    sol_usdc = sol_price_ref(series) or 100
    print(f"sol_usdc={sol_usdc:.1f}  size={size} SOL  EDGE_MIN={EDGE_MIN} "
          f"SUSTAIN={SUSTAIN}")

    total_windows = 0
    total_net = 0.0
    for addr, meta in pools.items():
        rows = sorted(series[addr], key=lambda d: d["t"])
        if len(rows) < 10:
            continue
        tvl_sol = (meta.get("tvl_usd") or 1) / sol_usdc
        # ratio at each snapshot using trailing 1h window
        ratios = []   # (t, ratio, idx)
        for i, b in enumerate(rows):
            lo = b["t"] - LOOKBACK_S
            j = i
            while j > 0 and rows[j - 1]["t"] >= lo:
                j -= 1
            a = rows[j]
            dt_h = (b["t"] - a["t"]) / 3600
            if dt_h < 0.25:      # need >=15min window for stable rates
                ratios.append((b["t"], None, i))
                continue
            try:
                fs = fees_sol(a, b, meta, sol_usdc)
            except (KeyError, TypeError):
                fs = None
            p_in, p_out = price_of(a), price_of(b)
            if fs is None or not p_in or not p_out:
                ratios.append((b["t"], None, i))
                continue
            fee_rate = fs * LP_MULT / dt_h / tvl_sol
            il_rate = abs(p_out - p_in) / p_in / dt_h / 2
            ratio = fee_rate / il_rate if il_rate > 1e-9 else (
                999.0 if fee_rate > 0 else 0.0)
            ratios.append((b["t"], ratio, i))
        # sustained favorable runs
        wins = []
        run = []
        for t, r, i in ratios:
            if r is not None and r >= EDGE_MIN:
                run.append((t, r, i))
            else:
                if len(run) >= SUSTAIN:
                    wins.append(run)
                run = []
        if len(run) >= SUSTAIN:
            wins.append(run)
        # score each window
        pool_net = 0.0
        print(f"\n== {meta['name']} ({addr[:8]}) — {len(wins)} favorable "
              f"windows over {(rows[-1]['t']-rows[0]['t'])/3600:.1f}h ==")
        for w in wins:
            i0, i1 = w[0][2], w[-1][2]
            a, b = rows[i0], rows[i1]
            hold_h = (b["t"] - a["t"]) / 3600
            try:
                fs = (fees_sol(a, b, meta, sol_usdc) or 0) * LP_MULT
            except (KeyError, TypeError):
                fs = 0.0
            liq_act = float(b.get("liq_active") or 0)
            # our share of active bin: size in Y raw units / liq_active
            y_dec = meta["y_dec"]
            if meta["y_sym"] == "SOL":
                our_raw = size * 1e9
            else:
                our_raw = size * sol_usdc * 10 ** y_dec
            share = our_raw / liq_act if liq_act > 0 else 0
            share = min(share, 0.05)   # cap: >5% of a bin = impact + artifact guard
            fees = fs * share
            p_in, p_out = price_of(a), price_of(b)
            il = abs(p_out - p_in) / p_in / 2 * size if p_in and p_out else 0
            net = fees - il - FIXED
            pool_net += net
            total_windows += 1
            total_net += net
            print(f"  {time.strftime('%m-%d %H:%M', time.localtime(a['t']))}"
                  f" hold {hold_h*60:5.0f}m  ratio~{sum(x[1] for x in w)/len(w):5.1f}"
                  f"  fees {fees:+.5f}  il {il:.5f}  net {net:+.5f}")
        if wins:
            print(f"  pool total: {pool_net:+.5f} SOL at size {size}")
    print(f"\nALL: {total_windows} favorable windows, "
          f"combined net {total_net:+.5f} SOL at size {size}")


if __name__ == "__main__":
    main()
