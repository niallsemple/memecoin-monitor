"""live_trader.py — live execution path for the memecoin-monitor system.

SAFETY MODEL (two hard gates, BOTH required for a real transaction):
  1. manual_signoff.json must exist in this directory AND contain
     {"live": true}. The OWNER creates this file. The agent never does.
  2. The file STOP_LIVE_TRADING must NOT exist. Drop that file here to
     halt everything instantly (checked before every single trade).

Default mode is DRY-RUN: quotes are fetched and logged, nothing is
signed or submitted. The wallet secret never leaves this machine:
Jupiter returns an unsigned transaction; we sign locally with the
ed25519 key from live_wallet.json and submit via public RPC.

Coverage: Jupiter Ultra/v6 works for PumpSwap (graduated) tokens.
Bonding-curve (pre-graduation) swaps are NOT built here yet — entries
on the curve need the pump.fun program path (§109 work).

All decisions append to mfg_live_trades.jsonl, including dry-runs and
refusals, so the paper record and the live record stay comparable.
"""
import base64
import json
import os
import time
import urllib.request
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

MON = Path(__file__).resolve().parent
WALLET_F = MON / "live_wallet.json"
SIGNOFF_F = MON / "manual_signoff.json"     # owner-created; agent never touches
KILL_F = MON / "STOP_LIVE_TRADING"          # drop this file = instant halt
LEDGER = MON / "mfg_live_trades.jsonl"

SOL = "So11111111111111111111111111111111111111112"
# §164: Helius upgraded (10M credits/mo) BUT its balance/account reads served
# a stale pre-sell snapshot for ~5+ min after a sell landed (verified vs
# mainnet-beta at a NEWER slot). Unsafe for sizing/verification reads.
# Order: public RPCs primary for account state; Helius kept as last fallback
# (its WS birth feed in the tracker is unaffected and benefits from the plan).
_HK_F = MON / "helius_key.txt"
_HK = _HK_F.read_text().strip() if _HK_F.exists() else ""
RPCS = ["https://solana-rpc.publicnode.com",
        "https://api.mainnet-beta.solana.com"] + \
       ([f"https://mainnet.helius-rpc.com/?api-key={_HK}"] if _HK else [])
JUP_Q = "https://lite-api.jup.ag/swap/v1/quote"
JUP_S = "https://lite-api.jup.ag/swap/v1/swap"

# Position sizing: fixed fraction of balance, hard caps.
FRAC = 0.05              # 5% of wallet balance per entry
MAX_SOL = 0.20           # never more than 0.2 SOL on one entry
MIN_BAL_KEEP = 0.05      # always keep this much for fees/rent
SLIPPAGE_BPS = 1500      # memecoin reality; tight slips just fail
PRIOR_FEE_MICROLAMPORTS = 200_000  # ~0.0002 SOL priority fee

_state = {"rpc": 0}


def _log(row):
    row["ts"] = time.time()
    with LEDGER.open("a") as f:
        f.write(json.dumps(row) + "\n")


def _rpc(method, params):
    for attempt in range(4):
        # §164: ordered fallback — Helius first on every call, public only
        # on failure (was round-robin rotation to spare the free endpoints).
        url = RPCS[attempt % len(RPCS)]
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps({"jsonrpc": "2.0", "id": 1,
                                 "method": method, "params": params}).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=25) as r:
                out = json.loads(r.read())
            if "error" in out:
                time.sleep(2.0)
                continue
            return out.get("result")
        except Exception:
            time.sleep(2.0)
    return None


def _tx_success(sig, tries=6, gap=2.5):
    """§137: a signature is not a fill. Confirm the tx landed AND
    succeeded on-chain before position state may be mutated.
    LUTN 2026-09-02: pool_sell returned a sig whose tx failed with
    Custom 6001 (slippage) — tokens never sold, but the book closed
    the position and booked est_sol as recovered."""
    for _ in range(tries):
        st = _rpc("getSignatureStatuses",
                  [[sig], {"searchTransactionHistory": True}])
        v = None
        if st:
            vals = st.get("value") or []
            v = vals[0] if vals else None
        if v:
            if v.get("err"):
                return False
            if v.get("confirmationStatus") in ("confirmed", "finalized"):
                return True
        time.sleep(gap)
    return False


def _load_key():
    d = json.loads(WALLET_F.read_text())
    sec = bytes(d["keypair_bytes"])
    return Ed25519PrivateKey.from_private_bytes(sec[:32]), d["address"]


def live_enabled():
    """Both gates must pass. Returns (bool, reason)."""
    if KILL_F.exists():
        return False, "kill-switch file present"
    if not SIGNOFF_F.exists():
        return False, "no manual_signoff.json (owner has not enabled live)"
    try:
        if not json.loads(SIGNOFF_F.read_text()).get("live"):
            return False, "manual_signoff.json live flag is not true"
    except Exception:
        return False, "manual_signoff.json unreadable"
    return True, "live"


def balance_sol(address):
    # §164b: Helius can serve stale finalized balances (~3 min observed);
    # "confirmed" tracks the tip much closer for sizing decisions.
    r = _rpc("getBalance", [address, {"commitment": "confirmed"}])
    return (r or {}).get("value", 0) / 1e9


def position_size_sol(address):
    bal = balance_sol(address)
    size = min(bal * FRAC, MAX_SOL)
    size = min(size, bal - MIN_BAL_KEEP)
    return max(0.0, round(size, 4)), bal


def jupiter_quote(mint, amount_sol, side="buy"):
    """side=buy: SOL->mint. side=sell: mint->SOL (amount_sol ignored then;
    pass raw token amount via amount_sol=None handled by caller)."""
    if side == "buy":
        params = (f"inputMint={SOL}&outputMint={mint}"
                  f"&amount={int(amount_sol * 1e9)}"
                  f"&slippageBps={SLIPPAGE_BPS}")
    else:
        raise ValueError("sell path needs raw token amount")
    with urllib.request.urlopen(f"{JUP_Q}?{params}", timeout=20) as r:
        return json.loads(r.read())


def jupiter_quote_sell(mint, token_amount_raw, slippage_bps=None):
    """mint->SOL quote for a raw token amount (pool-venue exits)."""
    params = (f"inputMint={mint}&outputMint={SOL}"
              f"&amount={int(token_amount_raw)}"
              f"&slippageBps={slippage_bps or SLIPPAGE_BPS}")
    with urllib.request.urlopen(f"{JUP_Q}?{params}", timeout=20) as r:
        return json.loads(r.read())


def _jupiter_submit(q):
    """Sign a Jupiter quote locally and submit. Returns tx signature."""
    key, address = _load_key()
    req = urllib.request.Request(
        JUP_S,
        data=json.dumps({
            "quoteResponse": q, "userPublicKey": address,
            "wrapAndUnwrapSol": True,
            "prioritizationFeeLamports": PRIOR_FEE_MICROLAMPORTS,
        }).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        swap = json.loads(r.read())
    signed = _sign_versioned_tx(swap["swapTransaction"], key)
    return _rpc("sendTransaction", [signed, {"encoding": "base64"}])


def pool_sell(mint, token_amount_raw, reason="exit", slippage_bps=None):
    """§123: Jupiter sell for graduated (pool-venue) positions."""
    ok, why = live_enabled()
    # §136: 100%-of-balance sells fail in Jupiter with Custom 6024
    # (observed live on J3a25GSe — 4 failed submits; 99.9% simulates
    # clean). Cap every sell at 99.9%; the dust remainder is negligible.
    token_amount_raw = int(token_amount_raw * 0.999)
    row = {"action": "pool_sell", "mint": mint,
           "tokens_raw": int(token_amount_raw), "reason": reason,
           "mode": "live" if ok else "dry-run", "gate": why}
    try:
        q = jupiter_quote_sell(mint, token_amount_raw, slippage_bps)
        row["quote_out_sol"] = int(q.get("outAmount", 0)) / 1e9
        row["quote_price_impact"] = q.get("priceImpactPct")
        if not ok:
            row["result"] = f"dry-run ok ({why})"
        else:
            row["sig"] = _jupiter_submit(q)
            # §127: a submit that returns no signature did NOT land —
            # never report it as submitted.
            row["result"] = "submitted" if row["sig"] else \
                "submit failed: no signature (RPC)"
    except Exception as e:
        row["result"] = f"error: {e}"
    _log(row)
    return row


def _sign_versioned_tx(tx_b64, key):
    """Sign a Jupiter v0 transaction locally. Jupiter txs need exactly one
    signature (the fee payer = us) at signatures[0]."""
    raw = bytearray(base64.b64decode(tx_b64))

    def read_shortvec(buf, i):
        val = shift = 0
        while True:
            b = buf[i]; i += 1
            val |= (b & 0x7F) << shift
            if not b & 0x80:
                return val, i
            shift += 7

    n_sigs, i = read_shortvec(raw, 0)
    msg = bytes(raw[i + 64 * n_sigs:])
    sig = key.sign(msg)
    out = bytearray()
    # rewrite signature array (n_sigs almost always 1)
    out += bytes([n_sigs])
    out += sig
    out += raw[i + 64: i + 64 * n_sigs]      # any remaining sigs (unused)
    out += msg
    return base64.b64encode(bytes(out)).decode()


def buy(mint, reason="signal"):
    """One live (or dry-run) entry. Returns the ledger row."""
    ok, why = live_enabled()
    size, bal = position_size_sol(json.loads(WALLET_F.read_text())["address"])
    row = {"action": "buy", "mint": mint, "reason": reason,
           "size_sol": size, "balance_sol": round(bal, 4),
           "mode": "live" if ok else "dry-run", "gate": why}
    if size <= 0:
        row["result"] = "refused: zero size (balance too low)"
        _log(row)
        return row
    try:
        q = jupiter_quote(mint, size, "buy")
        row["quote_out"] = q.get("outAmount")
        row["tokens_raw"] = q.get("outAmount")
        row["quote_price_impact"] = q.get("priceImpactPct")
    except Exception as e:
        row["result"] = f"quote failed: {e}"
        _log(row)
        return row
    if not ok:
        row["result"] = f"dry-run ok ({why})"
        _log(row)
        return row
    try:
        row["sig"] = _jupiter_submit(q)
        # §127: a submit that returns no signature did NOT land —
        # never report it as submitted.
        row["result"] = "submitted" if row["sig"] else \
            "submit failed: no signature (RPC)"
        # §137b: a signature is not a fill — verify on-chain success.
        # Prefix "error:" so the automation leaves the signal
        # unconsumed and retries instead of opening a ghost position.
        if row["sig"] and not _tx_success(row["sig"]):
            row["result"] = "error: buy tx failed on-chain (sig present)"
    except Exception as e:
        row["result"] = f"submit failed: {e}"
    _log(row)
    return row


if __name__ == "__main__":
    ok, why = live_enabled()
    d = json.loads(WALLET_F.read_text())
    size, bal = position_size_sol(d["address"])
    print(f"address : {d['address']}")
    print(f"balance : {bal:.4f} SOL")
    print(f"mode    : {'LIVE' if ok else 'DRY-RUN'} ({why})")
    print(f"next buy size: {size} SOL")


# ======================= §111: pump.fun bonding-curve path =======================
# Canonical layouts from the on-chain Anchor IDL (§110, pump_idl.json).
# Legacy transaction building, local ed25519 signing, dry-run gated.
# Buys are TOKEN-amount + max-SOL-cap; sells are token-amount + min-SOL floor.
import hashlib
import struct

ALPH58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
def b58dec(s):
    n = 0
    for c in s:
        n = n * 58 + ALPH58.index(c)
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return b"\0" * (len(s) - len(s.lstrip("1"))) + b
def b58enc(b):
    n = int.from_bytes(b, "big"); s = ""
    while n:
        n, r = divmod(n, 58); s = ALPH58[r] + s
    return "1" * (len(b) - len(b.lstrip(b"\0"))) + s

_P = 2**255 - 19
_D = (-121665 * pow(121666, _P - 2, _P)) % _P
def _on_curve(yb):
    y = int.from_bytes(yb, "little") & ((1 << 255) - 1)
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    return x2 == 0 or pow(x2, (_P - 1) // 2, _P) == 1
def pda(seeds, prog):
    for bump in range(255, -1, -1):
        h = hashlib.sha256()
        for s in seeds:
            h.update(s)
        h.update(bytes([bump])); h.update(prog)
        h.update(b"ProgramDerivedAddress")
        out = h.digest()
        if not _on_curve(out):
            return out
    raise ValueError("no PDA bump")

PUMP_PROG = b58dec("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
FEE_PROG  = b58dec("pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ")
ATA_PROG  = b58dec("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
SYS_PROG  = b58dec("11111111111111111111111111111111")
TOKENKEG  = b58dec("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
TOKEN2022 = b58dec("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")
CMP_PROG  = b58dec("ComputeBudget111111111111111111111111111111")
FEE_CFG_C = bytes([1,86,224,246,147,102,90,207,68,219,21,104,191,23,91,170,
                   81,137,203,151,245,210,255,59,101,93,43,182,253,109,24,176])
BUY_DISC  = bytes.fromhex("66063d1201daebea")
SELL_DISC = bytes.fromhex("33e685a4017f83ad")

G_GLOBAL = pda([b"global"], PUMP_PROG)
G_EVENT_AUTH = pda([b"__event_authority"], PUMP_PROG)
G_GVA = pda([b"global_volume_accumulator"], PUMP_PROG)
G_FEE_CFG = pda([b"fee_config", FEE_CFG_C], FEE_PROG)


def _get_account(address, _null_retries=3):
    import base64 as _b64
    # §133: brand-new mints can return a SUCCESSFUL null value while RPC
    # nodes lag propagation — treat null as retryable, not terminal.
    r = None
    for _attempt in range(_null_retries + 1):
        r = _rpc("getAccountInfo", [address, {"encoding": "base64"}])
        if r and r.get("value"):
            break
        if _attempt < _null_retries:
            time.sleep(2.0)
    if not r or not r.get("value"):
        return None
    v = r["value"]
    return {"owner": v["owner"],
            "lamports": v["lamports"],
            "data": _b64.b64decode(v["data"][0])}


def curve_state(mint):
    """Return dict with reserves/fee info for a bonding-curve mint."""
    mb = b58dec(mint)
    mint_acc = _get_account(mint)
    if not mint_acc:
        raise ValueError("mint not found")
    token_prog = b58dec(mint_acc["owner"])
    curve = pda([b"bonding-curve", mb], PUMP_PROG)
    cc = _get_account(b58enc(curve))
    if not cc:
        raise ValueError("bonding curve not found (graduated?)")
    d = cc["data"]
    v_tok, v_sol, r_tok, r_sol, supply = struct.unpack("<5Q", d[8:48])
    complete = d[48] != 0
    glob = _get_account(b58enc(G_GLOBAL))
    fee_bps = struct.unpack("<Q", glob["data"][105:113])[0]
    creator_bps = struct.unpack("<Q", glob["data"][154:162])[0]
    fee_recipient = b58enc(glob["data"][41:73])
    return {"v_tok": v_tok, "v_sol": v_sol, "complete": complete,
            "token_prog": token_prog, "curve": curve,
            "fee_bps": fee_bps, "creator_bps": creator_bps,
            "fee_recipient": fee_recipient}


def tokens_for_sol(st, sol_lamports):
    """Expected tokens out for sol in (constant-product on virtual
    reserves, fees deducted from input)."""
    eff = sol_lamports * (10_000 - st["fee_bps"] - st["creator_bps"]) // 10_000
    return eff * st["v_tok"] // (st["v_sol"] + eff)


def sol_for_tokens(st, token_amount):
    """Expected SOL out for tokens in (fees deducted from output)."""
    gross = token_amount * st["v_sol"] // (st["v_tok"] + token_amount)
    return gross * (10_000 - st["fee_bps"] - st["creator_bps"]) // 10_000


def _shortvec(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def build_legacy_tx(payer_b, instructions):
    """instructions: list of (program_id_bytes, [(key_bytes, writable, signer)],
    data_bytes). Compiles keys, signs locally, returns base64 tx."""
    # compile account keys: payer first, then writable, then readonly
    keys = [payer_b]
    meta = {payer_b: [True, True]}  # writable, signer
    for prog, accs, _ in instructions:
        for k, w, s in accs:
            if k not in meta:
                meta[k] = [w, s]
                keys.append(k)
            else:
                meta[k][0] = meta[k][0] or w
                meta[k][1] = meta[k][1] or s
        if prog not in meta:
            meta[prog] = [False, False]
            keys.append(prog)
    signers = [k for k in keys if meta[k][1]]
    writable = [k for k in keys if not meta[k][1] and meta[k][0]]
    readonly = [k for k in keys if not meta[k][1] and not meta[k][0]]
    ordered = signers + writable + readonly
    idx = {k: i for i, k in enumerate(ordered)}
    n_sig = len(signers)
    n_ro_sig = sum(1 for k in signers if not meta[k][0])
    n_ro_unsig = len(readonly)
    bh = _rpc("getLatestBlockhash", [{"commitment": "finalized"}])
    if not bh:
        raise RuntimeError("no blockhash")
    blockhash = b58dec(bh["value"]["blockhash"])
    msg = bytearray()
    msg += bytes([n_sig, n_ro_sig, n_ro_unsig])
    msg += _shortvec(len(ordered))
    for k in ordered:
        msg += k
    msg += blockhash
    msg += _shortvec(len(instructions))
    for prog, accs, data in instructions:
        msg += bytes([idx[prog]])
        msg += _shortvec(len(accs))
        for k, _, _ in accs:
            msg += bytes([idx[k]])
        msg += _shortvec(len(data)) + data
    key, _addr = _load_key()
    sig = key.sign(bytes(msg))
    tx = _shortvec(n_sig) + sig + b"\0" * 64 * (n_sig - 1) + bytes(msg)
    return base64.b64encode(bytes(tx)).decode()


def _ata(owner_b, mint_b, token_prog_b):
    return pda([owner_b, token_prog_b, mint_b], ATA_PROG)


def curve_buy(mint, sol_amount, reason="signal"):
    """Live/dry-run bonding-curve buy. Same gates as Jupiter path."""
    ok, why = live_enabled()
    addr = json.loads(WALLET_F.read_text())["address"]
    row = {"action": "curve_buy", "mint": mint, "reason": reason,
           "mode": "live" if ok else "dry-run", "gate": why}
    try:
        st = curve_state(mint)
        if st["complete"]:
            row["result"] = "refused: curve complete (use Jupiter path)"
            _log(row); return row
        lamports = int(sol_amount * 1e9)
        expect = tokens_for_sol(st, lamports)
        min_tokens = int(expect * 0.85)          # 15% adverse-move guard
        mb = b58dec(mint)
        ub = b58dec(addr)
        user_ata = _ata(ub, mb, st["token_prog"])
        creator_vault = None
        # creator from chain: bonding curve data has no creator post-2025;
        # creator vault = PDA["creator-vault", creator]; creator read from
        # the curve account tail (pubkey at offset 49) when present.
        cc = _get_account(b58enc(st["curve"]))
        creator = cc["data"][49:81] if len(cc["data"]) >= 81 else None
        if not creator or creator == b"\0" * 32:
            row["result"] = "refused: creator unknown"
            _log(row); return row
        creator_vault = pda([b"creator-vault", creator], PUMP_PROG)
        ixs = [
            (CMP_PROG, [], struct.pack("<BI", 2, 300_000)),
            (CMP_PROG, [], struct.pack("<BQ", 3, PRIOR_FEE_MICROLAMPORTS)),
            (ATA_PROG, [(ub, True, True), (user_ata, True, False),
                        (ub, False, False), (mb, False, False),
                        (SYS_PROG, False, False), (st["token_prog"], False, False)],
             b"\x01"),  # createIdempotent
            (PUMP_PROG, [
                (G_GLOBAL, False, False),
                (b58dec(st["fee_recipient"]), True, False),
                (mb, False, False),
                (st["curve"], True, False),
                (_ata(st["curve"], mb, st["token_prog"]), True, False),
                (user_ata, True, False),
                (ub, True, True),
                (SYS_PROG, False, False),
                (st["token_prog"], False, False),
                (creator_vault, True, False),
                (G_EVENT_AUTH, False, False),
                (PUMP_PROG, False, False),
                (G_GVA, False, False),
                (pda([b"user_volume_accumulator", ub], PUMP_PROG), True, False),
                (G_FEE_CFG, False, False),
                (FEE_PROG, False, False),
            ], BUY_DISC + struct.pack("<QQ", min_tokens, lamports)),
        ]
        tx_b64 = build_legacy_tx(ub, ixs)
        row["expect_tokens"] = expect
        row["min_tokens"] = min_tokens
        row["size_sol"] = sol_amount
        if not ok:
            # free structural validation: simulate without sig check
            sim = _rpc("simulateTransaction",
                       [tx_b64, {"encoding": "base64", "sigVerify": False,
                                 "replaceRecentBlockhash": True}])
            row["simulation"] = (sim or {}).get("value", {})
            row["result"] = f"dry-run built+simulated ({why})"
        else:
            sig = _rpc("sendTransaction", [tx_b64, {"encoding": "base64"}])
            row["result"] = "submitted"; row["sig"] = sig
            # §137b: verify on-chain success; "error:" keeps the signal
            # unconsumed so the next run retries instead of ghosting.
            if sig and not _tx_success(sig):
                row["result"] = "error: buy tx failed on-chain (sig present)"
    except Exception as e:
        row["result"] = f"error: {e}"
    _log(row)
    return row


def curve_sell(mint, token_amount, min_sol_out=0, reason="exit"):
    """Live/dry-run bonding-curve sell. Pass min_sol_out>0 for honest
    slippage floor (bots pass 0; we don't)."""
    ok, why = live_enabled()
    addr = json.loads(WALLET_F.read_text())["address"]
    row = {"action": "curve_sell", "mint": mint, "tokens": token_amount,
           "reason": reason, "mode": "live" if ok else "dry-run", "gate": why}
    try:
        st = curve_state(mint)
        mb = b58dec(mint); ub = b58dec(addr)
        user_ata = _ata(ub, mb, st["token_prog"])
        cc = _get_account(b58enc(st["curve"]))
        creator = cc["data"][49:81] if len(cc["data"]) >= 81 else None
        creator_vault = pda([b"creator-vault", creator], PUMP_PROG)
        ixs = [
            (CMP_PROG, [], struct.pack("<BI", 2, 200_000)),
            (CMP_PROG, [], struct.pack("<BQ", 3, PRIOR_FEE_MICROLAMPORTS)),
            (PUMP_PROG, [
                (G_GLOBAL, False, False),
                (b58dec(st["fee_recipient"]), True, False),
                (mb, False, False),
                (st["curve"], True, False),
                (_ata(st["curve"], mb, st["token_prog"]), True, False),
                (user_ata, True, False),
                (ub, True, True),
                (SYS_PROG, False, False),
                (creator_vault, True, False),
                (st["token_prog"], False, False),
                (G_EVENT_AUTH, False, False),
                (PUMP_PROG, False, False),
                (G_FEE_CFG, False, False),
                (FEE_PROG, False, False),
            ], SELL_DISC + struct.pack("<QQ", token_amount, min_sol_out)),
        ]
        tx_b64 = build_legacy_tx(ub, ixs)
        row["expect_sol"] = sol_for_tokens(st, token_amount) / 1e9
        if not ok:
            sim = _rpc("simulateTransaction",
                       [tx_b64, {"encoding": "base64", "sigVerify": False,
                                 "replaceRecentBlockhash": True}])
            row["simulation"] = (sim or {}).get("value", {})
            row["result"] = f"dry-run built+simulated ({why})"
        else:
            sig = _rpc("sendTransaction", [tx_b64, {"encoding": "base64"}])
            row["result"] = "submitted"; row["sig"] = sig
    except Exception as e:
        row["result"] = f"error: {e}"
    _log(row)
    return row


# ======================= §113: exit watcher =======================
# Manages open positions (dry-run or live) with the §56e exit stack:
# freeroll 75% at 1.5x, trail at 50% of peak, abort15 (<1.08x at 15m),
# abort30 (<1.15x at 30m), timestop at 120m. Runs inside the tracker
# pass (~10-15 min cadence) — fine for aborts/timestop, but the
# freeroll window can be SECONDS after entry; a dedicated faster loop
# is future work. Every decision (hold/freeroll/exit) is ledgered.
POSITIONS = MON / "live_positions.json"
P_FR_TARGET = 1.5     # freeroll trigger
P_FR_SELL = 0.75      # sell 75%
P_TRAIL_F = 0.5       # trail at 50% of peak
P_ABORT15 = (15, 1.08)
P_ABORT30 = (30, 1.15)
P_TIMESTOP_MIN = 120
P_NM_TOUCH = 1.30   # §131: momentum-touch level that arms nm_abort
P_NM_MIN = 5        # minutes below freeroll target after touch -> exit
# §138: pre-nm fade exit. LUTN drained from peak 1.2814x without ever
# arming nm_touch; paper band [1.15,1.30) finished -43.9% (n=1) while
# exiting at 0.90x peak would have booked ~+3.8%. Only applies BEFORE
# the 1.30x touch (nm cohort keeps the working nm_abort path).
P_FADE_PEAK = 1.15  # minimum peak that arms the fade exit
P_FADE_K = 0.90     # exit when r falls to this fraction of peak
# §148: panic stop. LUTN drained 1.27->0.006 in <3min between watcher
# ticks and 29H7 sat at ~1.0 then hit 0.0 before abort15's age gate —
# both returned dust. Any tick seeing r below P_PANIC sells immediately
# regardless of age, to catch fast drains mid-flight and recover a
# fraction instead of nothing. Trades off ~20% givebacks on wicked dips.
P_PANIC = 0.80      # instant market sell if r < this at any check


def _load_positions():
    if POSITIONS.exists():
        try:
            return json.loads(POSITIONS.read_text())
        except Exception:
            pass
    return {}


def _save_positions(p):
    POSITIONS.write_text(json.dumps(p, indent=1))


def _price_sol_per_token(st):
    return st["v_sol"] / st["v_tok"] if st["v_tok"] else 0.0


def open_position(mint, size_sol, mode, venue="curve", entry_px=None,
                  tokens=None):
    """Record a position after a (dry-run or live) entry fill.
    venue="pool" = graduated token bought via Jupiter; entry_px and
    tokens (raw) come from the buy quote — the curve no longer exists."""
    pos = _load_positions()
    if mint in pos and pos[mint].get("open"):
        return pos[mint]
    if venue == "curve":
        st = curve_state(mint)
        entry_px = _price_sol_per_token(st)
        tokens = tokens_for_sol(st, int(size_sol * 1e9))
    pos[mint] = {"open": True, "mode": mode, "venue": venue,
                 "entry_t": time.time(),
                 "entry_px": entry_px, "tokens": tokens,
                 "tokens_left": tokens, "size_sol": size_sol,
                 "peak_mult": 1.0, "freerolled": False,
                 "sol_recovered": 0.0}
    _save_positions(pos)
    _log({"action": "open_position", "mint": mint, "mode": mode,
          "venue": venue, "size_sol": size_sol, "tokens": tokens,
          "entry_px": entry_px})
    _shadow_insider_screen(mint, pos)
    return pos[mint]


# §191: insider-overhang shadow screen at entry (non-blocking).
# §189 fingerprint: drain killers are whales that never bought via the
# pool. Snapshot top-holders vs pool-buyer history at entry; log only —
# promotion to a blocking gate awaits forward correlation evidence.
AMM_PROG = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"


def _discover_pool(mint):
    try:
        r = _rpc("getProgramAccounts",
                 [AMM_PROG, {"encoding": "base64",
                             "filters": [{"memcmp": {"offset": 43,
                                                     "bytes": mint}}],
                             "dataSlice": {"offset": 0, "length": 0}}])
        accts = r or []
        return accts[0]["pubkey"] if accts else None
    except Exception:
        return None


BLOCKLIST_F = MON / "drainer_blocklist.json"


def _blocklist_wallets():
    """All known drainer-network wallets (masters, killers, feeders)."""
    try:
        bl = json.loads(BLOCKLIST_F.read_text())
        out = set()
        for section in ("masters", "killers", "feeders", "funded_next_gen"):
            out.update(bl.get(section, {}))
        return out
    except Exception:
        return set()


def _feeder_count(mint):
    """§195: blocklist wallets active on this mint in the ledger.
    Retrospective: feeders present on 2/36 mints, BOTH drained."""
    bl = _blocklist_wallets()
    if not bl:
        return 0, []
    import wallet_ledger
    hits = {}
    if wallet_ledger.LEDGER.exists():
        for line in wallet_ledger.LEDGER.open():
            if not line.strip():
                continue
            r = json.loads(line)
            if r["mint"] == mint and r["wallet"] in bl:
                hits[r["wallet"]] = hits.get(r["wallet"], 0) + 1
    return len(hits), sorted(hits)[:8]


def _shadow_insider_screen(mint, pos):
    try:
        import wallet_ledger
        import insider_screen
        pool = insider_screen.POOLS.get(mint) or _discover_pool(mint)
        if not pool:
            _log({"action": "insider_screen", "mint": mint,
                  "error": "no pool found"})
            return
        # make sure the ledger has this mint's pool buyers first
        wallet_ledger.update(mint, pool)
        if mint not in insider_screen.POOLS:
            insider_screen.POOLS[mint] = pool
        s = insider_screen.screen(mint)
        f_n, f_wallets = _feeder_count(mint)
        pos[mint]["insider_overhang_pct"] = s.get("overhang_pct")
        pos[mint]["insider_n"] = len(s.get("insiders", []))
        pos[mint]["blocklist_feeders"] = f_n
        _save_positions(pos)
        _log({"action": "insider_screen", "mint": mint,
              "overhang_pct": s.get("overhang_pct"),
              "insider_n": len(s.get("insiders", [])),
              "blocklist_feeders": f_n,
              "feeder_wallets": f_wallets,
              "insiders": [i["owner"] for i in s.get("insiders", [])][:8]})
        if f_n:
            _log({"action": "DRAINER_NETWORK_ALERT", "mint": mint,
                  "blocklist_feeders": f_n, "wallets": f_wallets})
    except Exception as e:
        _log({"action": "insider_screen", "mint": mint,
              "error": str(e)[:150]})


def exit_watch():
    """One pass over open positions. Returns list of actions taken."""
    pos = _load_positions()
    actions = []
    for mint, p in list(pos.items()):
        if not p.get("open"):
            continue
        try:
            venue = p.get("venue", "curve")
            if venue == "pool":
                # §123: graduated position — per-token price from a
                # Jupiter sell quote on the remaining stack (quote is
                # size-aware; at our size impact is within slippage).
                q = jupiter_quote_sell(mint, p["tokens_left"])
                est_left_sol = int(q.get("outAmount", 0)) / 1e9
                px = (est_left_sol / p["tokens_left"]
                      if p["tokens_left"] else 0.0)
                st = None
            else:
                st = curve_state(mint)
                px = _price_sol_per_token(st)
            r = px / p["entry_px"] if p["entry_px"] else 0.0
            p["peak_mult"] = max(p["peak_mult"], r)
            mins = (time.time() - p["entry_t"]) / 60
            # §131: nm_abort — momentum-stall exit. Forward paper tally:
            # the cohort that touched 1.30x but failed to reach the 1.5x
            # freeroll within 5 min exited at +34.5% avg (n=14); riding
            # those to timestop risks the drain. Track first 1.30x touch.
            if not p["freerolled"] and r >= P_NM_TOUCH \
                    and p.get("nm_touch_t") is None:
                p["nm_touch_t"] = time.time()
            act = None
            sell_tokens = 0
            if not p["freerolled"] and r >= P_FR_TARGET:
                act, sell_tokens = "freeroll", int(p["tokens_left"] * P_FR_SELL)
            elif p["freerolled"] and r <= P_TRAIL_F * p["peak_mult"]:
                act, sell_tokens = "trail", p["tokens_left"]
            elif not p["freerolled"] and r < P_PANIC:
                act, sell_tokens = "panic", p["tokens_left"]
            elif not p["freerolled"] and p.get("nm_touch_t") \
                    and (time.time() - p["nm_touch_t"]) >= P_NM_MIN * 60 \
                    and r < P_FR_TARGET:
                act, sell_tokens = "nm_abort", p["tokens_left"]
            elif not p["freerolled"] and p.get("nm_touch_t") is None \
                    and p["peak_mult"] >= P_FADE_PEAK \
                    and r <= P_FADE_K * p["peak_mult"]:
                act, sell_tokens = "fade", p["tokens_left"]
            elif not p["freerolled"] and mins >= P_ABORT15[0] and r < P_ABORT15[1]:
                act, sell_tokens = "abort15", p["tokens_left"]
            elif not p["freerolled"] and mins >= P_ABORT30[0] and r < P_ABORT30[1]:
                act, sell_tokens = "abort30", p["tokens_left"]
            elif not p["freerolled"] and mins >= P_TIMESTOP_MIN:
                act, sell_tokens = "timestop", p["tokens_left"]
            if act:
                if venue == "pool":
                    est_sol = px * sell_tokens
                    res = pool_sell(mint, sell_tokens, reason=act)
                    # §176: panic slippage escalation — LUTN and 29H7
                    # drained to zero while their 15%-slip sells kept
                    # failing Custom 6001 mid-collapse. On a verified
                    # failed panic, immediately re-quote wider: 30%,
                    # then 50%. A deep-discount fill beats zero.
                    # §176b: escalation extended to nm_abort/fade —
                    # all three sell into weakening momentum where a
                    # rejected tx risks riding to zero. Clock exits
                    # (abort15/30, timestop) stay single-shot: flat
                    # positions, safe to retry next pass.
                    if act in ("panic", "nm_abort", "fade") \
                            and res.get("sig") \
                            and not _tx_success(res["sig"]):
                        _log({"action": "slip_escalate", "mint": mint,
                              "exit": act, "first_sig": res["sig"]})
                        for _wide in (3000, 5000):
                            res = pool_sell(mint, sell_tokens,
                                            reason=f"{act}_slip{_wide}",
                                            slippage_bps=_wide)
                            if res.get("sig") and _tx_success(res["sig"]):
                                break
                else:
                    est_sol = sol_for_tokens(st, sell_tokens) / 1e9
                    res = curve_sell(mint, sell_tokens,
                                     min_sol_out=int(est_sol * 0.85 * 1e9),
                                     reason=act)
                # §127: only mutate position state when the exit REALLY
                # happened — dry-run, or a live submit that returned a
                # signature. A signature-less "submitted" never landed;
                # keep the position open so the next pass retries.
                _ok_res = (str(res.get("result", "")).startswith("dry-run")
                           or (res.get("result") == "submitted"
                               and res.get("sig")))
                # §137: verify the submitted tx actually succeeded
                # on-chain; a failed tx leaves the position open so
                # the next pass retries the exit.
                if _ok_res and res.get("sig") and not str(
                        res.get("result", "")).startswith("dry-run"):
                    if not _tx_success(res["sig"]):
                        res["result"] = "tx failed on-chain (sig present)"
                        _ok_res = False
                if not _ok_res:
                    actions.append({"mint": mint, "act": "exit_failed",
                                    "r": round(r, 3),
                                    "result": res.get("result")})
                    _log({"action": "exit_failed", "mint": mint, "exit": act,
                          "mult": round(r, 3), "mins_open": round(mins, 1),
                          "result": res.get("result")})
                    continue
                p["sol_recovered"] += est_sol
                p["tokens_left"] -= sell_tokens
                if act == "freeroll":
                    p["freerolled"] = True
                else:
                    p["open"] = False
                    p["closed_reason"] = act
                    p["pnl_sol"] = round(
                        p["sol_recovered"] - p["size_sol"], 5)
                actions.append({"mint": mint, "act": act, "r": round(r, 3),
                                "est_sol": round(est_sol, 5),
                                "result": res.get("result")})
                _log({"action": "exit_decision", "mint": mint, "exit": act,
                      "mult": round(r, 3), "mins_open": round(mins, 1),
                      "est_sol": round(est_sol, 5),
                      "result": res.get("result")})
            else:
                actions.append({"mint": mint, "act": "hold",
                                "r": round(r, 3)})
        except Exception as e:
            actions.append({"mint": mint, "act": "error",
                            "err": str(e)[:100]})
    _save_positions(pos)
    return actions
