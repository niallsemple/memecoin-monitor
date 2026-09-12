#!/usr/bin/env python3
"""
bin_collector.py — dense bin-level liquidity collector (memo #35 build).

Purpose: the hourly skim_lab test PASSED (96% of fee bursts outlive LP
crowding), but pool-level TVL at ~2h cadence cannot see the 30s-5min
windows ChatGPT's fee-density hypothesis is about. This collector takes
bin-level snapshots (active bin ±10, liquidity per bin) of the pools with
the hottest CURRENT fee velocity, so we can measure:
  - true active-liquidity crowding half-life (bin-level, minute cadence)
  - fee velocity vs bin-liquidity delta (skim pressure)
  - markout from active-bin price path

Universe: top 8 pools by recent fee velocity (d(cum_fees)/dt over last
two meteora_fee_snapshots), plus any pool with an open live/paper position.

Each run appends one row per pool to bin_snapshots.jsonl:
  {t, pool, active_bin, bin_step, liq_active, liq_pm10, bins:[...]}
Run it every poll cycle; the Bash-level loop (5 x 60s) gives minute cadence.

Usage: python3 bin_collector.py            # one snapshot round
       python3 bin_collector.py 5 60       # 5 rounds, 60s apart
"""
import json, os, subprocess, sys, time, collections

MON = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(MON, "meteora_fee_snapshots.jsonl")
OUT = os.path.join(MON, "bin_snapshots.jsonl")
BUNDLE = os.path.join(MON, "lp_exec", "meteora_lp.bundle.cjs")
TOP_N = 8


def hot_pools(now):
    """Top pools by fee velocity over their last two snapshots."""
    last2 = collections.defaultdict(list)
    with open(SNAP) as f:
        for l in f:
            try:
                r = json.loads(l)
            except Exception:
                continue
            if r.get("pool") and r.get("cum_fees") is not None and r.get("t"):
                last2[r["pool"]].append((r["t"], r["cum_fees"]))
    vel = {}
    for p, rows in last2.items():
        rows.sort()
        for (t1, c1), (t2, c2) in zip(rows[-2:-1], rows[-1:]):
            if t2 > t1 and c2 >= c1 and t2 > now - 6 * 3600:
                vel[p] = (c2 - c1) / ((t2 - t1) / 60)
    return [p for p, _ in sorted(vel.items(), key=lambda kv: -kv[1])[:TOP_N]]


def snap_pool(pool):
    try:
        r = subprocess.run(["node", BUNDLE, "binsjson", pool],
                           capture_output=True, text=True, timeout=90)
        line = [l for l in r.stdout.splitlines()
                if l.strip().startswith('{"pool"')]
        if not line:
            return None
        d = json.loads(line[-1])
        ab = d["activeBin"]
        liq_active = sum(b["liqY"] for b in d["bins"] if b["binId"] == ab)
        liq_pm10 = sum(b["liqY"] for b in d["bins"])
        return {"t": d["t"], "pool": pool, "active_bin": ab,
                "bin_step": d["binStep"], "liq_active": liq_active,
                "liq_pm10": liq_pm10, "bins": d["bins"],
                "vol_accum": int(d.get("volAccum", 0)), "vol_ref": int(d.get("volRef", 0)),
                "var_fee_ctl": int(d.get("varFeeCtl", 0)), "base_factor": int(d.get("baseFactor", 0)),
                "prot_fee_y": int(d.get("protFeeY", 0)), "prot_fee_x": int(d.get("protFeeX", 0))}
    except Exception as e:
        print(f"  snap fail {pool[-6:]}: {str(e)[:60]}")
        return None


def round_once(now):
    pools = hot_pools(now)
    # always track pools with open positions (live surf / guardian)
    try:
        for p in json.load(open(os.path.join(MON, "lp_positions.json")))["positions"]:
            if p.get("status") == "open" and p.get("pool") not in pools:
                pools.append(p["pool"])
    except Exception:
        pass
    # always track pool with an open HFNA paper position (3-bin and w7)
    open_pos_pools = []
    for sf in ("hfna_paper_state.json", "hfna_paper_w7_state.json"):
        try:
            hp = json.load(open(os.path.join(MON, sf))).get("pos")
            if hp and hp.get("pool"):
                open_pos_pools.append(hp["pool"])
                if hp["pool"] not in pools:
                    pools.append(hp["pool"])
        except Exception:
            pass
    # always track HFNA live-pilot watchlist pools — the pilot cannot evaluate
    # entries without fresh snapshots even when we hold no position
    try:
        for wp in json.load(open(os.path.join(MON, "hfna_watchlist.json")))["pools"]:
            if wp not in pools:
                pools.append(wp)
    except Exception:
        pass
    n = 0
    with open(OUT, "a") as f:
        for p in pools:
            s = snap_pool(p)
            if s:
                f.write(json.dumps(s) + "\n")
                n += 1
    print(f"bin snapshot: {n}/{len(pools)} pools")
    return open_pos_pools


def fast_tail(open_pos_pools, max_rounds=3, gap=15):
    """While paper positions are open, snapshot just those pools at ~15s so
    the w7 boundary early exit is measured at realistic cadence (the 64s
    default lets price gap straight past the exit zone — GBR 23:10 strike)."""
    if not open_pos_pools:
        return
    for i in range(max_rounds):
        time.sleep(gap)
        n = 0
        with open(OUT, "a") as f:
            for p in open_pos_pools:
                s = snap_pool(p)
                if s:
                    f.write(json.dumps(s) + "\n")
                    n += 1
        print(f"fast tail {i+1}/{max_rounds}: {n}/{len(open_pos_pools)} pos pools")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "fast":
        # post-entry mode: snapshot only pools with open paper positions,
        # 3 rounds x 15s. Run AFTER the engines in a poll cycle so newly
        # opened positions get 15s coverage during the danger window.
        pos_pools = []
        for sf in ("hfna_paper_state.json", "hfna_paper_w7_state.json"):
            try:
                hp = json.load(open(os.path.join(MON, sf))).get("pos")
                if hp and hp.get("pool") and hp["pool"] not in pos_pools:
                    pos_pools.append(hp["pool"])
            except Exception:
                pass
        if pos_pools:
            fast_tail(pos_pools)
        else:
            print("fast: no open positions")
        return
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    gap = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    open_pos = []
    for i in range(rounds):
        open_pos = round_once(time.time()) or open_pos
        if i < rounds - 1:
            time.sleep(gap)
    fast_tail(open_pos)


if __name__ == "__main__":
    main()
