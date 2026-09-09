#!/usr/bin/env python3
"""liq_fire_split.py — §399: split-transaction liquidation fire path.

Why: the atomic flash recipe (liq_fire.fire_flash) cannot fit this class of
liquidatee in one transaction — the liquidatee's health-check accounts plus a
memecoin-liab Jupiter exit route exceed Solana's 64-account lock limit
(TooManyAccountLocks). Incumbent bots hit the same wall, which is why a
$359k-debt account has sat liquidatable for days.

Split design (own capital, no flash loan, no marginfi borrow):
  tx1  Jupiter swap SOL -> liab memecoin (sized to repay + buffer)
  tx2  marginfi deposit(liab ATA -> our mfi account)
       + oracle refreshes + lending_account_liquidate + withdraw_all(seized)
       -> seized collateral lands in our asset ATA
  tx3  Jupiter swap seized asset -> SOL
P&L = wallet SOL delta across the three txs minus fees. Leftover liab dust
stays as a deposit in our mfi account and is consumed by the NEXT fire on the
same bank (deposit is drawn first by the liquidate ix).

Safety: sim gate via liq_sim before any capital moves; tx2 is re-simulated
after tx1 lands (real balances) and aborted to an unwind swap if it fails;
live fire requires lt.live_enabled() AND the LIQ_SPLIT_FIRE_OK arming file;
SOL spend capped per fire.

CLI: python3 liq_fire_split.py <liquidatee> <asset_bank> <liab_bank> <seize_usd> [--live]
"""
import base64
import hashlib
import json
import struct
import sys
import time
from pathlib import Path

MON = Path(__file__).resolve().parent
sys.path.insert(0, str(MON))

import importlib.util
_spec = importlib.util.spec_from_file_location("live_trader", str(MON / "live_trader.py"))
lt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lt)

import liq_health as lh
import liq_flash as lf
from liq_sim import PROG, acct_raw, LIQ_STANDIN, LIQ_AUTH

DEPOSIT_DISC = hashlib.sha256(b"global:lending_account_deposit").digest()[:8]
ARM_FILE = MON / "LIQ_SPLIT_FIRE_OK"
LOG = MON / "liq_split_fires.jsonl"
MAX_SOL_PER_FIRE = 1.25          # hard cap on tx1 SOL spend (≈$130 at $103)
MIN_EDGE_USD = 1.0
EDGE_HAIRCUT = 0.80              # measured round-trip swap cost ~0.45% (abort 3iQs1g…), keep 80% of the bonus
BUY_BUFFER = 1.03                # buy 3% more liab than the computed repay


def _log(row):
    row["ts"] = time.time()
    with open(LOG, "a") as f:
        f.write(json.dumps(row) + "\n")


def _sol_balance(addr_s):
    return lh.rpc("getBalance", [addr_s])["result"]["value"] / 1e9


def _ata_balance(ata_s):
    v = lh.rpc("getAccountInfo", [ata_s, {"encoding": "base64"}])["result"]["value"]
    if not v:
        return 0
    raw = base64.b64decode(v["data"][0])
    return struct.unpack("<Q", raw[64:72])[0]


def _confirm(sig, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = lh.rpc("getSignatureStatuses", [[sig]])
        v = (st.get("result") or {}).get("value") or [None]
        if v and v[0]:
            if v[0].get("err"):
                return False, v[0]["err"]
            if v[0].get("confirmationStatus") in ("confirmed", "finalized"):
                return True, None
        time.sleep(1.5)
    return False, "confirm_timeout"


def build_tx2(tee_pk, asset_bank, liab_bank, asset_amount, deposit_amount, payer_b):
    """deposit + refreshes + liquidate + withdraw_all, one v0 tx over our ALTs."""
    from liq_sim import build_liq_ix
    lb_raw = acct_raw(liab_bank)
    group = lb_raw[41:73]
    lb_b = lt.b58dec(liab_bank)
    liab_ata = lf.ata(payer_b, lb_raw[8:40])
    liab_vault = lf.pda([b"liquidity_vault", lb_b], PROG)
    mfi_b = lt.b58dec(LIQ_STANDIN)
    deposit = (PROG, [(group, False, False), (mfi_b, True, False),
                      (payer_b, False, True), (lb_b, True, False),
                      (liab_ata, True, False), (liab_vault, True, False),
                      (lf.TOK, False, False)],
               DEPOSIT_DISC + struct.pack("<Q", deposit_amount) + b"\x00")
    obs = lf.recipe_obs(asset_bank, liab_bank)
    ixs = [lf.cu_price_ix(50_000), lf.cu_limit_ix(1_000_000), deposit]
    ixs += build_liq_ix(tee_pk, asset_bank, liab_bank, asset_amount, payer_b=payer_b)
    ixs.append(lf.build_withdraw_ix(asset_bank, obs))
    return lf.build_v0_tx(payer_b, ixs, lf.our_alts())


def fire_split(tee_pk, asset_bank, liab_bank, seize_usd, dry_run=True):
    row = {"kind": "liq_fire_split", "liquidatee": tee_pk,
           "asset_bank": asset_bank, "liab_bank": liab_bank,
           "seize_usd": seize_usd}
    wallet_key, wallet_addr = lt._load_key()
    payer_b = lt.b58dec(wallet_addr)

    banks = lh.load_banks()
    px = lh.load_prices(banks)
    dec = lh.load_decimals(banks)
    ab, bb = banks.get(asset_bank), banks.get(liab_bank)
    if not ab or not bb:
        row["result"] = "unknown_bank"; _log(row); return row
    a_px = px[ab["oracle"]]["px"]
    l_px = px[bb["oracle"]]["px"]
    a_dec, l_dec = dec[ab["mint"]], dec[bb["mint"]]
    fees = bb["liq_fee"] + bb["ins_fee"]
    est_edge = seize_usd * bb["liq_fee"] * EDGE_HAIRCUT
    row.update(asset_mint=ab["mint"], liab_mint=bb["mint"],
               est_edge_usd=round(est_edge, 2))
    if est_edge < MIN_EDGE_USD:
        row["result"] = "skip_below_min_edge"; _log(row); return row

    asset_amount = int(seize_usd / a_px * (10 ** a_dec))
    repay_usd = seize_usd / (1.0 + fees) * BUY_BUFFER
    liab_needed_raw = int(seize_usd / (1.0 + fees) / l_px * (10 ** l_dec))
    sol_px = None
    for bpk, b in banks.items():
        if b["mint"] == lt.SOL and b["oracle"] in px:
            sol_px = px[b["oracle"]]["px"]
            break
    if not sol_px:
        row["result"] = "no_sol_price"; _log(row); return row
    sol_spend = repay_usd / sol_px
    row.update(asset_amount=asset_amount, liab_needed_raw=liab_needed_raw,
               sol_spend=round(sol_spend, 4))
    if sol_spend > MAX_SOL_PER_FIRE:
        row["result"] = "over_spend_cap"; _log(row); return row

    # Gate 1: full liquidation simulation (health-math true) before capital moves
    # §400: reload from disk — the tracker process caches plain imports.
    import importlib
    import liq_sim
    importlib.reload(liq_sim)
    res = liq_sim.simulate(tee_pk, asset_bank, liab_bank, asset_amount)
    err = res.get("result", {}).get("value", {}).get("err")
    row["sim_err"] = err
    if err is not None:
        row["result"] = "sim_gate_fail"; _log(row); return row

    if dry_run:
        row["result"] = "dry_run_ok"; _log(row); return row

    ok, why = lt.live_enabled()
    if not ok:
        row["result"] = f"gate: {why}"; _log(row); return row
    if not ARM_FILE.exists():
        row["result"] = "not_armed (no LIQ_SPLIT_FIRE_OK)"; _log(row); return row

    sol0 = _sol_balance(wallet_addr)
    row["sol_before"] = sol0

    # tx1: SOL -> liab memecoin
    q = lt.jupiter_quote(bb["mint"], sol_spend, "buy")
    if int(q.get("outAmount", 0)) < liab_needed_raw:
        row["result"] = "quote_short"; _log(row); return row
    sig1 = lt._jupiter_submit(q)
    if isinstance(sig1, dict):
        sig1 = sig1.get("result")
    row["tx1_sig"] = sig1
    if not sig1:
        row["result"] = "tx1_send_fail"; _log(row); return row
    okc, errc = _confirm(sig1)
    if not okc:
        row["result"] = f"tx1_unconfirmed: {errc}"; _log(row); return row

    liab_ata_s = lt.b58enc(lf.ata(payer_b, lt.b58dec(bb["mint"])))
    dep_amt = _ata_balance(liab_ata_s)
    row["liab_ata_balance"] = dep_amt
    if dep_amt < liab_needed_raw:
        # unwind: swap whatever arrived back to SOL
        row["result"] = "tx1_fill_short_unwinding"
        _unwind(bb["mint"], dep_amt, row)
        _log(row); return row

    # tx2: deposit + liquidate + withdraw (real-balance sim, then send)
    try:
        tx2 = build_tx2(tee_pk, asset_bank, liab_bank, asset_amount, dep_amt, payer_b)
    except Exception as e:
        row["result"] = f"tx2_build_error: {str(e)[:200]}"
        _unwind(bb["mint"], dep_amt, row)
        _log(row); return row
    sim2 = lh.rpc("simulateTransaction", [tx2, {"encoding": "base64",
                  "sigVerify": False, "replaceRecentBlockhash": True}])
    val2 = (sim2.get("result") or {}).get("value") or {}
    row["tx2_sim_err"] = val2.get("err")
    if sim2.get("error") or val2.get("err"):
        row["result"] = "tx2_sim_fail_unwinding"
        row["tx2_logs_tail"] = [l for l in (val2.get("logs") or []) if "rror" in l][-4:]
        _unwind(bb["mint"], dep_amt, row)
        _log(row); return row
    sig2 = (lh.rpc("sendTransaction", [tx2, {"encoding": "base64"}]) or {}).get("result")
    row["tx2_sig"] = sig2
    if not sig2:
        row["result"] = "tx2_send_fail_unwinding"
        _unwind(bb["mint"], dep_amt, row)
        _log(row); return row
    okc, errc = _confirm(sig2)
    if not okc:
        row["result"] = f"tx2_unconfirmed: {errc} — MANUAL CHECK NEEDED"
        _log(row); return row

    # tx3: seized asset -> SOL (full ATA balance)
    asset_ata_s = lt.b58enc(lf.ata(payer_b, lt.b58dec(ab["mint"])))
    seized = _ata_balance(asset_ata_s)
    row["seized_raw"] = seized
    if seized:
        q3 = lt.jupiter_quote_sell(ab["mint"], seized)
        sig3 = lt._jupiter_submit(q3)
        if isinstance(sig3, dict):
            sig3 = sig3.get("result")
        row["tx3_sig"] = sig3
        if sig3:
            okc, errc = _confirm(sig3)
            if not okc:
                row["result"] = f"tx3_unconfirmed: {errc} — MANUAL CHECK NEEDED"
                _log(row); return row
        else:
            row["result"] = "tx3_send_fail — MANUAL CHECK NEEDED"
            _log(row); return row

    sol1 = _sol_balance(wallet_addr)
    row["sol_after"] = sol1
    row["net_sol"] = round(sol1 - sol0, 6)
    row["result"] = "confirmed"
    _log(row); return row


def _unwind(mint, raw_amount, row):
    """Swap whatever liab tokens we hold back to SOL after an abort."""
    try:
        q = lt.jupiter_quote_sell(mint, raw_amount)
        sig = lt._jupiter_submit(q)
        if isinstance(sig, dict):
            sig = sig.get("result")
        row["unwind_sig"] = sig
        if sig:
            _confirm(sig)
    except Exception as e:
        row["unwind_error"] = str(e)[:200]


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print(__doc__)
        sys.exit(1)
    live = "--live" in sys.argv
    out = fire_split(sys.argv[1], sys.argv[2], sys.argv[3],
                     float(sys.argv[4]), dry_run=not live)
    print(json.dumps(out, indent=1))
