#!/usr/bin/env python3
"""kamino_hunt.py — Kamino liquidation fire path (PAPER/simulate only until
a real alert fires and the owner approves live firing).

Pipeline: decode obligation (offsets verified vs production IDL §460) →
pick biggest borrow (repay) + biggest deposit (withdraw) → fetch reserve
accounts → build liquidateObligationAndRedeemReserveCollateral (V1 flat,
disc [177,71,154,188,226,133,74,55]) → simulateTransaction(sigVerify=false).

Expected sim result on a HEALTHY obligation: program error ObligationHealthy
or similar — that still proves serialization + account resolution. On a real
liquidatable alert, sim success = fire-ready.

§461 live-sim findings (validated on a real healthy obligation):
  - Liquidate ix serialization + 20-account resolution ACCEPTED by KLend
    ("Instruction: LiquidateObligationAndRedeemReserveCollateral" logged).
  - Fire bundle shape REQUIRED: refreshReserve (disc [2,218,138,235,79,201,25,102],
    accounts reserve/lendingMarket/pythOracle/swbPrice/swbTwap/scopePrices) +
    refreshObligation (disc [33,132,147,228,151,192,72,89]) in the SAME tx —
    check_refresh introspects the instructions sysvar and PANICS on any ix with
    <8B data, so ATA creation (1B data) must go in a separate setup tx.
  - ATAs for repay/collateral/withdraw mints should be PRE-STAGED for top
    reserves (one-time setup tx per mint) so the fire tx stays atomic.
"""
import json, base64, hashlib, struct, sys, time
from pathlib import Path
import urllib.request

MON = Path(__file__).resolve().parent
sys.path.insert(0, str(MON))
from liq_health import rpc, b58encode  # noqa: E402  (helius key lives there)

KLEND = "KLend2g3cP87fffoy8q1mQqGKjrxjC8boSyAYavgmjDhe".replace("he", "")  # §458 guard
KLEND = "KLend2g3cP87fffoy8q1mQqGKjrxjC8boSyAYavgmjD"
ALPH = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
SF60 = float(2 ** 60)

def b58decode(s: str) -> bytes:
    n = 0
    for c in s:
        n = n * 58 + ALPH.index(c)
    b = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\0" * (len(s) - len(s.lstrip("1"))) + b

# --- obligation layout (§459/§460, production-verified) ---
DEP_BASE, DEP_STRIDE = 96, 136     # deposits[8]
BRW_BASE, BRW_STRIDE = 1208, 200   # borrows[5]
OFF_ADJ, OFF_UNH = 2208, 2256
# deposit: reserve+0, amount+32, mv_sf+40 ; borrow: reserve+0, amt_sf+88, mv_sf+104

# --- reserve layout (computed from refs/klend_idl_full.json §460) ---
RES_MKT, RES_LIQ_MINT, RES_LIQ_SUPPLY, RES_LIQ_FEEVAULT = 32, 128, 160, 192
RES_DECIMALS, RES_COL_MINT, RES_COL_SUPPLY = 272, 2560, 2600

LIQ_DISC = bytes([177, 71, 154, 188, 226, 133, 74, 55])
TOKEN_PROG = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
ATA_PROG = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
IX_SYSVAR = "Sysvar1nstructions1111111111111111111111111"
SYS_PROG = "11111111111111111111111111111111"

# --- farms (§472: withdraw-side collateral farm required by check_refresh) ---
FARMS_PROG = "FarmsPZpWu9i7Kky8tPN37rs2TpmMrAZrC7S7vJa91Hr"  # verified owner of farm acct
RES_FARM_COL, RES_FARM_DEBT = 64, 96   # reserve fields (col farm found @64 on-chain)
RENT_SYSVAR = "SysvarRent111111111111111111111111111111111"
import hashlib as _hl
FARMS_REFRESH_DISC = _hl.sha256(
    b"global:refresh_obligation_farms_for_reserve").digest()[:8]

def _farm_of(res_raw: bytes, off: int):
    pk = res_raw[off:off+32]
    return b58encode(pk) if any(pk) else None

def farm_user_state(farm_pk: str, ob_pk: str) -> str:
    """Verified on-chain: [b'user', farm, obligation] under FARMS_PROG."""
    return _pda([b"user", b58decode(farm_pk), b58decode(ob_pk)], FARMS_PROG)

def farm_refresh_ix(res_pk: str, farm_pk: str, ob_pk: str, mkt: str,
                    mkt_auth: str, crank: str, mode: int):
    """refreshObligationFarmsForReserve: [crank(sig), obligation, lma, reserve,
    reserveFarmState(mut), obligationFarmUserState(mut), lendingMarket,
    farmsProgram, rent, systemProgram] + mode u8 (0=collateral, 1=debt)."""
    accs = [(b58decode(crank), False, True),
            (b58decode(ob_pk), False, False),
            (b58decode(mkt_auth), False, False),
            (b58decode(res_pk), False, False),
            (b58decode(farm_pk), True, False),
            (b58decode(farm_user_state(farm_pk, ob_pk)), True, False),
            (b58decode(mkt), False, False),
            (b58decode(FARMS_PROG), False, False),
            (b58decode(RENT_SYSVAR), False, False),
            (b58decode(SYS_PROG), False, False)]
    return (b58decode(KLEND), accs, FARMS_REFRESH_DISC + bytes([mode]))

def _on_curve(h: bytes) -> bool:
    """Pure-python ed25519 point-existence check (managed runtime has no nacl).
    Standard recover-x test: x² = (y²−1)/(d·y²+1) must be a quadratic residue."""
    p = 2 ** 255 - 19
    d = (-121665 * pow(121666, p - 2, p)) % p
    y = int.from_bytes(h, "little") & ((1 << 255) - 1)
    if y >= p:
        return False
    y2 = y * y % p
    den = (d * y2 + 1) % p
    x2 = (y2 - 1) * pow(den, p - 2, p) % p
    # quadratic residue test via Euler criterion
    return pow(x2, (p - 1) // 2, p) == 1 or x2 == 0

def _pda(seeds, prog: str) -> str:
    p = b58decode(prog)
    for bump in range(255, -1, -1):
        data = b"".join(seeds) + bytes([bump]) + p + b"ProgramDerivedAddress"
        h = hashlib.sha256(data).digest()
        if not _on_curve(h):
            return b58encode(h)
    raise ValueError("no PDA bump")

def ata(owner: str, mint: str, token_prog: str = TOKEN_PROG) -> str:
    return _pda([b58decode(owner), b58decode(token_prog), b58decode(mint)], ATA_PROG)

def acct_raw(pk: str) -> bytes:
    v = rpc("getAccountInfo", [pk, {"encoding": "base64"}])["result"]["value"]
    return base64.b64decode(v["data"][0]) if v else b""

def mint_owner(mint: str) -> str:
    v = rpc("getAccountInfo", [mint, {"encoding": "base64"}])["result"]["value"]
    return v["owner"] if v else TOKEN_PROG

def u128le(raw, off):
    return int.from_bytes(raw[off:off+16], "little")

def decode_obligation(raw: bytes) -> dict:
    deps, brws = [], []
    for i in range(8):
        o = DEP_BASE + i * DEP_STRIDE
        amt = int.from_bytes(raw[o+32:o+40], "little")
        mv = u128le(raw, o+40) / SF60
        if amt:
            deps.append({"reserve": b58encode(raw[o:o+32]), "amount": amt, "mv": mv})
    for i in range(5):
        o = BRW_BASE + i * BRW_STRIDE
        amt = u128le(raw, o+88) / SF60
        mv = u128le(raw, o+104) / SF60
        if amt:
            brws.append({"reserve": b58encode(raw[o:o+32]), "amt_sf": amt, "mv": mv})
    return {"deposits": sorted(deps, key=lambda d: -d["mv"]),
            "borrows": sorted(brws, key=lambda b: -b["mv"]),
            "adj_debt": u128le(raw, OFF_ADJ) / SF60,
            "unhealthy": u128le(raw, OFF_UNH) / SF60,
            "owner": b58encode(raw[64:96]),
            "lending_market": b58encode(raw[32:64])}

def reserve_info(pk: str) -> dict:
    raw = acct_raw(pk)
    return {"reserve": pk,
            "lending_market": b58encode(raw[RES_MKT:RES_MKT+32]),
            "liq_mint": b58encode(raw[RES_LIQ_MINT:RES_LIQ_MINT+32]),
            "liq_supply": b58encode(raw[RES_LIQ_SUPPLY:RES_LIQ_SUPPLY+32]),
            "liq_feevault": b58encode(raw[RES_LIQ_FEEVAULT:RES_LIQ_FEEVAULT+32]),
            "decimals": int.from_bytes(raw[RES_DECIMALS:RES_DECIMALS+8], "little"),
            "col_mint": b58encode(raw[RES_COL_MINT:RES_COL_MINT+32]),
            "col_supply": b58encode(raw[RES_COL_SUPPLY:RES_COL_SUPPLY+32])}

def resolve(ob_pk: str) -> dict:
    """Pick repay (biggest borrow) + withdraw (biggest deposit) and fetch reserves."""
    raw = acct_raw(ob_pk)
    ob = decode_obligation(raw)
    if not ob["borrows"] or not ob["deposits"]:
        return {"ok": False, "reason": "no debt or no collateral", "ob": ob}
    repay = reserve_info(ob["borrows"][0]["reserve"])
    withdraw = reserve_info(ob["deposits"][0]["reserve"])
    return {"ok": True, "ob_pk": ob_pk, "ob": ob, "repay": repay, "withdraw": withdraw,
            "repay_amount_raw": ob["borrows"][0]["amt_sf"],
            "seize_mv": ob["deposits"][0]["mv"]}

def build_liq_ix(r: dict, liquidator: str, amount: int):
    """V1 flat liquidate ix. Returns (program_id, [(pk,writable,signer)], data)."""
    mkt = r["ob"]["lending_market"]
    mkt_auth = _pda([b"lma", b58decode(mkt)], KLEND)
    rep, wd = r["repay"], r["withdraw"]
    rep_tp = mint_owner(rep["liq_mint"])
    wd_liq_tp = mint_owner(wd["liq_mint"])
    wd_col_tp = mint_owner(wd["col_mint"])
    accts = [
        (liquidator, False, True),
        (r["ob_pk"], True, False),
        (mkt, False, False),
        (mkt_auth, False, False),
        (rep["reserve"], True, False),
        (rep["liq_mint"], False, False),
        (rep["liq_supply"], True, False),
        (wd["reserve"], True, False),
        (wd["liq_mint"], False, False),
        (wd["col_mint"], True, False),
        (wd["col_supply"], True, False),
        (wd["liq_supply"], True, False),
        (wd["liq_feevault"], True, False),
        (ata(liquidator, rep["liq_mint"], rep_tp), True, False),      # userSourceLiquidity
        (ata(liquidator, wd["col_mint"], wd_col_tp), True, False),    # userDestinationCollateral
        (ata(liquidator, wd["liq_mint"], wd_liq_tp), True, False),    # userDestinationLiquidity
        (wd_col_tp, False, False),
        (rep_tp, False, False),
        (wd_liq_tp, False, False),
        (IX_SYSVAR, False, False),
    ]
    data = LIQ_DISC + struct.pack("<QQQ", amount, 1, 0)
    return KLEND, accts, data

def simulate(ob_pk: str, liquidator: str, amount: int) -> dict:
    """Signed-locally legacy tx via live_trader.build_legacy_tx, then
    simulateTransaction(sigVerify=false, replaceRecentBlockhash). Paper only:
    we never send. Uses the exact builder the marginfi path was validated with."""
    import live_trader as lt
    r = resolve(ob_pk)
    if not r.get("ok"):
        return r
    prog, accts, data = build_liq_ix(r, liquidator, amount)
    ixs = [(lt.b58dec(prog), [(lt.b58dec(pk), w, s) for pk, w, s in accts], data)]
    tx_b64 = lt.build_legacy_tx(lt.b58dec(liquidator), ixs)
    res = rpc("simulateTransaction",
              [tx_b64, {"encoding": "base64", "sigVerify": False,
                        "replaceRecentBlockhash": True,
                        "commitment": "confirmed"}])
    return {"resolve": r, "sim": res.get("result") or res}

# --- fire bundle (§462): refresh × reserves, refreshObligation, flash wrap ---
REFRESH_RES_DISC = bytes([2, 218, 138, 235, 79, 201, 25, 102])
REFRESH_OB_DISC = bytes([33, 132, 147, 228, 151, 192, 72, 89])
FLASH_BORROW_DISC = bytes([135, 231, 52, 167, 7, 52, 212, 193])
FLASH_REPAY_DISC = bytes([185, 117, 0, 203, 96, 245, 180, 186])
# oracle offsets in reserve account (§462): scope@5112 swbAgg@5160 pyth@5224 flashFeeSf@4904
RES_SCOPE, RES_SWB, RES_PYTH, RES_FLASHFEE = 5112, 5160, 5224, 4904
NULL_PK = "11111111111111111111111111111111"

def _oracle_slots(reserve_raw: bytes) -> tuple:
    """(pyth, swbPrice, swbTwap, scope) — unused slots get KLEND placeholder
    (ground truth from on-chain refreshReserve tx §462)."""
    def slot(off):
        v = b58encode(reserve_raw[off:off+32])
        return KLEND if v == NULL_PK else v
    return slot(RES_PYTH), slot(RES_SWB), KLEND, slot(RES_SCOPE)

def build_fire_bundle(ob_pk: str, liquidator: str):
    """[refreshReserve(repay), refreshReserve(withdraw), refreshObligation,
    flashBorrow, liquidate, flashRepay]. Swap leg (seized→repay) is inserted
    before flashRepay at fire time from a live Jupiter quote. Returns
    (ixs, meta) where ixs are (prog_bytes, [(key,w,s)], data)."""
    import live_trader as lt
    r = resolve(ob_pk)
    if not r.get("ok"):
        return None, r
    mkt = r["ob"]["lending_market"]
    mkt_auth = _pda([b"lma", b58decode(mkt)], KLEND)
    rep, wd = r["repay"], r["withdraw"]
    rep_raw, wd_raw = acct_raw(rep["reserve"]), acct_raw(wd["reserve"])
    rep_tp = mint_owner(rep["liq_mint"])
    wd_liq_tp = mint_owner(wd["liq_mint"])
    wd_col_tp = mint_owner(wd["col_mint"])
    # debt amount to repay: min(borrow, close-factor) — use full stored debt
    debt_raw = kh_u128(acct_raw(ob_pk), BRW_BASE + 88) // 2 ** 60
    fee_sf = int.from_bytes(rep_raw[RES_FLASHFEE:RES_FLASHFEE+8], "little")
    repay_with_fee = debt_raw + (debt_raw * fee_sf) // 2 ** 60 + 2

    def refresh_reserve_ix(res_pk, raw):
        pyth, swb, swb_twap, scope = _oracle_slots(raw)
        return (b58decode(KLEND), [
            (b58decode(res_pk), True, False),
            (b58decode(mkt), False, False),
            (b58decode(pyth), False, False),
            (b58decode(swb), False, False),
            (b58decode(swb_twap), False, False),
            (b58decode(scope), False, False)], REFRESH_RES_DISC)

    # refreshObligation needs the obligation's reserve accounts as remaining
    # accounts (deposits in slot order, then borrows — non-empty slots only)
    ob_raw = acct_raw(ob_pk)
    rem = []
    for i in range(8):
        o = DEP_BASE + i * DEP_STRIDE
        if int.from_bytes(ob_raw[o+32:o+40], "little"):
            rem.append((ob_raw[o:o+32], False, False))
    for i in range(5):
        o = BRW_BASE + i * BRW_STRIDE
        if kh_u128(ob_raw, o+88):
            rem.append((ob_raw[o:o+32], False, False))
    refresh_ob_ix = (b58decode(KLEND), [
        (b58decode(mkt), False, False),
        (b58decode(ob_pk), True, False)] + rem, REFRESH_OB_DISC)

    def flash_ix(disc, amount, extra_idx_data=b""):
        # accounts identical for borrow/repay except source/dest swap
        return [
            (b58decode(liquidator), True, True),            # userTransferAuthority
            (b58decode(mkt_auth), False, False),
            (b58decode(mkt), False, False),
            (b58decode(rep["reserve"]), True, False),
            (b58decode(rep["liq_mint"]), False, False),
            (b58decode(rep["liq_supply"]), True, False),    # source(borrow)/dest(repay)
            (b58decode(ata(liquidator, rep["liq_mint"], rep_tp)), True, False),
            (b58decode(rep["liq_feevault"]), True, False),
            (b58decode(KLEND), False, False),               # referrerTokenState placeholder
            (b58decode(KLEND), False, False),               # referrerAccount placeholder
            (b58decode(IX_SYSVAR), False, False),
            (b58decode(rep_tp), False, False)]

    flash_borrow = (b58decode(KLEND), flash_ix(FLASH_BORROW_DISC, debt_raw),
                    FLASH_BORROW_DISC + struct.pack("<Q", debt_raw))
    _, liq_accts, liq_data = build_liq_ix(r, liquidator, debt_raw)
    liquidate = (b58decode(KLEND),
                 [(b58decode(pk), w, s) for pk, w, s in liq_accts], liq_data)
    # §462: program checks repay.liquidity_amount == borrow.liquidity_amount
    # (it computes the fee itself) and borrowInstructionIndex == borrow's index
    flash_repay = (b58decode(KLEND), flash_ix(FLASH_REPAY_DISC, debt_raw),
                   FLASH_REPAY_DISC + struct.pack("<Q", debt_raw) + bytes([0]))
    # §463/§472: constraints proven by on-chain sim errors on BYojGuT5:
    #  (a) refreshObligation rejects stale reserves (0x1779) -> an early
    #      [rr_rep, rr_wd, refreshOb] warmup makes the reserve accounts fresh;
    #  (b) check_refresh at liquidate (0x17a3) requires, immediately before
    #      liquidate: [RefreshFarmsForObligationForReserve(withdraw) IF the
    #      withdraw reserve has a collateral farm, RefreshObligation,
    #      RefreshReserve(repay), RefreshReserve(withdraw)].
    # flashBorrow stays FIRST; flashRepay's borrowInstructionIndex stays 0.
    rr_rep = refresh_reserve_ix(rep["reserve"], rep_raw)
    rr_wd  = refresh_reserve_ix(wd["reserve"], wd_raw)
    wd_farm = _farm_of(wd_raw, RES_FARM_COL)
    rep_farm = _farm_of(rep_raw, RES_FARM_DEBT)
    post = []
    if wd_farm:
        post.append(farm_refresh_ix(wd["reserve"], wd_farm, ob_pk, mkt,
                                    mkt_auth, liquidator, 0))
    if rep_farm:
        post.append(farm_refresh_ix(rep["reserve"], rep_farm, ob_pk, mkt,
                                    mkt_auth, liquidator, 1))
    # §472 CANONICAL layout, proven against klend master refresh_ix_utils.rs:
    # required_pre_ixs = [rr(wd), rr(rep), refreshOb, farms...] then REVERSED
    # and checked backward from liquidate; required_post_ixs = [farms...]
    # (NOT reversed) checked FORWARD from liquidate. So:
    #   liq-4=RefreshReserve(WITHDRAW), liq-3=RefreshReserve(REPAY),
    #   liq-2=RefreshObligation, liq-1=FarmsRefresh, LIQ, liq+1=FarmsRefresh.
    # (No-farm case collapses to [rr_wd, rr_rep, refreshOb, LIQ] — the §463
    # layout that passed on 6LTRK3Am.)
    ixs = [flash_borrow,
           rr_wd, rr_rep, refresh_ob_ix, *post,
           liquidate, *post,
           flash_repay]
    return ixs, {"resolve": r, "debt_raw": debt_raw,
                 "repay_with_fee": repay_with_fee,
                 "wd_farm": wd_farm, "rep_farm": rep_farm}

def kh_u128(raw, off):
    return int.from_bytes(raw[off:off+16], "little")

def compile_fire_tx(ixs: list, liquidator: str) -> str:
    """Compile+sign the v0 fire tx via node fire_compile.js (official web3.js
    compiler — my hand-rolled v0 failed RPC sanitize, §464). Returns tx_b64."""
    import subprocess
    def ser(prog, accs, data):
        return {"programId": b58encode(prog),
                "accounts": [{"pubkey": b58encode(k), "isWritable": w,
                              "isSigner": s} for k, w, s in accs],
                "data": list(data)}
    payload = json.dumps({"ixs": [ser(*i) for i in ixs],
                          "walletPath": str(MON / "live_wallet.json"),
                          "altPath": str(ALT_FILE),
                          "heliusPath": str(MON / "helius_key.txt")})
    out = subprocess.run(["node", str(MON / "fire_compile.js")],
                         input=payload, capture_output=True, text=True,
                         timeout=60)
    res = json.loads(out.stdout.strip().splitlines()[-1])
    if res.get("error"):
        raise RuntimeError(res["error"])
    return res["tx_b64"]

def simulate_fire(ob_pk: str, liquidator: str, with_swap: bool = True) -> dict:
    """Full-bundle paper simulation (incl. Jupiter exit leg when mints differ).
    On a HEALTHY obligation, expect failure at swap/flashRepay (nothing seized)
    after all refreshes + flashBorrow + liquidate succeed — the fire-ready
    signature. Atomic revert means a bad fire costs only the (unsent) sim."""
    import live_trader as lt
    ixs, meta = build_fire_bundle(ob_pk, liquidator)
    if ixs is None:
        return meta
    if with_swap:
        r = meta["resolve"]
        est = estimate_seize(r)
        in_mint = r["withdraw"]["liq_mint"]
        out_mint = r["repay"]["liq_mint"]
        swap_ixs, swap_meta = build_swap_leg(in_mint, out_mint, est, liquidator)
        meta["swap"] = {"est_seize": est, **swap_meta}
        if swap_ixs:
            ixs = ixs[:-1] + swap_ixs + [ixs[-1]]  # before flashRepay
    # v0 + ALT via official compiler (§464)
    allkeys = []
    for prog, accs, _ in ixs:
        allkeys.append(b58encode(prog))
        allkeys += [b58encode(k) for k, _, _ in accs]
    allkeys = [k for k in dict.fromkeys(allkeys) if k != liquidator]
    ensure_alt(liquidator, allkeys)
    tx_b64 = compile_fire_tx(ixs, liquidator)
    res = rpc("simulateTransaction",
              [tx_b64, {"encoding": "base64", "sigVerify": False,
                        "replaceRecentBlockhash": True,
                        "commitment": "confirmed"}])
    return {"meta": meta, "sim": res.get("result") or res}

# --- Jupiter exit leg (§464): seized underlying -> repay asset ---
def build_swap_leg(in_mint: str, out_mint: str, amount: int, wallet: str,
                   slippage_bps: int = 150):
    """Jupiter swap-instructions → [(prog, [(k,w,s)], data)]. Any ix with
    <8 bytes of data would PANIC KLend's flash sysvar scan (data[..8] slice),
    so those are flagged and must be excluded from the flash tx."""
    if in_mint == out_mint or amount <= 0:
        return [], {"skipped": "same_mint_or_zero"}
    qurl = ("https://lite-api.jup.ag/swap/v1/quote?inputMint=%s&outputMint=%s"
            "&amount=%d&slippageBps=%d" % (in_mint, out_mint, amount, slippage_bps))
    q = json.loads(urllib.request.urlopen(qurl, timeout=20).read())
    body = json.dumps({"quoteResponse": q, "userPublicKey": wallet,
                       "wrapAndUnwrapSol": False}).encode()  # wSOL ATA pre-staged
    req = urllib.request.Request("https://lite-api.jup.ag/swap/v1/swap-instructions",
                                 data=body, headers={"Content-Type": "application/json"})
    sj = json.loads(urllib.request.urlopen(req, timeout=20).read())
    ixs, short = [], []
    for ins in (sj.get("setupInstructions") or []) + [sj["swapInstruction"]] + \
               (sj.get("cleanupInstructions") or []):
        data = base64.b64decode(ins["data"])
        rec = (b58decode(ins["programId"]),
               [(b58decode(a["pubkey"]), a["isWritable"], a["isSigner"])
                for a in ins["accounts"]], data)
        if len(data) < 8:
            short.append(ins["programId"])  # would panic flash sysvar scan
        else:
            ixs.append(rec)
    return ixs, {"quote_out": int(q.get("outAmount", 0)),
                 "short_ixs_dropped": short}

def estimate_seize(r: dict) -> int:
    """Estimated seized underlying (raw units): debt_mv × (1+min bonus) priced
    into collateral units from the obligation's own stored values, 1% haircut."""
    ob, wd = r["ob"], r["withdraw"]
    dep = ob["deposits"][0]
    brw = ob["borrows"][0]
    if dep["mv"] <= 0 or dep["amount"] <= 0:
        return 0
    wd_raw = acct_raw(wd["reserve"])
    bonus_bps = int.from_bytes(wd_raw[4874:4876], "little")  # minLiquidationBonusBps
    seize_mv = min(brw["mv"] * (1 + bonus_bps / 1e4), dep["mv"])
    px_per_unit = dep["mv"] / dep["amount"]
    return int(seize_mv / px_per_unit * 0.99)

# --- v0 tx + Address Lookup Table (§464): legacy bundle exceeded 1232B ---
ALT_PROG = "AddressLookupTab1e1111111111111111111111111"
ALT_FILE = Path(__file__).parent / "kamino_alt.json"

def _shortvec(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)

def ensure_alt(liquidator: str, extra_keys: list) -> str:
    """Create our ALT if missing and extend with any new keys. Returns address."""
    import live_trader as lt
    state = json.loads(ALT_FILE.read_text()) if ALT_FILE.exists() else {}
    payer_b = b58decode(liquidator)
    if not state.get("address"):
        base = rpc("getLatestBlockhash", [{"commitment": "finalized"}])["result"]["context"]["slot"]
        tab = bump = None
        resp = {}
        # §464: some slots produce no blockhash — walk down until accepted
        for slot in range(base, base - 40, -1):
            for b in range(255, -1, -1):
                h = hashlib.sha256(payer_b + struct.pack("<Q", slot) +
                                   bytes([b]) + b58decode(ALT_PROG) +
                                   b"ProgramDerivedAddress").digest()
                if not _on_curve(h):
                    tab, bump = h, b
                    break
            data = struct.pack("<IQB", 0, slot, bump)
            ixs = [(b58decode(ALT_PROG), [(tab, True, False), (payer_b, False, True),
                    (payer_b, True, True), (b58decode(SYS_PROG), False, False)], data)]
            tx = lt.build_legacy_tx(payer_b, ixs)
            resp = rpc("sendTransaction", [tx, {"encoding": "base64"}])
            if resp.get("result"):
                break
            if "recent slot" not in json.dumps(resp.get("error")):
                break
        if not resp.get("result"):
            raise RuntimeError(f"ALT create failed: {resp.get('error')}")
        state = {"address": b58encode(tab), "keys": []}
        time.sleep(2)
    have = set(state["keys"])
    new = [k for k in dict.fromkeys(extra_keys) if k not in have]
    while new:
        chunk, new = new[:20], new[20:]
        data = struct.pack("<IQ", 2, len(chunk)) + b"".join(b58decode(k) for k in chunk)
        ixs = [(b58decode(ALT_PROG), [(b58decode(state["address"]), True, False),
                (payer_b, False, True), (payer_b, True, True),
                (b58decode(SYS_PROG), False, False)], data)]
        tx = lt.build_legacy_tx(payer_b, ixs)
        resp = rpc("sendTransaction", [tx, {"encoding": "base64"}])
        if not resp.get("result"):
            raise RuntimeError(f"ALT extend failed: {resp.get('error')}")
        state["keys"] += chunk
        time.sleep(1.5)
    ALT_FILE.write_text(json.dumps(state))
    return state["address"]

def build_v0_tx(payer_b: bytes, ixs: list, alt_addr: str, alt_keys: list,
                signers: dict) -> str:
    """Compile+sign a v0 tx. signers: {pubkey_bytes: Ed25519PrivateKey}.
    ALT keys usable as non-signer accounts; jupiter/other route keys go static."""
    alt_b = b58decode(alt_addr)
    alt_set = {b58decode(k): i for i, k in enumerate(alt_keys)}
    meta = {payer_b: [True, True]}
    for prog, accs, _ in ixs:
        for k, w, s in accs:
            e = meta.setdefault(k, [w, s]); e[0] |= w; e[1] |= s
        meta.setdefault(prog, [False, False])
    static, lookups_w, lookups_r = [], [], []
    for k, (w, s) in meta.items():
        if s:
            static.append((k, w, s))  # signers must be static
        elif k in alt_set:
            (lookups_w if w else lookups_r).append(k)
        else:
            static.append((k, w, s))
    lookups_w.sort(key=lambda k: alt_set[k])  # §464: sanitize wants ascending
    lookups_r.sort(key=lambda k: alt_set[k])
    sig_w = sorted([x for x in static if x[2] and x[1]], key=lambda x: 0 if x[0] == payer_b else 1)
    sig_r = [x for x in static if x[2] and not x[1]]
    nw = [x for x in static if not x[2] and x[1]]
    nr = [x for x in static if not x[2] and not x[1]]
    ordered = sig_w + sig_r + nw + nr
    keys = [x[0] for x in ordered]
    # index space: static, then writable lookups, then readonly lookups
    idx = {k: i for i, k in enumerate(keys)}
    for k in lookups_w:
        idx[k] = len(idx)
    for k in lookups_r:
        idx[k] = len(idx)
    bh = rpc("getLatestBlockhash", [{"commitment": "finalized"}])["result"]
    msg = bytearray(b"\x80")
    msg += bytes([len(sig_w) + len(sig_r), len(sig_r), len(nr)])
    msg += _shortvec(len(keys)) + b"".join(keys)
    msg += b58decode(bh["value"]["blockhash"])
    msg += _shortvec(len(ixs))
    for prog, accs, data in ixs:
        msg += bytes([idx[prog]]) + _shortvec(len(accs))
        msg += bytes(idx[k] for k, _, _ in accs)
        msg += _shortvec(len(data)) + data
    msg += _shortvec(1)
    msg += alt_b
    msg += _shortvec(len(lookups_w)) + bytes(alt_set[k] for k in lookups_w)
    msg += _shortvec(len(lookups_r)) + bytes(alt_set[k] for k in lookups_r)
    sigs = [signers[k].sign(bytes(msg)) for k in keys if meta[k][1]]
    tx = _shortvec(len(sigs)) + b"".join(sigs) + bytes(msg)
    return base64.b64encode(tx).decode()

if __name__ == "__main__":
    # paper run against the largest obligation seen by the tail
    import os
    rows = json.loads((MON / "kamino_tail_latest.json").read_text())
    rows = rows.get("rows", rows) if isinstance(rows, dict) else rows
    ob = rows[0]["pubkey"]
    wallet = json.loads((MON / "live_positions.json").read_text())  # noqa (unused)
    print("resolving", ob)
    r = resolve(ob)
    print(json.dumps(r, indent=1)[:1200])
