"""raydium_cpmm.py — Phase 1: READ-ONLY Raydium CPMM venue access.

§scope RAYDIUM_SCOPE.md. Verified 2026-09-06 ON-CHAIN:
  POOL_PROG = CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C exists and is
  executable (BPFLoaderUpgradeable); the SEO-page variant ...THS4K9uP6eh
  does NOT exist. Never trust docs for program IDs.

PoolState (Anchor, 8-byte discriminator first):
  +32 amm_config  +64 pool_creator  +96 token_0_vault  +128 token_1_vault
  +160 lp_mint  +192 token_0_mint?? — NO: offsets measured from 0:
  disc 0-8, amm_config 8-40, pool_creator 40-72, token_0_vault 72-104,
  token_1_vault 104-136, lp_mint 136-168, token_0_mint 168-200,
  token_1_mint 200-232, token_0_program 232-264, token_1_program 264-296,
  observation_key 296-328, then packed smalls: auth_bump u8 @328,
  status u8 @329, lp_dec u8 @330, mint0_dec u8 @331, mint1_dec u8 @332,
  lp_supply u64 @333, fees..., open_time u64 @357.

AmmConfig (Anchor): disc 0-8, bump/flags @8-11 (packed smalls + pad),
  trade_fee_rate u32 @12 (per-million) — VERIFIED ON-CHAIN 2026-09-06 on
  config ...ff000000 c4090000 -> 2500ppm = 0.25%. (Offset 11 reads 640000,
  the one-byte-shifted ghost; do not trust borsh-packed guesses.)

Reserves are NOT stored in PoolState — read vault SPL token account
balances (amount u64 @ offset 64).

Usage: python3 raydium_cpmm.py <mint>   # prints pools + sell quote
"""
import base64
import json
import struct
import time
from pathlib import Path

MON = Path(__file__).resolve().parent
CACHE_F = MON / "raydium_pools.json"

POOL_PROG = "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C"
WSOL = "So11111111111111111111111111111111111111112"

# ---- base58 decode (no deps) ------------------------------------------------
_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58decode(s):
    n = 0
    for ch in s:
        n = n * 58 + _B58.index(ch)
    b = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    pad = len(s) - len(s.lstrip("1"))
    return b"\x00" * pad + b


def b58encode(b):
    n = int.from_bytes(b, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = _B58[r] + out
    pad = len(b) - len(b.lstrip(b"\x00"))
    return "1" * pad + (out or "")


# ---- RPC (reuse live_trader's rotating endpoints) ----------------------------
_lt = None


def _load_lt():
    global _lt
    if _lt is None:
        import importlib.util as il
        s = il.spec_from_file_location("lt", MON / "live_trader.py")
        _lt = il.module_from_spec(s)
        s.loader.exec_module(_lt)
    return _lt


def rpc(method, params):
    return _load_lt()._rpc(method, params)


# ---- PoolState decode --------------------------------------------------------
def decode_pool(raw_b64):
    d = base64.b64decode(raw_b64)
    if len(d) < 341:
        return None
    return {
        "amm_config": b58encode(d[8:40]),
        "token_0_vault": b58encode(d[72:104]),
        "token_1_vault": b58encode(d[104:136]),
        "token_0_mint": b58encode(d[168:200]),
        "token_1_mint": b58encode(d[200:232]),
        "status": d[329],
        "mint0_dec": d[331],
        "mint1_dec": d[332],
        "lp_supply": struct.unpack("<Q", d[333:341])[0],
    }


def trade_fee_rate(amm_config_addr):
    """trade_fee_rate (per-million) from the AmmConfig account."""
    r = rpc("getAccountInfo", [amm_config_addr, {"encoding": "base64"}])
    v = (r or {}).get("value")
    if not v:
        return None
    d = base64.b64decode(v["data"][0])
    if len(d) < 16:
        return None
    return struct.unpack("<I", d[12:16])[0]


def _vault_amount(addr):
    r = rpc("getTokenAccountBalance", [addr])
    v = (r or {}).get("value")
    return int(v["amount"]) if v else None


def find_pools(mint, use_cache=True):
    """All CPMM pools containing mint (either side). Cached: pools are
    immutable, so a found pool never needs re-discovery."""
    cache = json.loads(CACHE_F.read_text()) if CACHE_F.exists() else {}
    if use_cache and mint in cache:
        return cache[mint]
    pools = []
    for off in (168, 200):  # token_0_mint / token_1_mint offsets
        try:
            res = rpc("getProgramAccounts", [POOL_PROG, {
                "encoding": "base64",
                "filters": [{"memcmp": {"offset": off, "bytes": mint}}],
                "dataSlice": {"offset": 0, "length": 341},
            }]) or []
        except Exception:
            continue
        for acc in res:
            p = decode_pool(acc["account"]["data"][0])
            if p:
                p["pool"] = acc["pubkey"]
                pools.append(p)
    cache[mint] = pools
    CACHE_F.write_text(json.dumps(cache, indent=1))
    return pools


def pool_state(pool):
    """Live reserves + fee for a decoded pool dict."""
    a0 = _vault_amount(pool["token_0_vault"])
    a1 = _vault_amount(pool["token_1_vault"])
    fee = trade_fee_rate(pool["amm_config"])
    if a0 is None or a1 is None or fee is None:
        return None
    return {"reserve0": a0, "reserve1": a1, "fee_ppm": fee,
            "pool": pool["pool"],
            "token_0_mint": pool["token_0_mint"],
            "token_1_mint": pool["token_1_mint"],
            "mint0_dec": pool["mint0_dec"], "mint1_dec": pool["mint1_dec"]}


def cpmm_quote(amount_in, reserve_in, reserve_out, fee_ppm):
    """Constant-product with per-million fee. Returns raw output amount."""
    in_eff = amount_in * (1_000_000 - fee_ppm)
    return (in_eff * reserve_out) // (reserve_in * 1_000_000 + in_eff)


def quote_for_mint(mint, sol_in=None, tokens_in=None):
    """Best-pool quote. sol_in (SOL float) -> tokens_out; tokens_in (raw int)
    -> sol_out. Picks the deepest WSOL pool."""
    best = None
    for p in find_pools(mint):
        if WSOL not in (p["token_0_mint"], p["token_1_mint"]):
            continue
        st = pool_state(p)
        if not st:
            continue
        wsol0 = st["token_0_mint"] == WSOL
        r_wsol = st["reserve0"] if wsol0 else st["reserve1"]
        if best is None or r_wsol > best[1]:
            best = (st, r_wsol, wsol0)
    if not best:
        return None
    st, _, wsol0 = best
    r_in_w = st["reserve0"] if wsol0 else st["reserve1"]
    r_out_t = st["reserve1"] if wsol0 else st["reserve0"]
    t_dec = st["mint1_dec"] if wsol0 else st["mint0_dec"]
    if sol_in is not None:
        out = cpmm_quote(int(sol_in * 1e9), r_in_w, r_out_t, st["fee_ppm"])
        return {"pool": st["pool"], "tokens_out": out / 10 ** t_dec,
                "fee_ppm": st["fee_ppm"], "depth_sol": r_in_w / 1e9}
    out = cpmm_quote(tokens_in, r_out_t, r_in_w, st["fee_ppm"])
    return {"pool": st["pool"], "sol_out": out / 1e9,
            "fee_ppm": st["fee_ppm"], "depth_sol": r_in_w / 1e9}


if __name__ == "__main__":
    import sys
    mint = sys.argv[1] if len(sys.argv) > 1 else \
        "6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN"  # TRUMP (known CPMM)
    t0 = time.time()
    pools = find_pools(mint, use_cache=False)
    print("pools found:", len(pools), "(%.1fs)" % (time.time() - t0))
    q = quote_for_mint(mint, sol_in=0.05)
    print("0.05 SOL buy quote:", json.dumps(q, indent=1))
