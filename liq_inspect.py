#!/usr/bin/env python3
"""Inspect raw positions of liquidation candidates from the last health scan.

For each candidate: every active slot with bank, mint, RAW (unweighted) asset
and liability USD, risk tier, and emode tag. Tells us what is actually
seizable — health-weighted assets of $0 can still hide raw isolated collateral.
"""
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import liq_health as lh


def main():
    banks = lh.load_banks()
    px = lh.load_prices(banks)
    dec = lh.load_decimals(banks)
    mint_to_sym = {}
    # read last scan for candidates
    log = Path(lh.MON / "liq_health_log.jsonl")
    last = json.loads(log.read_text().splitlines()[-1])
    cands = last.get("liquidatable_now", [])
    print(f"{len(cands)} candidates from scan ts={last['ts']:.0f}\n")
    for m in cands:
        pk = m["pk"]
        v = lh.rpc("getAccountInfo", [pk, {"encoding": "base64"}])["result"]["value"]
        raw = base64.b64decode(v["data"][0])
        bal = raw[lh.BAL_OFF:lh.BAL_OFF + lh.STRIDE * lh.SLOTS]
        print(f"{pk}  health={m['health']}")
        for i in range(lh.SLOTS):
            o = i * lh.STRIDE
            if bal[o] != 1:
                continue
            bpk = lh.b58encode(bal[o + 1:o + 33])
            b = banks.get(bpk)
            if not b:
                print(f"   slot{i}: unknown bank {bpk[:12]}")
                continue
            p = px.get(b["oracle"])
            d = dec.get(b["mint"])
            a_sh = lh.i80(bal[o + 40:o + 56]) * b["asset_sv"]
            l_sh = lh.i80(bal[o + 56:o + 72]) * b["liab_sv"]
            pxv = p["px"] if p else 0.0
            a_raw = a_sh / (10 ** d) * pxv if d is not None else -1
            l_raw = l_sh / (10 ** d) * pxv if d is not None else -1
            tier = {0: "COLL", 1: "ISOL"}.get(b["risk_tier"], b["risk_tier"])
            print(f"   slot{i}: bank={bpk[:8]} mint={b['mint'][:8]} tier={tier} "
                  f"etag={b['emode_tag']} A=${a_raw:,.2f} L=${l_raw:,.2f}")
        print()


if __name__ == "__main__":
    main()
