#!/usr/bin/env python3
"""
liq_sim.py — assemble an unsigned marginfi liquidate instruction and run it
through simulateTransaction (sigVerify=false). PAPER ONLY: nothing is sent.

Construction validated against real liquidation tx 8V1k2f74 (§350-352):
  [0] group  [1] asset_bank  [2] liab_bank  [3] liquidator mfi acct
  [4] liquidator authority (signer)  [5] liquidatee mfi acct
  [6] liab vault auth PDA  [7] liab liquidity vault PDA
  [8] liab insurance vault PDA  [9] token program
  [10] asset bank oracle  [11] liab bank oracle
  [12+] per-active-balance (bank, oracle) pairs: liquidatee's, then liquidator's

The liquidator stand-in is borrowed from the real tx (5cpDCRKz…) purely to
satisfy deserialization in simulation; sigVerify=false means no signature is
checked. We never broadcast.
"""
import json
import base64
import hashlib
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

from liq_health import rpc, load_banks, i80, b58encode, STRIDE, SLOTS

PROG_S = "MFv2hWf31Z9kbCa1snEPYctwafyhdvnV7FZnsebVacA"
PROG = lt.b58dec(PROG_S)
TOK = lt.b58dec("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
LIQ_DISC = hashlib.sha256(b"global:lending_account_liquidate").digest()[:8]
TRAILER = bytes.fromhex("0a04")  # as seen on the real tx (flags/version bytes)

LIQ_STANDIN = "6oqK5Xy3y9mMjSP5gUUjJ8s1Yy1pQpz8De8dHHdQvdGS"   # real liquidator acct (unsigned stand-in)
LIQ_AUTH = "12NZhrj5FRoqXKM2rSdiN3MF78AbeYckiR9FJ6wQcZcR"      # its authority (unchecked in sim)


def pda(seeds, prog=PROG):
    return lt.pda(list(seeds), prog) if hasattr(lt, "pda") else _pda(seeds, prog)


def _pda(seeds, prog):
    from nacl.bindings import crypto_core_ed25519_is_valid_point
    for bump in range(255, -1, -1):
        h = hashlib.sha256()
        for s in seeds:
            h.update(s)
        h.update(bytes([bump]))
        h.update(prog)
        h.update(b"ProgramDerivedAddress")
        d = h.digest()
        if not crypto_core_ed25519_is_valid_point(d):
            return d
    raise RuntimeError("no bump")


def acct_raw(pk: str) -> bytes:
    v = rpc("getAccountInfo", [pk, {"encoding": "base64"}])["result"]["value"]
    return base64.b64decode(v["data"][0])


def active_slots(raw: bytes):
    out = []
    for i in range(SLOTS):
        o = 72 + i * STRIDE
        if raw[o] == 1:
            out.append(b58encode(raw[o + 1:o + 33]))
    return out


def build_liq_ix(liquidatee_pk: str, asset_bank: str, liab_bank: str, asset_amount: int):
    banks = load_banks()
    ab_raw = acct_raw(asset_bank)
    group = ab_raw[41:73]  # §353: mint@8, decimals@40, group@41-72
    liq_raw = acct_raw(LIQ_STANDIN)
    tee_raw = acct_raw(liquidatee_pk)
    asset_oracle = b58encode(ab_raw[610:642])
    liab_raw = acct_raw(liab_bank)
    liab_oracle = b58encode(liab_raw[610:642])

    auth_pda = lt.pda([b"liquidity_vault_auth", lt.b58dec(liab_bank)], PROG)
    liq_vault = lt.pda([b"liquidity_vault", lt.b58dec(liab_bank)], PROG)
    ins_vault = lt.pda([b"insurance_vault", lt.b58dec(liab_bank)], PROG)

    A = []  # (key_bytes, writable, signer)
    A.append((group, False, False))                      # 0 group
    A.append((lt.b58dec(asset_bank), True, False))       # 1 asset bank
    A.append((lt.b58dec(liab_bank), True, False))        # 2 liab bank
    A.append((lt.b58dec(LIQ_STANDIN), True, False))      # 3 liquidator acct
    A.append((lt.b58dec(LIQ_AUTH), False, True))         # 4 authority (signer)
    A.append((lt.b58dec(liquidatee_pk), True, False))    # 5 liquidatee
    A.append((auth_pda, False, False))                   # 6 vault auth
    A.append((liq_vault, True, False))                   # 7 liquidity vault
    A.append((ins_vault, True, False))                   # 8 insurance vault
    A.append((TOK, False, False))                        # 9 token program
    A.append((lt.b58dec(asset_oracle), False, False))    # 10 asset oracle
    A.append((lt.b58dec(liab_oracle), False, False))     # 11 liab oracle
    # health remaining: liquidatee banks+oracles, then liquidator's
    # §354: remaining schema from marginfi-v2 source (liquidate.rs):
    # [asset_oracle, liab_oracle, liquidator_obs pairs..., liquidatee_obs pairs...]
    # args trailer = u8 len(liquidatee remaining) + u8 len(liquidator remaining).
    liq_pairs, tee_pairs = [], []
    for bpk in active_slots(liq_raw):
        braw = acct_raw(bpk)
        liq_pairs += [(lt.b58dec(bpk), False, False), (braw[610:642], False, False)]
    for bpk in active_slots(tee_raw):
        braw = acct_raw(bpk)
        tee_pairs += [(lt.b58dec(bpk), False, False), (braw[610:642], False, False)]
    A.extend(liq_pairs)
    A.extend(tee_pairs)
    data = LIQ_DISC + struct.pack("<Q", asset_amount) + struct.pack("<BB", len(tee_pairs), len(liq_pairs))
    return [(PROG, A, data)]


def simulate(liquidatee_pk: str, asset_bank: str, liab_bank: str, asset_amount: int):
    ixs = build_liq_ix(liquidatee_pk, asset_bank, liab_bank, asset_amount)
    payer = lt.b58dec(lt._load_key()[1])
    tx_b64 = lt.build_legacy_tx(payer, ixs)
    res = rpc("simulateTransaction", [tx_b64, {
        "encoding": "base64", "sigVerify": False,
        "replaceRecentBlockhash": True,
    }])
    return res


if __name__ == "__main__":
    # target: 57WvwCCthAhm whale — JLP collateral, USDC debt
    last = json.loads((MON / "liq_health_log.jsonl").read_text().strip().splitlines()[-1])
    tgt = [m for m in last["liquidatable_now"] if m["pk"].startswith("57WvwCCthAhm")]
    if not tgt:
        tgt = [m for m in last["top20"] if m["liabs"] > 50000]
    tee = tgt[0]["pk"]
    tee_raw = acct_raw(tee)
    banks = load_banks()
    slots = active_slots(tee_raw)
    # classify: collateral slot (biggest assets) vs debt slot (biggest liabs)
    info = []
    for bpk in slots:
        b = banks[bpk]
        info.append((bpk, b["mint"]))
    print("liquidatee:", tee)
    for bpk, mint in info:
        print(f"  slot bank={bpk[:12]} mint={mint[:12]}")
    # USDC bank = liab, JLP bank = asset
    USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    JLP = "27G8MtK7VtTcCHkpASjSDdkWWYfoqT6ggEuKidVJidD4"
    liab_bank = [b for b, m in info if m == USDC][0]
    asset_bank = [b for b, m in info if m == JLP][0]
    # seize a modest $10k slice of JLP @ ~4.48 → 2232 JLP (6 dec)
    amt = int(2232 * 1e6)
    print(f"simulating liquidate: seize ~{amt/1e6:,.0f} JLP from {tee[:12]}")
    r = simulate(tee, asset_bank, liab_bank, amt)
    val = (r.get("result") or {}).get("value") or {}
    print("err:", val.get("err"))
    print("unitsConsumed:", val.get("unitsConsumed"))
    for line in (val.get("logs") or [])[:40]:
        print("  ", line)
