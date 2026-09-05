#!/usr/bin/env python3
"""Sim-verify the real liquidation candidates through the program gate.

Each candidate: seize ~40% of debt value worth of the collateral asset.
A PASS here (no HealthyAccount error, liquidation executes) is the same gate
that killed the phantom whales — only sim-verified targets are real.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import liq_health as lh
import liq_sim

CANDS = [
    # (liquidatee, asset_bank_prefix, liab_bank_prefix, seize_usd)
    ("GFxxnJpDAjb3VQNsQNerqw5t3iicUnaBahBj65WLkNKu", "8g5qG6PV", "CCKtUs6C", 3000),
    ("9VtU887m9HCJ98pxhapksYXuS1Wtax4CKP7jMCtezTZo", "4gQYBXPg", "CCKtUs6C", 1000),
    ("FuNhzGJ54Yx218SNFHkxsmCdifgtA81nhSyZFFASoZHs", "27Cpv49j", "2s37akK2", 100),
]


def main():
    banks = lh.load_banks()
    px = lh.load_prices(banks)
    by_prefix = {}
    for pk, b in banks.items():
        by_prefix[pk[:8]] = (pk, b)
    for tee, ab_pre, lb_pre, seize_usd in CANDS:
        ab, abb = by_prefix[ab_pre]
        lb, lbb = by_prefix[lb_pre]
        d = lh.load_decimals({ab: abb}).get(abb["mint"])
        p = px.get(abb["oracle"])
        if not p or d is None:
            print(f"{tee[:12]}: cannot price asset bank"); continue
        amount = int(seize_usd / p["px"] * (10 ** d))
        print(f"\n=== {tee[:12]} seize ${seize_usd} of {abb['mint'][:8]} ({amount} native) "
              f"repay via {lbb['mint'][:8]}")
        try:
            res = liq_sim.simulate(tee, ab, lb, amount)
            val = res.get("result", {}).get("value", {})
            err = val.get("err")
            logs = val.get("logs") or []
            print("err:", err)
            interesting = [l for l in logs if any(k in l for k in
                           ("Error", "error", "health", "Health", "liquidat", "Liquidat",
                            "Instruction: ", "insufficient", "Insufficient"))]
            for l in interesting[:12]:
                print("  ", l)
        except Exception as e:
            print("EXC:", e)


if __name__ == "__main__":
    main()
