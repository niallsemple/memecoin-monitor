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
SOL_MINT = "So11111111111111111111111111111111111111112"
ROUTE_CACHE = MON / "liq_routable.json"
OUR_MFI = "A91fDng3SdKxBMPq4DxUSE4LKqBR1g6tf3rC8ypvogRy"


def jup_routable(mint: str) -> bool:
    """§370: staked LST collateral is often TOKEN_NOT_TRADABLE on Jupiter —
    no exit leg, so the candidate is untradeable via the flash recipe.
    Cached per mint."""
    try:
        cache = json.loads(ROUTE_CACHE.read_text())
    except Exception:
        cache = {}
    if mint in cache:
        return cache[mint]
    import urllib.error
    import urllib.request
    ok = True
    try:
        q = (f"inputMint={mint}&outputMint={SOL_MINT}"
             f"&amount=1000000&slippageBps=300")
        urllib.request.urlopen(f"https://lite-api.jup.ag/swap/v1/quote?{q}",
                               timeout=15).read()
    except urllib.error.HTTPError as e:
        if e.code == 400:
            ok = False
    except Exception:
        pass  # transient: don't cache a negative
    cache[mint] = ok
    ROUTE_CACHE.write_text(json.dumps(cache))
    return ok


def our_holds_nonstaked(banks: dict) -> bool:
    """§371 (6047): an account holding non-staked assets cannot absorb staked
    collateral. True if OUR marginfi account has any active non-staked asset."""
    import liq_health as lh
    raw = lh.rpc("getAccountInfo", [OUR_MFI, {"encoding": "base64"}])
    v = raw["result"]["value"]
    data = base64.b64decode(v["data"][0])
    bal = data[lh.BAL_OFF:lh.BAL_OFF + lh.STRIDE * lh.SLOTS]
    for i in range(lh.SLOTS):
        o = i * lh.STRIDE
        if bal[o] != 1:
            continue
        if lh.i80(bal[o + 40:o + 56]) <= 0:   # asset shares
            continue
        b = banks.get(lh.b58encode(bal[o + 1:o + 33]))
        if b and b.get("tag") != 2:
            return True
    return False


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
            elif banks.get(best_asset[1], {}).get("tag") == 2:
                # §371 (6047): staked collateral can only be absorbed by an
                # account holding ONLY staked assets, and the liab must be SOL
                if best_liab[2] != SOL_MINT:
                    rec["skipped"] = "staked_liab_not_sol_6047"
                elif our_holds_nonstaked(banks):
                    rec["skipped"] = "staked_blocked_6047"
                elif not jup_routable(best_asset[2]):
                    rec["skipped"] = "unroutable_collateral"
            elif not jup_routable(best_asset[2]):
                rec["skipped"] = "unroutable_collateral"
            if (not rec.get("skipped") and best_asset and best_liab
                    and best_asset[0] >= MIN_SEIZE_USD and sims_left > 0):
                sims_left -= 1
                import liq_sim
                seize_usd = min(best_asset[0], best_liab[0] * SEIZE_FRACTION,
                                50.0)  # own-capital envelope until flash ships
                rec["asset_bank"] = best_asset[1]
                rec["liab_bank"] = best_liab[1]
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
                    # §371: flash recipe is the primary fire path — atomic
                    # exit, no capital, works once gates pass. Legacy
                    # deposit+borrow fire only as build-error fallback.
                    try:
                        import liq_fire
                        fr = liq_fire.fire_flash(pk, best_asset[1], best_liab[1],
                                                 amount, seize_usd)
                        if fr.get("result") in ("build_error", "skip_integrated_no_mult"):
                            fr = liq_fire.fire(pk, best_asset[1], best_liab[1],
                                               amount, seize_usd)
                            rec["fire_path"] = "legacy"
                        else:
                            rec["fire_path"] = "flash"
                        rec["fire_result"] = fr.get("result")
                        rec["fire_sig"] = fr.get("sig")
                        if (fr.get("result") == "confirmed"
                                and rec.get("fire_path") == "legacy"):
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
