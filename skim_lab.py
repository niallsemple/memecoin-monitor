#!/usr/bin/env python3
"""
skim_lab.py — falsification test for the "LP skim window" hypothesis
(ChatGPT memo #35): do short-lived windows exist where fee flow rises
faster than active liquidity, and how fast does the LP crowd arrive?

Uses the existing meteora_fee_snapshots.jsonl history (pool-level, ~2h
median cadence, ~90h span). This tests the HOURLY-scale version of the
hypothesis. A 30s-5min version needs a denser collector (not built yet).

Metrics per pool time series (sorted by t):
  fee_vel   = d(cum_fees)/dt        ($/min, interval fee flow)
  tvl_d     = d(TVL)/dt             ($/min, liquidity crowding)
  q         = |dprice %| / vol_int  (price displacement per $ traded)
  markout_p = price % change from burst snap to snap ~2h later
  crowd_hl  = minutes for TVL to +50% after a fee burst (crowding speed)
  fee_hl    = minutes for fee_vel to halve after burst peak

A "burst" = fee_vel >= 3x pool median AND >= $5/min (real money only).

Output: skim_lab_report.md + console summary.
"""
import json, os, statistics, collections

MON = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(MON, "meteora_fee_snapshots.jsonl")


def load_series():
    pools = collections.defaultdict(list)
    with open(SNAP) as f:
        for l in f:
            try:
                r = json.loads(l)
            except Exception:
                continue
            if r.get("pool") and r.get("t") and r.get("cum_fees") is not None:
                pools[r["pool"]].append(r)
    for v in pools.values():
        v.sort(key=lambda r: r["t"])
    return pools


def analyze(pool, rows):
    """Return list of burst events with decay/crowding/markout labels."""
    events = []
    # build interval metrics
    iv = []
    for a, b in zip(rows, rows[1:]):
        dt = (b["t"] - a["t"]) / 60.0  # minutes
        if dt <= 0:
            continue
        cf_a, cf_b = a.get("cum_fees"), b.get("cum_fees")
        if cf_a is None or cf_b is None:
            continue
        fee_vel = (cf_b - cf_a) / dt if cf_b >= cf_a else None
        tvl_a = float(a.get("tvl") or 0)
        tvl_b = float(b.get("tvl") or 0)
        tvl_d = (tvl_b - tvl_a) / dt
        pa = float(a.get("price") or 0)
        pb = float(b.get("price") or 0)
        dpct = (pb / pa - 1) * 100 if pa > 0 and pb > 0 else None
        vol_int = (b.get("cum_volume") or 0) - (a.get("cum_volume") or 0)
        q = abs(dpct) / vol_int * 1e4 if (dpct is not None and vol_int > 0) else None
        iv.append({"t": b["t"], "dt": dt, "fee_vel": fee_vel, "tvl_d": tvl_d,
                   "tvl": tvl_b, "price": pb, "dpct": dpct, "q": q,
                   "age_h": b.get("age_h")})
    vels = [x["fee_vel"] for x in iv if x["fee_vel"] is not None and x["fee_vel"] > 0]
    if len(vels) < 6:
        return events
    med = statistics.median(vels)
    if med <= 0:
        return events
    for i, x in enumerate(iv):
        fv = x["fee_vel"]
        if fv is None or fv < max(3 * med, 5.0):
            continue
        # burst at x. Look forward: fee halving, tvl +50%, markout ~2h
        fee_hl = crowd_hl = None
        for y in iv[i + 1:]:
            mins = (y["t"] - x["t"])
            if fee_hl is None and y["fee_vel"] is not None and y["fee_vel"] <= fv / 2:
                fee_hl = mins
            if crowd_hl is None and x["tvl"] > 0 and y["tvl"] >= 1.5 * x["tvl"]:
                crowd_hl = mins
            if fee_hl is not None and crowd_hl is not None:
                break
        mark = None
        for y in iv[i + 1:]:
            if (y["t"] - x["t"]) >= 110:  # ~2h markout
                if x["price"] > 0 and y["price"] > 0:
                    mark = (y["price"] / x["price"] - 1) * 100
                break
        events.append({"pool": pool, "t": x["t"], "fee_vel": fv,
                       "med_vel": med, "mult": fv / med,
                       "tvl": x["tvl"], "age_h": x.get("age_h"),
                       "q": x.get("q"), "fee_hl_min": fee_hl,
                       "crowd_hl_min": crowd_hl, "markout_2h_pct": mark})
    return events


def main():
    pools = load_series()
    all_ev = []
    for p, rows in pools.items():
        all_ev.extend(analyze(p, rows))
    print(f"pools with history: {len(pools)}, burst events: {len(all_ev)}")
    if not all_ev:
        print("no bursts found")
        return

    def pct(vals, p):
        vals = sorted(v for v in vals if v is not None)
        if not vals:
            return None
        k = min(len(vals) - 1, max(0, int(p / 100 * (len(vals) - 1))))
        return vals[k]

    fh = [e["fee_hl_min"] for e in all_ev if e["fee_hl_min"] is not None]
    ch = [e["crowd_hl_min"] for e in all_ev if e["crowd_hl_min"] is not None]
    mk = [e["markout_2h_pct"] for e in all_ev if e["markout_2h_pct"] is not None]
    qs = [e["q"] for e in all_ev if e["q"] is not None]
    # window alive = fee halves BEFORE crowd arrives (or crowd never in window)
    alive = sum(1 for e in all_ev
                if e["fee_hl_min"] is not None and
                (e["crowd_hl_min"] is None or e["crowd_hl_min"] > e["fee_hl_min"]))
    toxic = sum(1 for e in all_ev
                if e["markout_2h_pct"] is not None and e["markout_2h_pct"] < -10)
    lines = [
        "# Skim Lab — LP fee-density window falsification (hourly scale)",
        "",
        f"- history: {len(pools)} pools, bursts found: {len(all_ev)}",
        f"- burst def: interval fee velocity ≥ 3× pool median and ≥ $5/min",
        "",
        "## Window shape",
        f"- fee half-life after burst: p25={pct(fh,25):.0f}m median={pct(fh,50):.0f}m p75={pct(fh,75):.0f}m (n={len(fh)})",
        f"- LP crowding (+50% TVL): p25={pct(ch,25):.0f}m median={pct(ch,50):.0f}m p75={pct(ch,75):.0f}m (n={len(ch)})" if ch else "- LP crowding: never reached +50% within observed window for most bursts",
        f"- bursts where fee window outlived crowding: {alive}/{len(all_ev)} ({alive/len(all_ev)*100:.0f}%)",
        "",
        "## Toxicity",
        f"- 2h price markout after burst: p25={pct(mk,25):.1f}% median={pct(mk,50):.1f}% p75={pct(mk,75):.1f}% (n={len(mk)})",
        f"- bursts with < -10% markout (toxic): {toxic}/{len(mk)} ({toxic/max(1,len(mk))*100:.0f}%)",
        f"- Q (|dprice%| per $10k traded): median={pct(qs,50):.2f} p75={pct(qs,75):.2f}" if qs else "",
        "",
        "## Verdict (hourly scale)",
        ("PASS: fee windows systematically outlive LP crowding — a skim window exists at hourly scale."
         if alive / len(all_ev) > 0.5 and (pct(mk, 50) if pct(mk, 50) is not None else -99) > -10 else
         "MIXED/FAIL: either crowding arrives before fees decay, or post-burst markout is toxic. See numbers above."),
        "",
        "Note: pool-level TVL is a coarse proxy for active-bin liquidity; "
        "~2h median cadence cannot see 30s-5min windows. A dense bin-level "
        "collector is the next build if this passes.",
    ]
    rep = "\n".join(l for l in lines if l)
    print(rep)
    with open(os.path.join(MON, "skim_lab_report.md"), "w") as f:
        f.write(rep + "\n")
    with open(os.path.join(MON, "skim_bursts.jsonl"), "w") as f:
        for e in all_ev:
            f.write(json.dumps(e) + "\n")


if __name__ == "__main__":
    main()
