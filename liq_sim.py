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

LIQ_STANDIN = "A91fDng3SdKxBMPq4DxUSE4LKqBR1g6tf3rC8ypvogRy"   # §358: OUR marginfi account (main group)
LIQ_AUTH = "CQcKkSee9bdHZ1bejYFDUXVtodbfKHe2KSx6AaAnTW2K"      # our wallet = its authority

# Kamino refresh_reserve bundle (§365-366): marginfi requires any Kamino bank
# touched by the health check to have its reserve refreshed in the SAME slot
# (ensure_kamino_reserve_fresh, ReserveStale 6206). Accounts per kamino_lending
# IDL: reserve(w), lending_market, pyth_oracle, swb_price, swb_twap, scope.
# Unused oracle slots take the KLend program id as placeholder (Kamino convention).
KLEND = lt.b58dec("KLend2g3cP87fffoy8q1mQqGKjrxjC8boSyAYavgmjD")
KM_REFRESH_DISC = bytes([2, 218, 138, 235, 79, 201, 25, 102])
KAMINO_SETUPS = {6, 7}  # KaminoPythPush / KaminoSwitchboardPull

# §373: SPL single-validator-pool program (refs/constants.rs SPL_SINGLE_POOL_ID) —
# staked-bank onramp PDAs derive under it as ["onramp", vote_account].
SPL_SINGLE_POOL = lt.b58dec("SVSPxpvHdN29nkVg9rPapPNDddN5DipNLRUFhyjFThE")


def build_refresh_ix(bank_pk: str):
    """Kamino refresh_reserve ix for a marginfi Kamino bank, or None.

    Oracle slots are filled from the RESERVE's own token_info config (§366):
    scope price_feed @5112, swb aggregator @5160 (+twap @5192), pyth @5224
    (on-chain, incl. 8B disc). All-default slot -> KLend placeholder."""
    raw = acct_raw(bank_pk)
    setup = raw[609]
    if setup not in KAMINO_SETUPS:
        return None
    reserve = raw[642:674]        # oracle_keys[1]
    r_raw = acct_raw(b58encode(reserve))
    lending_market = r_raw[32:64]  # MinimalReserve: disc(8) + version(8) + slot(8) + stale(1) + status(1) + pad(6) -> @32
    ZERO = bytes(32)
    scope = r_raw[5112:5144]
    swb = r_raw[5160:5192]
    swb_twap = r_raw[5192:5224]
    pyth = r_raw[5224:5256]
    A = [(reserve, True, False), (lending_market, False, False),
         (pyth if pyth != ZERO else KLEND, False, False),
         (swb if swb != ZERO else KLEND, False, False),
         (swb_twap if swb_twap != ZERO else KLEND, False, False),
         (scope if scope != ZERO else KLEND, False, False)]
    return (KLEND, A, KM_REFRESH_DISC)


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


def bank_remaining(bpk: str):
    """Remaining accounts for one active balance, per
    get_remaining_accounts_per_bank / get_remaining_accounts_per_asset_tag.
    Count from oracle_setup when explicitly mapped, else from asset_tag:
    DEFAULT/SOL=2, KAMINO/DRIFT/SOLEND/JUPLEND=3, STAKED=5 (5th = onramp).
    """
    raw = acct_raw(bpk)
    setup, tag = raw[609], raw[785]
    keys = [raw[610 + 32 * k:642 + 32 * k] for k in range(5)]
    SETUP_COUNT = {8: 1, 13: 2, 14: 2, 17: 2, 19: 3, 20: 4, 21: 4,
                   22: 3, 23: 4, 24: 4, 25: 3, 26: 2}
    TAG_COUNT = {0: 2, 1: 2, 2: 5, 3: 3, 4: 3, 5: 3, 6: 3}
    count = SETUP_COUNT.get(setup) or TAG_COUNT.get(tag)
    if count is None:
        raise RuntimeError(f"unknown remaining count for {bpk} setup={setup} tag={tag}")
    out = [(lt.b58dec(bpk), False, False)]
    if count >= 2:
        out.append((keys[0], False, False))
    if count >= 3:
        out.append((keys[1], False, False))
    if count >= 4:
        out.append((keys[2], False, False))
    if count >= 5:
        onramp = keys[3] if keys[3] != bytes(32) else None
        if onramp is None:
            # §373 (lst_stake_price.rs: expected_staked_onramp): when
            # oracle_keys[3] is default, onramp = PDA["onramp", vote] under the
            # SPL single-pool program, vote = bank.integration_acc_1 @1560.
            vote = raw[1560:1592]
            if vote == bytes(32):
                raise RuntimeError(f"staked onramp: no oracle_keys[3] or integration_acc_1 for {bpk}")
            onramp = pda([b"onramp", vote], SPL_SINGLE_POOL)
        out.append((onramp, False, False))
    return out


def build_liq_ix(liquidatee_pk: str, asset_bank: str, liab_bank: str, asset_amount: int,
                 payer_b: bytes = None):
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
    # §366: head of remaining = asset bank's per-bank accounts (oracle [+
    # reserve for Kamino/Drift/etc]), then liab bank's — NOT two bare oracles.
    # liquidate.rs: asset consumes get_remaining_accounts_per_bank(asset)-1,
    # then liab consumes its own count-1 (lines 260-272).
    for entry in bank_remaining(asset_bank)[1:]:
        A.append(entry)
    for entry in bank_remaining(liab_bank)[1:]:
        A.append(entry)
    # health remaining: liquidatee banks+oracles, then liquidator's
    # §354: remaining schema from marginfi-v2 source (liquidate.rs):
    # [asset_oracle, liab_oracle, liquidator_obs pairs..., liquidatee_obs pairs...]
    # args trailer = u8 len(liquidatee remaining) + u8 len(liquidator remaining).
    liq_accts, tee_accts = [], []
    for bpk in active_slots(liq_raw):
        liq_accts += bank_remaining(bpk)
    for bpk in active_slots(tee_raw):
        tee_accts += bank_remaining(bpk)
    A.extend(liq_accts)
    A.extend(tee_accts)
    data = LIQ_DISC + struct.pack("<Q", asset_amount) + struct.pack("<BB", len(tee_accts), len(liq_accts))
    # §366: prepend refresh_reserve for every Kamino bank either account touches
    # (health check prices all active slots; stale reserve -> ReserveStale 6206)
    refreshes = []
    seen_reserves = set()
    for bpk in set(active_slots(liq_raw)) | set(active_slots(tee_raw)) | {asset_bank, liab_bank}:
        if bpk in seen_reserves:
            continue
        seen_reserves.add(bpk)
        r = build_refresh_ix(bpk)
        if r:
            refreshes.append(r)
    swb_feeds = []  # §367: SwbPull banks among touched slots need crossbar refresh
    for bpk in set(active_slots(liq_raw)) | set(active_slots(tee_raw)) | {asset_bank, liab_bank}:
        braw = acct_raw(bpk)
        if braw[609] == 4:  # SwitchboardPull
            swb_feeds.append(b58encode(braw[610:642]))
    if swb_feeds and payer_b is not None:
        import swb_refresh
        # fail-closed: dead feeds raise here -> no tx built at all
        refreshes = swb_refresh.fetch_update_ixs(sorted(set(swb_feeds)), payer_b) + refreshes
    return refreshes + [(PROG, A, data)]


def simulate(liquidatee_pk: str, asset_bank: str, liab_bank: str, asset_amount: int):
    payer = lt.b58dec(lt._load_key()[1])
    ixs = build_liq_ix(liquidatee_pk, asset_bank, liab_bank, asset_amount, payer_b=payer)
    has_swb = any(lt.b58enc(p) == swb_prog_id() for p, _, _ in ixs) if ixs else False
    cfg = {"encoding": "base64", "sigVerify": False, "replaceRecentBlockhash": True}
    if has_swb:
        # crossbar signs at the tip; finalized sims falsely reject (InvalidSlot
        # 6039). Real txs also execute at the tip, so processed is honest here.
        cfg["commitment"] = "processed"
    # §400: compile as v0 with our ALTs — the legacy compile of a real
    # liquidation exceeds the 1232B packet and the RPC returns an RPC-level
    # error, which the old code misread as err=None ("PASS"). Every historical
    # "liquidatable" verdict from this gate was a non-executing tx.
    import liq_flash as lf
    tx_b64 = lf.build_v0_tx(payer, ixs, lf.our_alts())
    res = rpc("simulateTransaction", [tx_b64, cfg])
    if res.get("error"):
        return {"result": {"value": {"err": {"rpc": str(res["error"])[:200]}}}}
    val = (res.get("result") or {}).get("value") or {}
    if val.get("err") is None and not val.get("unitsConsumed"):
        # defensive: err=None with zero units means the tx never executed
        return {"result": {"value": {"err": {"no_exec": True}}}}
    return res


def swb_prog_id():
    return "SBondMDrcV3K4kxZR1HNVT7osZxAHVHgYXL5Ze1oMUv"


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
