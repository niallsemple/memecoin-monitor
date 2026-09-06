#!/usr/bin/env python3
"""H14 graduation event study — measure the structural discontinuity at
pump.fun -> PumpSwap migration.

Data: mfg_tokens.jsonl snapshots (per-mint, repeated; age_s clock from birth,
mcap_sol pre-grad, pool_mcap_sol / pool_liq_sol / pool flow post-grad).
Event time zero = first snapshot where grad=True.

For each graduated mint:
  - pre-grad features: seed, unique_buyers, bs_ratio, mcap path into graduation
  - event-time returns: pool_mcap at +5m/+15m/+60m (nearest snapshot) vs
    terminal curve mcap (~85 SOL) — and vs last pre-grad mcap when available
Output: distribution stats, runner/husk rates, conditioning splits.
"""
import json, statistics as st
from pathlib import Path

MON = Path(__file__).parent
GRAD_MCAP = 85.0  # terminal curve mcap approximation (SOL)

def load():
    toks = {}
    for line in open(MON / "mfg_tokens.jsonl"):
        try:
            d = json.loads(line)
        except Exception:
            continue
        m = d.get("mint")
        if not m:
            continue
        toks.setdefault(m, []).append(d)
    for v in toks.values():
        v.sort(key=lambda r: r.get("t", 0))
    return toks

def nearest(snaps, target_age, tol=420):
    best, bd = None, tol
    for s in snaps:
        a = s.get("age_s")
        if a is None:
            continue
        d = abs(a - target_age)
        if d < bd:
            best, bd = s, d
    return best

def main():
    toks = load()
    events = []
    for mint, snaps in toks.items():
        grad_idx = next((i for i, s in enumerate(snaps) if s.get("grad")), None)
        if grad_idx is None:
            continue
        g = snaps[grad_idx]
        t0 = g.get("t")
        g_age = g.get("age_s") or 0
        pre = [s for s in snaps[:grad_idx] if s.get("mcap_sol")]
        last_pre = pre[-1] if pre else None
        # event-time post-grad snapshots by age relative to grad age
        rows = {}
        for label, tgt in (("p5", g_age + 300), ("p15", g_age + 900), ("p60", g_age + 3600)):
            s = nearest(snaps[grad_idx:], tgt)
            if s and (s.get("pool_mcap_sol") or s.get("mcap_sol")):
                rows[label] = s.get("pool_mcap_sol") or s.get("mcap_sol")
        events.append({
            "mint": mint, "t0": t0, "g_age": g_age,
            "seed": g.get("seed"), "creator": g.get("creator"),
            "ub": g.get("unique_buyers"), "bs": g.get("bs_ratio"),
            "last_pre_mcap": last_pre.get("mcap_sol") if last_pre else None,
            **rows,
        })
    print(f"graduated mints: {len(events)}")
    with_mcap = [e for e in events if e["last_pre_mcap"]]
    print(f"with pre-grad mcap: {len(with_mcap)}")

    for lbl in ("p5", "p15", "p60"):
        rets = []
        for e in events:
            v = e.get(lbl)
            if v:
                base = e["last_pre_mcap"] or GRAD_MCAP
                rets.append(v / base)
        if not rets:
            print(f"{lbl}: no data"); continue
        rets.sort()
        n = len(rets)
        runners = sum(1 for r in rets if r >= 2.0)
        husks = sum(1 for r in rets if r <= 0.5)
        flat = sum(1 for r in rets if 0.8 <= r <= 1.25)
        print(f"{lbl}: n={n} median={st.median(rets):.2f}x mean={st.mean(rets):.2f}x "
              f"p25={rets[n//4]:.2f} p75={rets[3*n//4]:.2f} "
              f"runners={runners} ({100*runners/n:.0f}%) husks={husks} ({100*husks/n:.0f}%) flat={flat}")

    # conditioning: does pre-grad momentum predict post-grad outcome at +60m?
    both = [e for e in events if e.get("p60") and e["last_pre_mcap"]]
    if len(both) > 40:
        both.sort(key=lambda e: e["last_pre_mcap"])
        hi = both[len(both)*2//3:]
        lo = both[:len(both)//3]
        for name, grp in (("hot-into-grad (top 1/3 pre mcap)", hi),
                          ("cold-into-grad (bottom 1/3)", lo)):
            rr = [e["p60"] / e["last_pre_mcap"] for e in grp]
            run = sum(1 for r in rr if r >= 2.0)
            print(f"{name}: n={len(grp)} median +60m={st.median(rr):.2f}x runners={100*run/len(rr):.0f}%")

    # seed-size split (farm vs normal)
    farm = [e for e in events if (e.get("seed") or 0) >= 50]
    norm = [e for e in events if e.get("seed") is not None and e["seed"] < 50]
    for name, grp in (("farm-seed (>=50 SOL)", farm), ("normal-seed", norm)):
        rr = [e["p60"] / (e["last_pre_mcap"] or GRAD_MCAP) for e in grp if e.get("p60")]
        if rr:
            run = sum(1 for r in rr if r >= 2.0)
            print(f"{name}: n={len(rr)} median +60m={st.median(rr):.2f}x runners={100*run/len(rr):.0f}%")

    out = MON / "grad_event_study.json"
    json.dump(events, open(out, "w"))
    print("wrote", out)

if __name__ == "__main__":
    main()
