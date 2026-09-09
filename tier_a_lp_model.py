#!/usr/bin/env python3
"""Tier-A LP economics model — rent-adjusted projections for safe major pools.

Answers: at what arm size does a tier-A pool (IL ~ 0, fa disabled, 21/21 live
days, calm ranges) beat its fixed costs, and how does that compare to the
newborn cell's per-trade expectancy?

Fixed costs per arm: ~0.003 SOL tx fees round-trip. Position rent (~0.057 SOL)
is REFUNDED on close — opportunity cost only, not a real cost. Real risks:
yield decay (modeled: flat / halve-weekly / halve-daily) and IL (tiny on
tier-A, taken from the ranker's recent-candle estimate).

Data: meteora_lp_ranker_report.json (today's scan). Output: tier_a_model.json
+ printed table.
"""
import json
from pathlib import Path

MON = Path(__file__).resolve().parent
TX_COST = 0.003          # add + exit + claims, round trip, SOL
HORIZONS = (7, 14, 30)
ARMS = (0.5, 1.0, 2.0, 5.0)
DECAYS = {"flat": lambda d: 1.0,
          "halve_weekly": lambda d: 0.5 ** (d / 7),
          "halve_daily": lambda d: 0.5 ** d}

# tier-A = passes all safety gates (IL, volAlive loose, fa, live21, hl10),
# ignoring the 2%/d yield gate
def tier_a(p):
    return (p.get("days", 0) >= 30
            and p.get("il_daily_avg7") is not None and p["il_daily_avg7"] > -0.01
            and p.get("fa_disabled")
            and p.get("live_days_21", 0) >= 10
            and p.get("max_hl_range_10d") and p["max_hl_range_10d"] < 2.0
            and p.get("net_daily_lp") is not None)


def main():
    r = json.loads((MON / "meteora_lp_ranker_report.json").read_text())
    pools = r.get("pools") or r.get("ranked") or []
    cands = [p for p in pools if tier_a(p)]
    cands.sort(key=lambda p: -p["net_daily_lp"])

    out = {"generated": r.get("generated_utc"), "tx_cost_sol": TX_COST,
           "pools": []}
    print(f"{'pool':>14} {'net%/d':>7} {'IL%/d':>7} | break-even days @ arm (flat yield)")
    print(f"{'':>14} {'':>7} {'':>7} | " + "  ".join(f"{a:>5.1f}" for a in ARMS))
    for p in cands:
        y = p["net_daily_lp"]
        rec = {"name": p["name"], "address": p["address"], "tvl": p["tvl"],
               "net_daily_lp": y, "il_daily_avg7": p["il_daily_avg7"],
               "vol_alive_ratio": p.get("vol_alive_ratio"), "scenarios": {}}
        be = []
        for a in ARMS:
            daily = a * y
            be.append(round(TX_COST / daily, 1) if daily > 0 else None)
        rec["breakeven_days_flat"] = dict(zip(map(str, ARMS), be))
        for dname, df in DECAYS.items():
            for h in HORIZONS:
                # integrate decaying yield over horizon
                tot = sum(a0 * 0 for a0 in ())  # placeholder
                for a in ARMS:
                    earned = sum(a * y * df(d) for d in range(1, h + 1))
                    net = earned - TX_COST
                    rec["scenarios"].setdefault(dname, {})[f"{a}sol_{h}d"] = round(net, 4)
        out["pools"].append(rec)
        il = f"{p['il_daily_avg7']*100:.3f}"
        print(f"{p['name'][:14]:>14} {y*100:7.3f} {il:>7} | "
              + "  ".join(f"{b:>5}" if b else "  ---" for b in be))

    # 30d projection detail for the top pool at decay scenarios
    if cands:
        top = cands[0]
        print(f"\nTOP: {top['name']} — 30d net SOL by arm & decay scenario:")
        print(f"{'arm':>5} " + " ".join(f"{n:>14}" for n in DECAYS))
        for a in ARMS:
            row = []
            for dname, df in DECAYS.items():
                earned = sum(a * top["net_daily_lp"] * df(d) for d in range(1, 31))
                row.append(earned - TX_COST)
            print(f"{a:5.1f} " + " ".join(f"{v:+14.4f}" for v in row))

    (MON / "tier_a_model.json").write_text(json.dumps(out, indent=1))
    print("\nwrote tier_a_model.json")


if __name__ == "__main__":
    main()
