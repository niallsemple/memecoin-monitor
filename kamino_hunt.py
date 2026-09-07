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
