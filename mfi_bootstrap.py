#!/usr/bin/env python3
"""mfi_bootstrap.py — fund our marginfi account with a SOL deposit.

Why: the liquidate ix repays from the liquidator's deposit in the liab bank
first, then borrows the rest against init-weight health. A standing SOL
deposit = instant repay source + borrow collateral for SOL-debt candidates
(the most common class). Seize+repay stay atomic inside the liquidate ix;
the exit swap is a separate follow-up tx.

Tx: create wSOL ATA (idempotent) + transfer 0.3 SOL + syncNative + deposit.
Deposit ix (IDL verified): lending_account_deposit
  [group, marginfi_account(w), authority(s), bank(w), signer_token_account(w),
   liquidity_vault(w), token_program]  args: amount u64 + Option<bool> None
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

from liq_health import rpc, b58encode
from mfi_init import build_signed_tx

PROG = lt.b58dec("MFv2hWf31Z9kbCa1snEPYctwafyhdvnV7FZnsebVacA")
SYSTEM = bytes(32)
TOKEN = lt.b58dec("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ATA_PROG = lt.b58dec("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
WSOL = lt.b58dec("So11111111111111111111111111111111111111112")
RENT = lt.b58dec("SysvarRent111111111111111111111111111111111")
GROUP = lt.b58dec("4qp6Fx6tnZkY5Wropq9wUYgtFxXKwE6viZxFHg3rdAG8")
SOL_BANK_S = None  # resolved at runtime (CCKtUs6C…)

DEPOSIT_AMT = int(0.30 * 1e9)
DEPOSIT_DISC = hashlib.sha256(b"global:lending_account_deposit").digest()[:8]
# spl-token: 9=closeAccount? we use 17=syncNative, 1=initializeAccount(ata prog)
SYNC_NATIVE = bytes([17])


def main():
    wallet_key, wallet_addr = lt._load_key()
    wallet_b = lt.b58dec(wallet_addr)
    mfi = json.loads((MON / "mfi_account_key.json").read_text())
    mfi_b = lt.b58dec(mfi["address"])

    # find the main-group SOL bank
    import liq_health as lh
    banks = lh.load_banks()
    sol_bank = None
    for pk, b in banks.items():
        if b["mint"] == "So11111111111111111111111111111111111111112":
            import base64 as b64
            raw = b64.b64decode(rpc("getAccountInfo", [pk, {"encoding": "base64"}])["result"]["value"]["data"][0])
            if b58encode(raw[41:73]) == b58encode(GROUP) and raw[785] == 1:  # tag SOL
                sol_bank = pk
                break
    assert sol_bank, "no main-group SOL bank"
    print("SOL bank:", sol_bank)
    bank_b = lt.b58dec(sol_bank)
    vault = lt.pda([b"liquidity_vault", bank_b], PROG)

    ata = lt._ata(wallet_b, WSOL, TOKEN)

    ixs = []
    # 1) create wSOL ATA (idempotent variant: CreateIdempotent = 1)
    ixs.append((ATA_PROG, [
        (wallet_b, True, True), (ata, True, False), (wallet_b, False, False),
        (WSOL, False, False), (SYSTEM, False, False), (TOKEN, False, False),
    ], bytes([1])))
    # 2) transfer SOL into the ATA
    ixs.append((SYSTEM, [
        (wallet_b, True, True), (ata, True, False),
    ], struct.pack("<IQ", 2, DEPOSIT_AMT)))  # system transfer = 2
    # 3) syncNative
    ixs.append((TOKEN, [(ata, True, False)], SYNC_NATIVE))
    # 4) marginfi deposit
    ixs.append((PROG, [
        (GROUP, False, False),
        (mfi_b, True, False),
        (wallet_b, False, True),
        (bank_b, True, False),
        (ata, True, False),
        (vault, True, False),
        (TOKEN, False, False),
    ], DEPOSIT_DISC + struct.pack("<Q", DEPOSIT_AMT) + b"\x00"))

    tx = build_signed_tx({wallet_b: wallet_key}, wallet_b, ixs)
    sim = rpc("simulateTransaction", [tx, {"encoding": "base64", "sigVerify": False,
                                         "replaceRecentBlockhash": True}])
    if sim.get("error"):
        print("SIM RPC ERROR (fail-closed):", sim["error"]); return
    val = sim["result"]["value"]
    print("simulate err:", val.get("err"))
    if val.get("err"):
        for l in val.get("logs") or []:
            print("  ", l)
        return

    res = rpc("sendTransaction", [tx, {"encoding": "base64", "skipPreflight": False}])
    sig = res.get("result")
    print("sent:", sig or json.dumps(res)[:300])
    if not sig:
        return
    for _ in range(30):
        st = lt._rpc("getSignatureStatuses", [[sig]])
        row = (st.get("value") or [None])[0]
        if row and row.get("confirmationStatus") in ("confirmed", "finalized"):
            print("confirmed err:", row.get("err"))
            break
        time.sleep(2)
    # verify deposit: our account's balance slots
    v = rpc("getAccountInfo", [mfi["address"], {"encoding": "base64"}])["result"]["value"]
    raw = base64.b64decode(v["data"][0])
    bal = raw[72:72 + 104 * 16]
    for i in range(16):
        o = i * 104
        if bal[o] == 1:
            bpk = b58encode(bal[o + 1:o + 33])
            a_sh = int.from_bytes(bal[o + 40:o + 56], "little", signed=True) / 2 ** 48
            print(f"slot{i}: bank={bpk[:8]} asset_shares={a_sh:.6f}")
    print("wallet balance now:", lt.balance_sol(wallet_addr), "SOL")


if __name__ == "__main__":
    main()
