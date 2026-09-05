#!/usr/bin/env python3
"""Validate the conf-band patch against the on-chain sim ground truth.

Account 57WvwCCthAhm (JLP whale): marginfi program computed (§355 sim)
  assets = $227,634  liabs = $195,018  => health = +$32,616 (HEALTHY)
The patched liq_health pricing must reproduce that within a few %.
"""
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import liq_health as lh

TARGET = "57WvwCCthAhm2a1FdUVn1vwBpdHRr6SFkJpQFJqS4vSe"  # prefix from §355
SIM_ASSETS, SIM_LIABS = 227634.0, 195018.0


def main():
    banks = lh.load_banks()
    px = lh.load_prices(banks)
    dec = lh.load_decimals(banks)
    print(f"banks={len(banks)} oracles={len(px)} mints={len(dec)}")

    res = lh.rpc("getProgramAccounts", [lh.PROG, {
        "encoding": "base64",
        "filters": [
            {"memcmp": {"offset": 0, "bytes": lh.disc("MarginfiAccount")}},
            {"memcmp": {"offset": 40, "bytes": "5"}},  # placeholder, fixed below
        ],
    }])
    # simpler: fetch account directly by its full pubkey — search log first
    full_pk = None
    log = Path(lh.MON / "liq_health_log.jsonl")
    for line in log.read_text().splitlines()[::-1]:
        try:
            rec = json.loads(line)
        except Exception:
            continue
        for m in rec.get("top20", []) + rec.get("liquidatable_now", []):
            if m["pk"].startswith("57WvwCCthAhm"):
                full_pk = m["pk"]
                break
        if full_pk:
            break
    if not full_pk:
        print("could not recover full pubkey from log"); return
    print("target:", full_pk)

    v = lh.rpc("getAccountInfo", [full_pk, {"encoding": "base64"}])["result"]["value"]
    raw = base64.b64decode(v["data"][0])
    bal = raw[lh.BAL_OFF:lh.BAL_OFF + lh.STRIDE * lh.SLOTS]

    assets = liabs = 0.0
    rows = []
    slots = []
    for i in range(lh.SLOTS):
        o = i * lh.STRIDE
        if bal[o] != 1:
            continue
        bpk = lh.b58encode(bal[o + 1:o + 33])
        b = banks.get(bpk)
        if not b:
            continue
        p = px.get(b["oracle"])
        d = dec.get(b["mint"])
        if not p or d is None:
            rows.append((bpk[:8], "no price/dec")); continue
        a_sh = lh.i80(bal[o + 40:o + 56]) * b["asset_sv"]
        l_sh = lh.i80(bal[o + 56:o + 72]) * b["liab_sv"]
        band = min(lh.CONF_K * p["conf_px"], lh.CONF_CAP * p["px"])
        slots.append({"bpk": bpk[:8], "b": b, "a_nat": a_sh / (10 ** d),
                      "l_nat": l_sh / (10 ** d),
                      "px_lo": p["px"] - band, "px_hi": p["px"] + band})
    liab_slots = [s for s in slots if s["l_nat"] > 0]
    rec = None
    for s in liab_slots:
        ent = dict(s["b"]["emode_entries"])
        if rec is None:
            rec = ent
        else:
            for t in list(rec):
                if t in ent:
                    rec[t] = min(rec[t], ent[t])
                else:
                    del rec[t]
    rec = rec or {}
    for s in slots:
        b = s["b"]
        a = l = 0.0
        if s["a_nat"] > 0 and b["risk_tier"] != 1:
            w = b["aw_maint"]
            if b["emode_tag"]:
                w = max(w, rec.get(b["emode_tag"], 0.0))
            a = s["a_nat"] * s["px_lo"] * w
            assets += a
        if s["l_nat"] > 0:
            l = s["l_nat"] * s["px_hi"] * b["lw_maint"]
            liabs += l
        rows.append((s["bpk"], f"a=${a:,.0f} l=${l:,.0f} emode_tag={b['emode_tag']} rec={rec}"))
    for r in rows:
        print("  ", r)
    print(f"\nscanner: assets=${assets:,.0f} liabs=${liabs:,.0f} health=${assets-liabs:,.0f}")
    print(f"sim    : assets=${SIM_ASSETS:,.0f} liabs=${SIM_LIABS:,.0f} health=${SIM_ASSETS-SIM_LIABS:,.0f}")
    da = abs(assets - SIM_ASSETS) / SIM_ASSETS
    dl = abs(liabs - SIM_LIABS) / SIM_LIABS
    print(f"match  : assets {da:.2%} off, liabs {dl:.2%} off ->",
          "PASS" if da < 0.05 and dl < 0.05 else "NEEDS k/CAP FIT")


if __name__ == "__main__":
    main()
