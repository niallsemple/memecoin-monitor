#!/usr/bin/env python3
"""liq_flash.py — marginfi flash-loan recipe (§337/§369).

Mechanics (verified in refs/account.rs:1420): while ACCOUNT_IN_FLASHLOAN is
set, ALL risk checks are skipped. So the size recipe is:

  start_flashloan(end_index)            # arms the flag, introspection sysvar
  [withdraw liab-token X]               # no health check during flash
  [liquidate: absorb debt + discounted collateral]
  [withdraw seized collateral]
  [Jupiter swap collateral -> liab token]
  [repay liab debt]
  end_flashloan                         # health re-checked HERE only

Own capital is only needed for gas; size is limited by vault liquidity and
exit-liquidity depth, not our balance. This module first validates the flash
machinery standalone (withdraw+repay roundtrip, no liquidation) since the
liquidate leg is already proven (§366-367) and Jupiter swaps are live-proven.
"""
import hashlib
import struct
import sys
from pathlib import Path

MON = Path(__file__).resolve().parent
sys.path.insert(0, str(MON))

import importlib.util
_spec = importlib.util.spec_from_file_location("live_trader", str(MON / "live_trader.py"))
lt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lt)

import liq_health as lh
from liq_sim import PROG, PROG_S, acct_raw, pda, LIQ_STANDIN, LIQ_AUTH

START_DISC = bytes([14, 131, 33, 220, 81, 186, 180, 107])      # start_flashloan
END_DISC = bytes([105, 124, 201, 106, 153, 2, 8, 156])        # end_flashloan
WITHDRAW_DISC = bytes([36, 72, 74, 19, 210, 210, 192, 192])   # withdraw
BORROW_DISC = bytes([4, 126, 116, 53, 48, 5, 212, 31])        # borrow (§369:
#   withdraw is WithdrawOnly in current marginfi — borrowing is its own ix)
REPAY_DISC = bytes([79, 209, 172, 177, 222, 51, 173, 151])    # repay

TOK = lt.b58dec("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ATA_PROG = lt.b58dec("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
SYS_PROG = lt.b58dec("11111111111111111111111111111111")
IXS_SYSVAR = lt.b58dec("Sysvar1nstructions1111111111111111111111111")
WSOL = lt.b58dec("So11111111111111111111111111111111111111112")


def ata(owner_b: bytes, mint_b: bytes) -> bytes:
    return pda([owner_b, TOK, mint_b], ATA_PROG)


def create_ata_idempotent(payer_b: bytes, ata_b: bytes, owner_b: bytes, mint_b: bytes):
    # CreateIdempotent: discriminator 1
    return (ATA_PROG, [
        (payer_b, True, True), (ata_b, True, False), (owner_b, False, False),
        (mint_b, False, False), (SYS_PROG, False, False), (TOK, False, False),
    ], bytes([1]))


def build_flash_roundtrip(bank_pk: str, amount: int, payer_b: bytes):
    """start -> borrow(amount) -> repay_all -> end. Standalone flash
    machinery validation; no liquidation leg."""
    from liq_sim import bank_remaining, active_slots
    bank_raw = acct_raw(bank_pk)
    group = bank_raw[41:73]
    mint = bank_raw[8:40]
    mfi_b = lt.b58dec(LIQ_STANDIN)
    auth_b = lt.b58dec(LIQ_AUTH)
    bank_b = lt.b58dec(bank_pk)
    vault_auth = lt.pda([b"liquidity_vault_auth", bank_b], PROG)
    liq_vault = lt.pda([b"liquidity_vault", bank_b], PROG)
    user_ata = ata(auth_b, mint)

    # observation remaining: our account's active balances PLUS the borrow
    # bank's pair — the CB price gate runs post-borrow (borrow.rs:224), when
    # the new balance is already active; missing pair -> InvalidBankAccount 6008
    liq_raw = acct_raw(LIQ_STANDIN)
    obs = []
    seen = set()
    for bpk in active_slots(liq_raw) + [bank_pk]:
        if bpk in seen:
            continue
        seen.add(bpk)
        obs += bank_remaining(bpk)

    ixs = []
    ixs.append(create_ata_idempotent(payer_b, user_ata, auth_b, mint))
    # ix order: [0]=create_ata, [1]=start, [2]=borrow, [3]=repay, [4]=end
    END_INDEX = 4
    ixs.append((PROG, [(mfi_b, True, False), (auth_b, False, True),
                       (IXS_SYSVAR, False, False)],
                START_DISC + struct.pack("<Q", END_INDEX)))
    ixs.append((PROG, [(group, False, False), (mfi_b, True, False),
                       (auth_b, False, True), (bank_b, True, False),
                       (user_ata, True, False), (vault_auth, False, False),
                       (liq_vault, True, False), (TOK, False, False)] + obs,
                BORROW_DISC + struct.pack("<Q", amount)))
    ixs.append((PROG, [(group, False, False), (mfi_b, True, False),
                       (auth_b, False, True), (bank_b, True, False),
                       (user_ata, True, False), (liq_vault, True, False),
                       (TOK, False, False)],
                # repay_all=Some(true): share-value rounding makes exact-amount
                # repay overshoot into an asset -> OperationRepayOnly 6022
                REPAY_DISC + struct.pack("<Q", amount) + bytes([1, 1])))
    ixs.append((PROG, [(mfi_b, True, False), (group, False, False),
                       (auth_b, False, True)] + obs, END_DISC))
    return ixs


if __name__ == "__main__":
    banks = lh.load_banks()
    sol_bank = next(k for k in banks if k.startswith("CCKtUs6C"))
    payer = lt.b58dec(lt._load_key()[1])
    amount = 200_000_000  # 0.2 SOL pure flash borrow (no deposit touched)
    ixs = build_flash_roundtrip(sol_bank, amount, payer)
    tx = lt.build_legacy_tx(payer, ixs)
    res = lh.rpc("simulateTransaction", [tx, {"encoding": "base64",
                 "sigVerify": False, "replaceRecentBlockhash": True}])
    val = (res.get("result") or {}).get("value") or {}
    print("err:", val.get("err"))
    print("units:", val.get("unitsConsumed"))
    for line in (val.get("logs") or [])[-25:]:
        print("  ", line)
