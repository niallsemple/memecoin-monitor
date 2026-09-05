#!/usr/bin/env python3
"""liq_hunt.py — candidate drill-down + on-chain sim gate for the radar.

Called by the tracker pass right after liq_health.main() when the scan found
health<0 accounts. For each candidate: inspect raw (unweighted) positions to
find seizable collateral; if seizable >= MIN_SEIZE_USD, run the real
liquidate transaction through simulateTransaction with OUR marginfi account
(§358). Only sim-verified opportunities are logged as actionable.

Log: liq_opportunities.jsonl — one record per candidate per pass.
"""
import base64
import json
import sys
import time
from pathlib import Path

MON = Path(__file__).resolve().parent
sys.path.insert(0, str(MON))

LOG_PATH = str(MON / "liq_opportunities.jsonl")
MIN_SEIZE_USD = 50.0
MAX_SIMS = 2
SEIZE_FRACTION = 0.40  # sim a partial seize sized at 40% of debt value


def hunt(record: dict) -> list:
    import liq_health as lh
    cands = record.get("liquidatable_now") or []
    if not cands:
        return []
    banks = lh.load_banks()
    px = lh.load_prices(banks)
    dec = lh.load_decimals(banks)
    out = []
    sims_left = MAX_SIMS
    for m in cands[:8]:
        pk = m["pk"]
        rec = {"ts": time.time(), "pk": pk, "health": m["health"],
               "assets": m["assets"], "liabs": m["liabs"]}
        # §366 twilight gate: scanner proved no pair can improve health —
        # drilling is wasted RPC and any fire would fail 6072.
        if m.get("feasible") is False:
            rec["skipped"] = "twilight_zone"
            out.append(rec)
            continue
        try:
            v = lh.rpc("getAccountInfo", [pk, {"encoding": "base64"}])["result"]["value"]
            raw = base64.b64decode(v["data"][0])
            bal = raw[lh.BAL_OFF:lh.BAL_OFF + lh.STRIDE * lh.SLOTS]
            assets, liabs = [], []
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
                    continue
                mult = b.get("mult") or 1.0
                a_usd = lh.i80(bal[o + 40:o + 56]) * b["asset_sv"] / (10 ** d) * p["px"] * mult
                l_usd = lh.i80(bal[o + 56:o + 72]) * b["liab_sv"] / (10 ** d) * p["px"] * mult
                if a_usd > 1 and b["risk_tier"] != 1:
                    assets.append((a_usd, bpk, b["mint"], d, p["px"] * mult, b["aw_maint"]))
                if l_usd > 1:
                    liabs.append((l_usd, bpk, b["mint"], b["lw_maint"],
                                  b["liq_fee"] + b["ins_fee"], b["liq_fee"]))
            # §366: pick the best FEASIBLE pair — a seize only improves health
            # when aw_asset < (1 - fees) * lw_liab. Base weight used
            # (conservative: emode can only loosen the inequality).
            best_asset = best_liab = None
            best_cov = 0.0
            for a in assets:
                for l in liabs:
                    if a[5] < (1.0 - l[4]) * l[3]:
                        cov = min(a[0], l[0])
                        if cov > best_cov:
                            best_cov = cov
                            best_asset = a
                            best_liab = l
            rec["seizable_usd"] = round(best_asset[0], 2) if best_asset else 0.0
            rec["seize_mint"] = best_asset[2] if best_asset else None
            rec["repay_mint"] = best_liab[2] if best_liab else None
            if not best_asset or not best_liab:
                rec["skipped"] = "no_feasible_pair"
            if best_asset and best_liab and best_asset[0] >= MIN_SEIZE_USD and sims_left > 0:
                sims_left -= 1
                import liq_sim
                seize_usd = min(best_asset[0], best_liab[0] * SEIZE_FRACTION,
                                50.0)  # own-capital envelope until flash ships
                amount = int(seize_usd / best_asset[4] * (10 ** best_asset[3]))
                res = liq_sim.simulate(pk, best_asset[1], best_liab[1], amount)
                err = res.get("result", {}).get("value", {}).get("err")
                rec["sim_err"] = err
                rec["sim_seize_usd"] = round(seize_usd, 2)
                rec["actionable"] = err is None
                if err is None:
                    # liquidator's bonus = the liab bank's actual liquidator
                    # fee (insurance portion goes to the bank, not us)
                    rec["est_gross_usd"] = round(seize_usd * best_liab[5], 2)
                    # §362: armed live fire (owner authorized live test).
                    # fire() re-sims signed and fail-closes on any error.
                    try:
                        import liq_fire
                        fr = liq_fire.fire(pk, best_asset[1], best_liab[1],
                                           amount, seize_usd)
                        rec["fire_result"] = fr.get("result")
                        rec["fire_sig"] = fr.get("sig")
                        if fr.get("result") == "confirmed":
                            ex = liq_fire.exit_seized(best_asset[1], best_asset[2],
                                                      best_asset[3])
                            rec["exit_result"] = ex.get("result")
                            rec["exit_out_sol"] = ex.get("exit_quote_out_sol")
                    except Exception as e:
                        rec["fire_error"] = str(e)[:200]
        except Exception as e:
            rec["error"] = str(e)[:200]
        out.append(rec)
    if out:
        with open(LOG_PATH, "a") as f:
            for r in out:
                f.write(json.dumps(r) + "\n")
    return out


if __name__ == "__main__":
    import liq_health as lh
    log = Path(LOG_PATH)
    last = json.loads((MON / "liq_health_log.jsonl").read_text().splitlines()[-1])
    print(json.dumps(hunt(last), indent=1))
