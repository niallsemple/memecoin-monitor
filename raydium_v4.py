"""raydium_v4.py — READ-ONLY Raydium AMM v4 (legacy) venue access.

Program VERIFIED ON-CHAIN 2026-09-06:
  675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8 (executable).
(My first-draft ID had two garbled chars — PX1M/Huue vs PX9M/Huze.
Registry rule stands: verify on-chain, never trust memory or docs.)

LiquidityStateLayoutV4 (752 bytes, NO Anchor discriminator — raw struct):
  u64 fields 0..319 (status, nonce, ... swap fees ...)
    swapFeeNumerator u64 @176, swapFeeDenominator u64 @184
    baseNeedTakePnl u64 @192, quoteNeedTakePnl u64 @200
  baseVault  Pubkey @336, quoteVault Pubkey @368   (NOT 320/352)
  baseMint   Pubkey @400, quoteMint  Pubkey @432   (NOT 384/416)
  All four EMPIRICALLY VERIFIED 2026-09-06 against the SOL/USDC pool
  58oQChx4yWmvKdwLLZzBi4ChoCc2fqCUWBkwMihLYQo2: WSOL bytes found @400,
  USDC @432; @336/@368 are token accounts of those mints. The classic
  published layout is 16 bytes short here (extra u128 after @312).

Reserves = vault SPL balances MINUS needTakePnl (untaken PnL sits in the
vaults; ignoring it overstates depth slightly — noted, acceptable for
scanning, re-check before any execution).
"""
import base64
import json
import struct
import time
from pathlib import Path

import raydium_cpmm as rc  # reuse rpc + b58 + WSOL

MON = Path(__file__).resolve().parent
CACHE_F = MON / "raydium_v4_pools.json"

POOL_PROG = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
OFF_SWAP_FEE_NUM = 176
OFF_SWAP_FEE_DEN = 184
OFF_BASE_PNL = 192
OFF_QUOTE_PNL = 200
OFF_BASE_VAULT = 336
OFF_QUOTE_VAULT = 368
OFF_BASE_MINT = 400
OFF_QUOTE_MINT = 432
MIN_LEN = 464


def decode_pool(raw_b64):
    d = base64.b64decode(raw_b64)
    if len(d) < MIN_LEN:
        return None
    u64 = lambda o: struct.unpack("<Q", d[o:o + 8])[0]
    return {
        "swap_fee_num": u64(OFF_SWAP_FEE_NUM),
        "swap_fee_den": u64(OFF_SWAP_FEE_DEN),
        "base_pnl": u64(OFF_BASE_PNL),
        "quote_pnl": u64(OFF_QUOTE_PNL),
        "base_vault": rc.b58encode(d[OFF_BASE_VAULT:OFF_BASE_VAULT + 32]),
        "quote_vault": rc.b58encode(d[OFF_QUOTE_VAULT:OFF_QUOTE_VAULT + 32]),
        "base_mint": rc.b58encode(d[OFF_BASE_MINT:OFF_BASE_MINT + 32]),
        "quote_mint": rc.b58encode(d[OFF_QUOTE_MINT:OFF_QUOTE_MINT + 32]),
    }


def find_pools(mint, use_cache=True):
    """AMM v4 pools containing mint. Cached — pools are immutable."""
    cache = json.loads(CACHE_F.read_text()) if CACHE_F.exists() else {}
    if use_cache and mint in cache:
        return cache[mint]
    pools = []
    for off in (OFF_BASE_MINT, OFF_QUOTE_MINT):
        try:
            res = rc.rpc("getProgramAccounts", [POOL_PROG, {
                "encoding": "base64",
                "filters": [{"memcmp": {"offset": off, "bytes": mint}}],
                "dataSlice": {"offset": 0, "length": MIN_LEN}}]) or []
        except Exception:
            continue
        for acc in res:
            p = decode_pool(acc["account"]["data"][0])
            if p and p["swap_fee_den"]:
                p["pool"] = acc["pubkey"]
                pools.append(p)
    cache[mint] = pools
    CACHE_F.write_text(json.dumps(cache, indent=1))
    return pools


def pool_state(pool):
    """Live reserves (vault balances minus untaken PnL) + fee ppm."""
    a0, d0 = rc._vault_amount(pool["base_vault"]), None
    v0 = (rc.rpc("getTokenAccountBalance", [pool["base_vault"]]) or {}).get("value")
    v1 = (rc.rpc("getTokenAccountBalance", [pool["quote_vault"]]) or {}).get("value")
    if not v0 or not v1:
        return None
    r0 = int(v0["amount"]) - pool["base_pnl"]
    r1 = int(v1["amount"]) - pool["quote_pnl"]
    if r0 <= 0 or r1 <= 0:
        return None
    fee_ppm = pool["swap_fee_num"] * 1_000_000 // pool["swap_fee_den"]
    return {"reserve0": r0, "reserve1": r1, "fee_ppm": fee_ppm,
            "pool": pool["pool"],
            "base_mint": pool["base_mint"], "quote_mint": pool["quote_mint"],
            "dec0": int(v0["decimals"]), "dec1": int(v1["decimals"])}


def quote_for_mint(mint, sol_in=None, tokens_in=None):
    """Best (deepest WSOL) pool quote, same contract as raydium_cpmm."""
    best = None
    for p in find_pools(mint):
        if rc.WSOL not in (p["base_mint"], p["quote_mint"]):
            continue
        st = pool_state(p)
        if not st:
            continue
        wsol0 = st["base_mint"] == rc.WSOL
        r_wsol = st["reserve0"] if wsol0 else st["reserve1"]
        if best is None or r_wsol > best[1]:
            best = (st, r_wsol, wsol0)
    if not best:
        return None
    st, _, wsol0 = best
    r_in_w = st["reserve0"] if wsol0 else st["reserve1"]
    r_out_t = st["reserve1"] if wsol0 else st["reserve0"]
    t_dec = st["dec1"] if wsol0 else st["dec0"]
    if sol_in is not None:
        out = rc.cpmm_quote(int(sol_in * 1e9), r_in_w, r_out_t, st["fee_ppm"])
        return {"pool": st["pool"], "tokens_out": out / 10 ** t_dec,
                "fee_ppm": st["fee_ppm"], "depth_sol": r_in_w / 1e9,
                "venue": "raydium_v4"}
    out = rc.cpmm_quote(tokens_in, r_out_t, r_in_w, st["fee_ppm"])
    return {"pool": st["pool"], "sol_out": out / 1e9,
            "fee_ppm": st["fee_ppm"], "depth_sol": r_in_w / 1e9,
            "venue": "raydium_v4"}


if __name__ == "__main__":
    import sys
    mint = sys.argv[1] if len(sys.argv) > 1 else \
        "6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN"  # TRUMP
    t0 = time.time()
    pools = find_pools(mint, use_cache=False)
    print("v4 pools found:", len(pools), "(%.1fs)" % (time.time() - t0))
    print("0.05 SOL buy quote:", json.dumps(quote_for_mint(mint, sol_in=0.05), indent=1))
