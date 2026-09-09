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
import base64
import hashlib
import json
import struct
import sys
import urllib.request
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


def _ata_verified(ata_b: bytes, owner_b: bytes, mint_b: bytes) -> bool:
    """§399: True only if the ATA exists on-chain AND is a token-program
    account with exactly this mint+owner. Fail-closed: any doubt -> False,
    caller keeps the create_idempotent ix."""
    try:
        v = lh.rpc("getAccountInfo", [lt.b58enc(ata_b),
                                      {"encoding": "base64"}])["result"]["value"]
        if not v:
            return False
        raw = base64.b64decode(v["data"][0])
        return (v["owner"] == lt.b58enc(TOK) and len(raw) >= 64
                and raw[0:32] == mint_b and raw[32:64] == owner_b)
    except Exception:
        return False


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


# ---------------------------------------------------------------- §370
# Full recipe assembly: v0 message + address lookup tables + Jupiter swap leg.

CB_PROG = lt.b58dec("ComputeBudget111111111111111111111111111111")
ALT_META_SIZE = 56  # ProgramState tag + LookupTableMeta (web3.js convention)
JUP_SI = "https://lite-api.jup.ag/swap/v1/swap-instructions"


def cu_limit_ix(units: int):
    return (CB_PROG, [], bytes([2]) + struct.pack("<I", units))


def cu_price_ix(micro_lamports: int):
    return (CB_PROG, [], bytes([3]) + struct.pack("<Q", micro_lamports))


def fetch_alt(alt_pk: str):
    """Addresses of an on-chain Address Lookup Table."""
    raw = acct_raw(alt_pk)
    body = raw[ALT_META_SIZE:]
    if not body or len(body) % 32:
        raise RuntimeError(f"ALT {alt_pk} malformed ({len(raw)}B)")
    return [body[i:i + 32] for i in range(0, len(body), 32)]


def jup_quote(input_mint: str, output_mint: str, amount_raw: int, slippage_bps=300):
    q = (f"inputMint={input_mint}&outputMint={output_mint}"
         f"&amount={int(amount_raw)}&slippageBps={slippage_bps}")
    with urllib.request.urlopen(f"{lt.JUP_Q}?{q}", timeout=20) as r:
        return json.loads(r.read())


def jup_swap_ixs(quote, user_pk: str, max_accounts=24):
    """POST /swap/v1/swap-instructions: returns raw instruction objects we can
    splice into our own v0 message, plus the ALTs Jupiter's route needs.
    §377: maxAccounts caps the route's total account footprint — the flash
    recipe shares a 1232-byte packet with the liquidation legs, and an
    uncapped route (SWB 1MB feed account, vote accounts, route ATAs) blew it
    to 1684B on the Kamino-asset candidate. If Jupiter can't fit the route in
    max_accounts it errors -> caller falls back to legacy fire()."""
    req = urllib.request.Request(
        JUP_SI, data=json.dumps({
            "quoteResponse": quote, "userPublicKey": user_pk,
            "wrapAndUnwrapSol": True,
            "maxAccounts": max_accounts}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        j = json.loads(r.read())

    def conv(o):
        return (lt.b58dec(o["programId"]),
                [(lt.b58dec(a["pubkey"]), a["isWritable"], a["isSigner"])
                 for a in o["accounts"]],
                base64.b64decode(o["data"]))
    ixs = [conv(o) for o in (j.get("setupInstructions") or [])]
    ixs.append(conv(j["swapInstruction"]))
    if j.get("cleanupInstruction"):
        ixs.append(conv(j["cleanupInstruction"]))
    # fail-closed: only OUR wallet may be a signer inside the splice
    for prog, accs, _ in ixs:
        for k, w, s in accs:
            if s and k != lt.b58dec(user_pk):
                raise RuntimeError(f"jupiter ix wants foreign signer {lt.b58enc(k)}")
    return ixs, (j.get("addressLookupTableAddresses") or [])


def build_v0_tx(payer_b: bytes, instructions, alt_pk_strs=(), commitment="finalized"):
    """Compile + sign a v0 message with address lookup tables.
    instructions: [(program_id_bytes, [(key, writable, signer)], data)]."""
    tables = {lt.b58dec(a): fetch_alt(a) for a in alt_pk_strs}
    meta = {payer_b: [True, True]}
    order = [payer_b]
    for prog, accs, _ in instructions:
        for k, w, s in accs:
            if k not in meta:
                meta[k] = [w, s]
                order.append(k)
            else:
                meta[k][0] |= w
                meta[k][1] |= s
        if prog not in meta:
            meta[prog] = [False, False]
            order.append(prog)
    loc = {}
    for tpk, addrs in tables.items():
        for i, a in enumerate(addrs):
            loc.setdefault(a, (tpk, i))
    sig_w = [payer_b] + [k for k in order
                         if k != payer_b and meta[k][1] and meta[k][0]]
    sig_r = [k for k in order if meta[k][1] and not meta[k][0]]
    # program ids must stay static: the runtime rejects a compiled ix whose
    # program_id_index resolves through a lookup table (sanitize failure)
    progs = {prog for prog, _, _ in instructions}
    nonsig = [k for k in order if not meta[k][1]]
    sw = [k for k in nonsig if meta[k][0] and (k not in loc or k in progs)]
    sr = [k for k in nonsig if not meta[k][0] and (k not in loc or k in progs)]
    static = sig_w + sig_r + sw + sr
    in_static = set(static)
    idx = {k: i for i, k in enumerate(static)}
    w_entries = [(tpk, i) for tpk, addrs in tables.items()
                 for i, a in enumerate(addrs)
                 if a in meta and a not in in_static and a not in progs
                 and meta[a][0] and loc[a] == (tpk, i)]
    r_entries = [(tpk, i) for tpk, addrs in tables.items()
                 for i, a in enumerate(addrs)
                 if a in meta and a not in in_static and a not in progs
                 and not meta[a][0] and loc[a] == (tpk, i)]
    base = len(static)
    for j, (t, i) in enumerate(w_entries):
        idx[tables[t][i]] = base + j
    for j, (t, i) in enumerate(r_entries):
        idx[tables[t][i]] = base + len(w_entries) + j

    bh = lh.rpc("getLatestBlockhash", [{"commitment": commitment}])
    blockhash = lt.b58dec(bh["result"]["value"]["blockhash"])
    msg = bytearray([0x80, len(sig_w) + len(sig_r), len(sig_r), len(sr)])
    msg += lt._shortvec(len(static)) + b"".join(static)
    msg += blockhash
    msg += lt._shortvec(len(instructions))
    for prog, accs, data in instructions:
        msg += bytes([idx[prog]])
        msg += lt._shortvec(len(accs))
        for k, _, _ in accs:
            msg += bytes([idx[k]])
        msg += lt._shortvec(len(data)) + data
    used_tables = [t for t in tables
                   if any(e[0] == t for e in w_entries + r_entries)]
    msg += lt._shortvec(len(used_tables))
    for tpk in used_tables:
        wi = [i for t, i in w_entries if t == tpk]
        ri = [i for t, i in r_entries if t == tpk]
        msg += tpk + lt._shortvec(len(wi)) + bytes(wi)
        msg += lt._shortvec(len(ri)) + bytes(ri)
    key, _ = lt._load_key()
    sig = key.sign(bytes(msg))
    tx = lt._shortvec(1) + sig + bytes(msg)
    return base64.b64encode(bytes(tx)).decode()


def recipe_obs(asset_bank: str, liab_bank: str):
    """Observation remaining accounts for the withdraw/end legs: every balance
    active on OUR account post-liquidate (current slots + the two banks the
    liquidation adds)."""
    from liq_sim import bank_remaining, active_slots
    liq_raw = acct_raw(LIQ_STANDIN)
    obs, seen = [], set()
    for bpk in active_slots(liq_raw) + [asset_bank, liab_bank]:
        if bpk in seen:
            continue
        seen.add(bpk)
        obs += bank_remaining(bpk)
    return obs


def build_withdraw_ix(bank_pk: str, obs):
    """withdraw_all of the seized collateral position to our ATA."""
    bank_raw = acct_raw(bank_pk)
    group = bank_raw[41:73]
    mint = bank_raw[8:40]
    bank_b = lt.b58dec(bank_pk)
    mfi_b = lt.b58dec(LIQ_STANDIN)
    auth_b = lt.b58dec(LIQ_AUTH)
    vault_auth = pda([b"liquidity_vault_auth", bank_b], PROG)
    liq_vault = pda([b"liquidity_vault", bank_b], PROG)
    dest = ata(auth_b, mint)
    return (PROG, [(group, False, False), (mfi_b, True, False),
                   (auth_b, False, True), (bank_b, True, False),
                   (dest, True, False), (vault_auth, False, False),
                   (liq_vault, True, False), (TOK, False, False)] + obs,
            WITHDRAW_DISC + struct.pack("<Q", 0) + bytes([1, 1]))


def our_alts():
    """Our own marginfi key-universe tables (liq_alt.py), freshest first."""
    f = MON / "liq_alts.json"
    if f.exists():
        return json.loads(f.read_text()).get("tables", [])
    return []


def build_recipe(tee_pk: str, asset_bank: str, liab_bank: str, asset_amount: int,
                 swap_in_raw: int, payer_b: bytes, slippage_bps=300,
                 cu_limit=1_200_000):
    """§337 full flash-liquidation recipe:
      compute budget -> create ATAs -> start_flashloan -> [oracle refreshes]
      -> liquidate -> withdraw_all(seized) -> Jupiter swap asset->liab
      -> repay_all(liab) -> end_flashloan.
    Returns (instructions, alt_pk_strs)."""
    from liq_sim import build_liq_ix
    ab_raw = acct_raw(asset_bank)
    lb_raw = acct_raw(liab_bank)
    asset_mint = lt.b58enc(ab_raw[8:40])
    liab_mint = lt.b58enc(lb_raw[8:40])
    auth_b = lt.b58dec(LIQ_AUTH)
    mfi_b = lt.b58dec(LIQ_STANDIN)
    group = lb_raw[41:73]
    asset_ata = ata(auth_b, ab_raw[8:40])
    liab_ata = ata(auth_b, lb_raw[8:40])

    obs = recipe_obs(asset_bank, liab_bank)
    pre = [cu_price_ix(50_000), cu_limit_ix(cu_limit)]
    # §399: skip ATA-creation ixs when the ATA already exists on-chain —
    # each create ix costs ~6 account locks and pushed the recipe past the
    # 64-lock limit (TooManyAccountLocks) on multi-bank liquidatees.
    if not _ata_verified(asset_ata, auth_b, ab_raw[8:40]):
        pre.append(create_ata_idempotent(payer_b, asset_ata, auth_b, ab_raw[8:40]))
    if not _ata_verified(liab_ata, auth_b, lb_raw[8:40]):
        pre.append(create_ata_idempotent(payer_b, liab_ata, auth_b, lb_raw[8:40]))
    liq_ixs = build_liq_ix(tee_pk, asset_bank, liab_bank, asset_amount,
                           payer_b=payer_b)
    wd = build_withdraw_ix(asset_bank, obs)
    quote = jup_quote(asset_mint, liab_mint, swap_in_raw, slippage_bps)
    swap_ixs, jup_alts = jup_swap_ixs(quote, LIQ_AUTH)
    alts = our_alts() + jup_alts

    lb_b = lt.b58dec(liab_bank)
    liq_vault = pda([b"liquidity_vault", lb_b], PROG)
    repay = (PROG, [(group, False, False), (mfi_b, True, False),
                    (auth_b, False, True), (lb_b, True, False),
                    (liab_ata, True, False), (liq_vault, True, False),
                    (TOK, False, False)],
             REPAY_DISC + struct.pack("<Q", 0) + bytes([1, 1]))
    end = (PROG, [(mfi_b, True, False), (group, False, False),
                  (auth_b, False, True)] + obs, END_DISC)

    mid = liq_ixs + [wd] + swap_ixs + [repay]
    end_index = len(pre) + 1 + len(mid)  # index of `end` in the final list
    start = (PROG, [(mfi_b, True, False), (auth_b, False, True),
                    (IXS_SYSVAR, False, False)],
             START_DISC + struct.pack("<Q", end_index))
    return pre + [start] + mid + [end], alts


if __name__ == "__main__":
    # Structural validation of the full §337 recipe against the last fire
    # candidate (GFxx — healthy at current prices). Expected outcome: the tx
    # compiles, ALTs resolve, pre-liquidate legs execute, and the sim aborts
    # INSIDE liquidate with HealthyAccount 6068 — proving every leg up to the
    # point only a real underwater account can unlock.
    payer_s = lt._load_key()[1]
    payer = lt.b58dec(payer_s)
    # Structural validation against OUR OWN healthy marginfi account (non-staked
    # SOL deposit — avoids the 6047 staked-asset tag rule that blocks seizing
    # staked collateral into an account holding a plain SOL deposit).
    TEE = "A91fDng3SdKxBMPq4DxUSE4LKqBR1g6tf3rC8ypvogRy"
    ASSET = "CCKtUs6Cgwo4aaQUmBPmyoApH2gUDErxNZCAntD6LYGh"   # SOL bank
    LIAB = "2s37akK2eyBbp8DZgCm7RtsaEz8eJP3Nxd4urLHQv7yB"    # main USDC bank
    AMT = 50_000_000  # 0.05 SOL seize sizing (aborts at 6068 regardless)
    ixs, alts = build_recipe(TEE, ASSET, LIAB, AMT, AMT, payer)
    print(f"recipe: {len(ixs)} ixs, alts={alts}")
    tx = build_v0_tx(payer, ixs, alts)
    print(f"tx size: {len(base64.b64decode(tx))} bytes")
    res = lh.rpc("simulateTransaction", [tx, {"encoding": "base64",
                 "sigVerify": False, "replaceRecentBlockhash": True,
                 "commitment": "processed"}])
    if "error" in res:
        print("RPC-ERR:", res["error"].get("message"))
        raise SystemExit(1)
    val = (res.get("result") or {}).get("value") or {}
    print("err:", val.get("err"))
    print("units:", val.get("unitsConsumed"))
    for line in (val.get("logs") or [])[-30:]:
        print("  ", line)
