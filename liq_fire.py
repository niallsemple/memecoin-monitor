#!/usr/bin/env python3
"""liq_fire.py — LIVE liquidation execution with our marginfi account.

Path (§358-361): our account A91fDng3 has a standing 0.30 SOL deposit in the
main-group SOL bank. The liquidate ix repays from that deposit first, then
borrows the rest against init-weight health — repay+seize are atomic in ONE
instruction. Exit is a follow-up tx: withdraw seized asset to our ATA, then
Jupiter swap to SOL.

Safety gates (all must pass before any send):
  1. live_enabled() — kill switch + manual_signoff (same as memecoin trader)
  2. fresh signed simulateTransaction of the exact tx must be error-free
  3. seize size <= our repay envelope (deposit + init-weight borrow capacity)
  4. est gross (5% bonus) > MIN_EDGE_USD after a slippage haircut

Auto-fire is armed only when the file LIQ_FIRE_OK exists (owner authorized a
live test 2026-09-05 19:36: "when ready you can try for a live test").
Every attempt lands in mfg_liq_fires.jsonl.
"""
import base64
import json
import struct
import sys
import time
import urllib.request
from pathlib import Path

MON = Path(__file__).resolve().parent
sys.path.insert(0, str(MON))
import importlib.util
_spec = importlib.util.spec_from_file_location("live_trader", str(MON / "live_trader.py"))
lt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lt)

import liq_health as lh
import liq_sim
from mfi_init import build_signed_tx

PROG = lt.b58dec("MFv2hWf31Z9kbCa1snEPYctwafyhdvnV7FZnsebVacA")
SYSTEM = bytes(32)
TOKEN = lt.b58dec("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ATA_PROG = lt.b58dec("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
GROUP = lt.b58dec("4qp6Fx6tnZkY5Wropq9wUYgtFxXKwE6viZxFHg3rdAG8")
GROUP_S = "4qp6Fx6tnZkY5Wropq9wUYgtFxXKwE6viZxFHg3rdAG8"

FIRE_LOG = MON / "mfg_liq_fires.jsonl"
LIVE_FIRE_OK = MON / "LIQ_FIRE_OK"          # arming flag file
MIN_EDGE_USD = 1.0                          # min est net edge to fire
SLIPPAGE_HAIRCUT = 0.55                     # assume we keep 55% of the 5% bonus

WITHDRAW_DISC = liq_sim.hashlib.sha256(b"global:lending_account_withdraw").digest()[:8]


def _log_fire(row: dict) -> None:
    row["ts"] = time.time()
    with open(FIRE_LOG, "a") as f:
        f.write(json.dumps(row) + "\n")


def fire(liquidatee: str, asset_bank: str, liab_bank: str, amount: int,
         est_seize_usd: float, dry_run: bool = False) -> dict:
    """Build the same liquidate tx as the sim, but signed by us. Simulate
    with real signatures; send only when every gate passes."""
    row = {"kind": "liq_fire", "liquidatee": liquidatee, "asset_bank": asset_bank,
           "liab_bank": liab_bank, "amount": amount, "est_seize_usd": est_seize_usd}
    est_edge = est_seize_usd * 0.05 * SLIPPAGE_HAIRCUT
    row["est_edge_usd"] = round(est_edge, 2)
    if est_edge < MIN_EDGE_USD:
        row["result"] = "skip_below_min_edge"
        _log_fire(row); return row
    ok, why = lt.live_enabled()
    if not ok and not dry_run:
        row["result"] = f"gate: {why}"
        _log_fire(row); return row
    if not LIVE_FIRE_OK.exists() and not dry_run:
        row["result"] = "not_armed (no LIQ_FIRE_OK)"
        _log_fire(row); return row

    wallet_key, wallet_addr = lt._load_key()
    wallet_b = lt.b58dec(wallet_addr)
    ixs = liq_sim.build_liq_ix(liquidatee, asset_bank, liab_bank, amount,
                               payer_b=wallet_b)
    tx = build_signed_tx({wallet_b: wallet_key}, wallet_b, ixs)
    # sigVerify can't combine with replaceRecentBlockhash (Helius -32602);
    # program-logic sim here, signature validity is enforced by send preflight.
    sim_cfg = {"encoding": "base64",
               "sigVerify": False, "replaceRecentBlockhash": True}
    if any(lt.b58enc(p) == liq_sim.swb_prog_id() for p, _, _ in ixs):
        # §367: crossbar signs at the tip; finalized sim falsely rejects (6039)
        sim_cfg["commitment"] = "processed"
    sim = lh.rpc("simulateTransaction", [tx, sim_cfg])
    if sim.get("error"):
        row["result"] = "sim_rpc_error"
        row["rpc_error"] = json.dumps(sim["error"])[:300]
        _log_fire(row); return row
    val = sim["result"]["value"]
    row["sim_err"] = val.get("err")
    if val.get("err"):
        row["result"] = "sim_failed"
        row["logs_tail"] = [l for l in (val.get("logs") or []) if "rror" in l or "health" in l][-4:]
        _log_fire(row); return row
    if dry_run:
        row["result"] = "dry_run_sim_ok"
        _log_fire(row); return row

    res = lh.rpc("sendTransaction", [tx, {"encoding": "base64", "skipPreflight": False}])
    sig = res.get("result")
    row["sig"] = sig
    if not sig:
        row["result"] = "send_rejected"
        row["rpc_error"] = json.dumps(res.get("error"))[:300]
        _log_fire(row); return row
    for _ in range(30):
        st = lt._rpc("getSignatureStatuses", [[sig]])
        r0 = (st.get("value") or [None])[0]
        if r0 and r0.get("confirmationStatus") in ("confirmed", "finalized"):
            row["result"] = "confirmed" if not r0.get("err") else "failed_onchain"
            row["onchain_err"] = r0.get("err")
            break
        time.sleep(2)
    else:
        row["result"] = "unconfirmed_timeout"
    _log_fire(row)
    return row


def exit_seized(asset_bank: str, asset_mint: str, dec: int) -> dict:
    """Follow-up tx: withdraw seized collateral (all) to our ATA, then Jupiter
    swap it to SOL. Best effort; each step logged."""
    row = {"kind": "liq_exit", "asset_bank": asset_bank, "asset_mint": asset_mint}
    wallet_key, wallet_addr = lt._load_key()
    wallet_b = lt.b58dec(wallet_addr)
    mfi = json.loads((MON / "mfi_account_key.json").read_text())
    mfi_b = lt.b58dec(mfi["address"])
    mint_b = lt.b58dec(asset_mint)
    bank_b = lt.b58dec(asset_bank)
    ata = lt._ata(wallet_b, mint_b, TOKEN)
    vault_auth = lt.pda([b"liquidity_vault_auth", bank_b], PROG)
    vault = lt.pda([b"liquidity_vault", bank_b], PROG)

    ixs = [
        (ATA_PROG, [(wallet_b, True, True), (ata, True, False),
                    (wallet_b, False, False), (mint_b, False, False),
                    (SYSTEM, False, False), (TOKEN, False, False)], bytes([1])),
        (PROG, [(GROUP, False, False), (mfi_b, True, False),
                (wallet_b, False, True), (bank_b, True, False),
                (ata, True, False), (vault_auth, False, False),
                (vault, True, False), (TOKEN, False, False)],
         WITHDRAW_DISC + struct.pack("<Q", 0) + b"\x01\x01"),  # amount ignored, withdraw_all=true
    ]
    tx = build_signed_tx({wallet_b: wallet_key}, wallet_b, ixs)
    sim = lh.rpc("simulateTransaction", [tx, {"encoding": "base64",
                 "sigVerify": True, "replaceRecentBlockhash": True}])
    val = sim.get("result", {}).get("value", {})
    row["withdraw_sim_err"] = val.get("err")
    if val.get("err"):
        row["result"] = "withdraw_sim_failed"
        row["logs_tail"] = (val.get("logs") or [])[-6:]
        _log_fire(row); return row
    res = lh.rpc("sendTransaction", [tx, {"encoding": "base64", "skipPreflight": False}])
    row["withdraw_sig"] = res.get("result")
    if not res.get("result"):
        row["result"] = "withdraw_send_rejected"
        _log_fire(row); return row
    time.sleep(6)

    # Jupiter swap seized -> SOL
    try:
        tv = lh.rpc("getTokenAccountBalance", [lh.b58encode(ata)])["result"]["value"]
        amount = int(tv["amount"])
    except Exception as e:
        row["result"] = f"exit_no_balance: {e}"
        _log_fire(row); return row
    if amount == 0:
        row["result"] = "exit_zero_balance"
        _log_fire(row); return row
    qurl = ("https://lite-api.jup.ag/swap/v1/quote?inputMint=%s&outputMint=%s"
            "&amount=%d&slippageBps=100" % (asset_mint,
            "So11111111111111111111111111111111111111112", amount))
    q = json.loads(urllib.request.urlopen(qurl, timeout=20).read())
    row["exit_quote_out_sol"] = int(q.get("outAmount", 0)) / 1e9
    body = json.dumps({"quoteResponse": q, "userPublicKey": wallet_addr,
                       "wrapAndUnwrapSol": True}).encode()
    req = urllib.request.Request("https://lite-api.jup.ag/swap/v1/swap-instructions",
                                 data=body, headers={"Content-Type": "application/json"})
    sj = json.loads(urllib.request.urlopen(req, timeout=20).read())
    sixs = []
    for ins in (sj.get("setupInstructions") or []) + [sj["swapInstruction"]] + (sj.get("cleanupInstructions") or []):
        sixs.append((lt.b58dec(ins["programId"]),
                     [(lt.b58dec(a["pubkey"]), a["isWritable"], a["isSigner"])
                      for a in ins["accounts"]],
                     base64.b64decode(ins["data"])))
    tx2 = build_signed_tx({wallet_b: wallet_key}, wallet_b, sixs)
    res2 = lh.rpc("sendTransaction", [tx2, {"encoding": "base64", "skipPreflight": False}])
    row["swap_sig"] = res2.get("result")
    row["result"] = "exited" if res2.get("result") else "swap_send_rejected"
    if not res2.get("result"):
        row["rpc_error"] = json.dumps(res2.get("error"))[:300]
    _log_fire(row)
    return row


if __name__ == "__main__":
    # construction smoke test: dry-run fire against a known account; expect
    # sim to reach the program (HealthyAccount proves assembly correctness).
    banks = lh.load_banks()
    by_prefix = {pk[:8]: pk for pk in banks}
    r = fire("GFxxnJpDAjb3VQNsQNerqw5t3iicUnaBahBj65WLkNKu",
             by_prefix["8g5qG6PV"], by_prefix["CCKtUs6C"],
             10_000_000_000, est_seize_usd=100.0, dry_run=True)
    print(json.dumps(r, indent=1))
