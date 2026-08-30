#!/usr/bin/env python3
"""mfg_report.py — runner/husk feature analyzer for the MFG tracker (§56).

Reads mfg_tokens.jsonl snapshots (+5m/+15m/+60m per tracked big-seed birth)
and answers the tradeable question: which features visible in the first
minutes after a manufactured launch separate runner-destined tokens from
husk-destined ones?

Outcome labels (from snapshot data only — honest, no external lookups):
  RUNNER: graduated AND +60m mcap >= 100 SOL (held above graduation ~85)
  HUSK:   graduated AND +60m mcap <= 45 SOL  (collapsed >~50% post-grad)
          OR never graduated AND +60m mcap <= 20 SOL AND notifs_15m flat
  (everything else = UNLABELLED — too young or ambiguous)

Usage: python3 mfg_report.py [--json out.json]
"""
import argparse
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

MON = Path("/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor")
SNAPS = MON / "mfg_tokens.jsonl"

GRAD_MCAP = 85.0        # approximate terminal curve mcap in SOL
POOL_RUNNER_FLOOR = 150.0  # +60m pool mcap >= this (~2x terminal) => runner-leaning
HUSK_CEIL = 45.0        # graduated but +60m mcap <= this => husk
DEAD_CEIL = 20.0        # never graduated and +60m mcap <= this => husk


def load_tokens():
    by_mint = defaultdict(dict)
    if not SNAPS.exists():
        return by_mint
    for line in SNAPS.read_text().splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        mint = r.get("mint")
        age = r.get("age_s")
        if mint and age:
            by_mint[mint][age] = r
    return by_mint


def label(snaps):
    """Outcome labels (§56b, pool-aware):
    - Graduated: use pool_mcap_sol (live PumpSwap marginal price at +60m).
      RUNNER >= 150 SOL (~2x the ~85 terminal), HUSK <= 45 (~half terminal).
      CAVEAT: pool mcap is marginal price x 1e9 supply; on thin manufactured
      pools it is inflated by design. Treat RUNNER as 'runner-leaning' and
      confirm with pool_buy_sol / pool_flow_ratio before trusting it.
    - Never graduated: HUSK when +60m curve mcap <= 20 (curve still live).
    - Graduated but no pool data yet: GRAD_POOL_NEEDED."""
    s60 = snaps.get(3600)
    if not s60:
        return None
    if s60.get("grad"):
        pm = s60.get("pool_mcap_sol")
        if pm is None:
            return "GRAD_POOL_NEEDED"
        if pm >= POOL_RUNNER_FLOOR:
            return "RUNNER"
        if pm <= HUSK_CEIL:
            return "HUSK"
        return None
    mcap = s60.get("mcap_sol")
    if mcap is None:
        return None
    if mcap <= DEAD_CEIL:
        return "HUSK"
    return None


def feat(s):
    if not s:
        return None
    return {"bs_ratio": s.get("bs_ratio"), "flow_ratio": s.get("flow_ratio"),
            "notifs": s.get("notifs"), "buy_sol": s.get("buy_sol"),
            "sell_sol": s.get("sell_sol"), "mcap_sol": s.get("mcap_sol"),
            "seed": s.get("seed"), "grad": s.get("grad")}


def med(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(st.median(xs), 2) if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write machine-readable report here")
    args = ap.parse_args()

    by_mint = load_tokens()
    n_snaps = sum(len(v) for v in by_mint.values())
    labelled = {"RUNNER": [], "HUSK": [], "GRAD_POOL_NEEDED": []}
    young = 0
    for mint, snaps in by_mint.items():
        lab = label(snaps)
        if lab:
            labelled[lab].append((mint, snaps))
        else:
            young += 1

    print(f"MFG tracker report — {len(by_mint)} tracked tokens, {n_snaps} snapshots")
    print(f"labelled: {len(labelled['RUNNER'])} RUNNER, {len(labelled['HUSK'])} HUSK, "
          f"{len(labelled['GRAD_POOL_NEEDED'])} graduated (outcome needs pool data), "
          f"{young} unlabelled (need +60m snapshot)\n")

    report = {"tokens": len(by_mint), "snapshots": n_snaps,
              "runners": len(labelled["RUNNER"]), "husks": len(labelled["HUSK"]),
              "grad_pool_needed": len(labelled["GRAD_POOL_NEEDED"]),
              "unlabelled": young, "features": {}}

    for age in (300, 900):
        print(f"--- features at +{age//60}m (median) ---")
        print(f"{'feature':<12} {'RUNNER':>10} {'HUSK':>10}")
        report["features"][f"plus_{age}s"] = {}
        rows = defaultdict(lambda: defaultdict(list))
        for lab, group in ((k, v) for k, v in labelled.items() if k != "GRAD_POOL_NEEDED"):
            for mint, snaps in group:
                f = feat(snaps.get(age))
                if f:
                    for k, v in f.items():
                        rows[k][lab].append(v)
        for k in ("seed", "bs_ratio", "flow_ratio", "notifs",
                  "buy_sol", "sell_sol", "mcap_sol"):
            r = med(rows[k]["RUNNER"]); h = med(rows[k]["HUSK"])
            print(f"{k:<12} {str(r):>10} {str(h):>10}")
            report["features"][f"plus_{age}s"][k] = {"runner": r, "husk": h}
        print()

    # pool-feature comparison at +60m for graduated labelled tokens
    pfeats = ("pool_mcap_sol", "pool_liq_sol", "pool_flow_ratio",
              "pool_buy_sol", "pool_sell_sol", "pool_buys", "pool_sells")
    prows = defaultdict(lambda: defaultdict(list))
    for lab in ("RUNNER", "HUSK"):
        for mint, snaps in labelled[lab]:
            s60 = snaps.get(3600)
            if s60 and s60.get("grad"):
                for k in pfeats:
                    prows[k][lab].append(s60.get(k))
    if any(prows[k]["RUNNER"] or prows[k]["HUSK"] for k in pfeats):
        print("--- POOL features at +60m, graduated tokens (median) ---")
        print(f"{'feature':<16} {'RUNNER':>12} {'HUSK':>12}")
        report["features"]["pool_plus_3600s"] = {}
        for k in pfeats:
            r = med(prows[k]["RUNNER"]); h = med(prows[k]["HUSK"])
            print(f"{k:<16} {str(r):>12} {str(h):>12}")
            report["features"]["pool_plus_3600s"][k] = {"runner": r, "husk": h}
        print("note: pool_mcap is marginal price x 1e9 — inflated on thin "
              "manufactured pools; pool_liq_sol and flow are the truer reads.\n")

    if labelled["GRAD_POOL_NEEDED"]:
        print("--- graduated, pool data pending ---")
        for mint, snaps in labelled["GRAD_POOL_NEEDED"][:10]:
            s60 = snaps.get(3600) or {}
            print(f"{(s60.get('symbol') or '?')[:16]:<16} seed={s60.get('seed')!s:<6}")
        print()
    if labelled["RUNNER"]:
        print("--- labelled RUNNERs ---")
        for mint, snaps in sorted(labelled["RUNNER"],
                                  key=lambda x: -(x[1].get(3600, {}).get("mcap_sol") or 0)):
            s5 = snaps.get(300) or {}
            s60 = snaps.get(3600) or {}
            print(f"{(s5.get('symbol') or '?')[:16]:<16} seed={s5.get('seed')!s:<6} "
                  f"+5m flow={s5.get('flow_ratio')!s:<6} "
                  f"pool_mcap={s60.get('pool_mcap_sol')} "
                  f"pool_flow={s60.get('pool_flow_ratio')} "
                  f"pool_buy_sol={s60.get('pool_buy_sol')} "
                  f"pool_liq={s60.get('pool_liq_sol')}")
        print()
    if labelled["HUSK"]:
        print("--- labelled HUSKs (first 10) ---")
        for mint, snaps in labelled["HUSK"][:10]:
            s5 = snaps.get(300) or {}
            s60 = snaps.get(3600) or {}
            print(f"{(s5.get('symbol') or '?')[:16]:<16} seed={s5.get('seed')!s:<6} "
                  f"+5m flow={s5.get('flow_ratio')!s:<6} "
                  f"pool_mcap={s60.get('pool_mcap_sol')} "
                  f"pool_flow={s60.get('pool_flow_ratio')} "
                  f"pool_buy_sol={s60.get('pool_buy_sol')} "
                  f"pool_liq={s60.get('pool_liq_sol')}")

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2))
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
