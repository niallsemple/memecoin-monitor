"""arb_scanner.py — Phase 2: PumpSwap vs Raydium CPMM gap logger. READ-ONLY.

For recently-graduated tokens that exist on BOTH venues, compute the
executable round trip in both directions at a fixed size, net of ALL fees:
  dir A: buy on PumpSwap -> sell on Raydium
  dir B: buy on Raydium -> sell on PumpSwap
Fees: PumpSwap 0.25% (2500ppm), Raydium per-pool trade_fee_rate (from
AmmConfig, verified @12). Plus a fixed priority-fee allowance.
Gaps above GAP_MIN are appended to arb_candidates.jsonl.

Same shadow discipline as H16: LOG ONLY. Execution requires owner
promotion after a week of evidence.
"""
import json
import time
from pathlib import Path

import raydium_cpmm as rc
import raydium_v4 as rv4

MON = Path(__file__).resolve().parent
LOG = MON / "arb_candidates.jsonl"
CURVES = MON / "curves.jsonl"

AMM_PROG = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
PS_FEE_PPM = 2500          # PumpSwap total fee (LP + protocol)
PRIOR_SOL = 0.0002         # priority fee allowance per round trip
TRADE_SOL = 0.05           # reference size
GAP_MIN = 0.005            # log when net gap > 0.5%
MAX_MINTS = 12             # RPC budget per pass
MIN_DEPTH_SOL = 5.0        # §403: ignore dust/clone pools below this

# PumpSwap Pool layout (Anchor): disc 0-8, bump @8, index @9-11,
# creator @11-43, base_mint @43-75, quote_mint @75-107, lp_mint @107-139,
# pool_base_token_account @139-171, pool_quote_token_account @171-203.


def _recent_migrations(hours=168, cap=MAX_MINTS):
    """Graduated mints from curves.jsonl (tail scan). Default 7d: fresh
    grads are PumpSwap-only — Raydium CPMM pools appear later on the
    survivors, so the dual-listed universe needs a longer window."""
    out = []
    cutoff = time.time() - hours * 3600
    try:
        lines = CURVES.read_bytes().splitlines()[-20000:]
    except Exception:
        return out
    for l in reversed(lines):
        try:
            r = json.loads(l)
        except Exception:
            continue
        if r.get("txType") == "migrate" and r.get("_ts", 0) > cutoff:
            m = r.get("mint")
            if m and m not in out:
                out.append(m)
                if len(out) >= cap:
                    break
    return out


def _pumpswap_pool(mint):
    """Pool pubkey via gPA memcmp on base_mint @43, then vault addrs."""
    r = rc.rpc("getProgramAccounts", [AMM_PROG, {
        "encoding": "base64",
        "filters": [{"memcmp": {"offset": 43, "bytes": mint}}],
        "dataSlice": {"offset": 0, "length": 203}}]) or []
    if not r:
        return None
    import base64
    d = base64.b64decode(r[0]["account"]["data"][0])
    if len(d) < 203:
        return None
    return {"pool": r[0]["pubkey"],
            "base_vault": rc.b58encode(d[139:171]),
            "quote_vault": rc.b58encode(d[171:203])}


def _vault_bal(addr):
    v = (rc.rpc("getTokenAccountBalance", [addr]) or {}).get("value")
    return (int(v["amount"]), int(v["decimals"])) if v else (None, None)


def _cp_out(amount_in, reserve_in, reserve_out, fee_ppm):
    eff = amount_in * (1_000_000 - fee_ppm)
    return (eff * reserve_out) / (reserve_in * 1_000_000 + eff)


def check_mint(mint):
    """Both-venue round trips at TRADE_SOL. Returns dict or None."""
    ps = _pumpswap_pool(mint)
    if not ps:
        return None
    ray = None
    for p in rc.find_pools(mint):
        if rc.WSOL in (p["token_0_mint"], p["token_1_mint"]):
            st = rc.pool_state(p)
            if st:
                ray = st
                break
    if not ray:
        # §403: older pump.fun grads live on Raydium AMM v4, not CPMM.
        # Normalize v4 pool state to the CPMM-shaped dict below.
        for p in rv4.find_pools(mint):
            if rc.WSOL in (p["base_mint"], p["quote_mint"]):
                st = rv4.pool_state(p)
                if st:
                    ray = {"reserve0": st["reserve0"],
                           "reserve1": st["reserve1"],
                           "fee_ppm": st["fee_ppm"],
                           "token_0_mint": st["base_mint"],
                           "token_1_mint": st["quote_mint"],
                           "venue": "raydium_v4"}
                    break
    if not ray:
        return None
    base_raw, base_dec = _vault_bal(ps["base_vault"])
    quote_raw, _ = _vault_bal(ps["quote_vault"])  # quote = WSOL (9 dec)
    if not base_raw or not quote_raw:
        return None
    # §403 dust filter: clone/scam pools with ~0 depth create phantom
    # 3000% "gaps". Both venues need MIN_DEPTH_SOL real liquidity.
    wsol0r = ray["token_0_mint"] == rc.WSOL
    ray_depth = (ray["reserve0"] if wsol0r else ray["reserve1"]) / 1e9
    if ray_depth < MIN_DEPTH_SOL or quote_raw / 1e9 < MIN_DEPTH_SOL:
        return None
    lamports = int(TRADE_SOL * 1e9)
    # PumpSwap: base = token, quote = WSOL
    ps_buy_tok = _cp_out(lamports, quote_raw, base_raw, PS_FEE_PPM)
    # Raydium orientation
    wsol0 = ray["token_0_mint"] == rc.WSOL
    r_wsol = ray["reserve0"] if wsol0 else ray["reserve1"]
    r_tok = ray["reserve1"] if wsol0 else ray["reserve0"]
    r_fee = ray["fee_ppm"]
    # dir A: buy PS -> sell Raydium
    a_sell_sol = _cp_out(ps_buy_tok, r_tok, r_wsol, r_fee) / 1e9
    net_a = a_sell_sol - TRADE_SOL - PRIOR_SOL
    # dir B: buy Raydium -> sell PS
    b_buy_tok = _cp_out(lamports, r_wsol, r_tok, r_fee)
    b_sell_sol = _cp_out(b_buy_tok, base_raw, quote_raw, PS_FEE_PPM) / 1e9
    net_b = b_sell_sol - TRADE_SOL - PRIOR_SOL
    return {"mint": mint, "t": time.time(),
            "ps_depth_sol": round(quote_raw / 1e9, 3),
            "ray_depth_sol": round(r_wsol / 1e9, 3),
            "net_A_ps_to_ray": round(net_a, 5),
            "net_B_ray_to_ps": round(net_b, 5),
            "gap_pct_A": round(net_a / TRADE_SOL * 100, 2),
            "gap_pct_B": round(net_b / TRADE_SOL * 100, 2)}


def run_pass():
    """Scan recent migrations; log gaps above GAP_MIN. Returns stats."""
    mints = _recent_migrations()
    both, logged = 0, 0
    for mint in mints:
        try:
            res = check_mint(mint)
        except Exception:
            continue
        if not res:
            continue
        both += 1
        if max(res["gap_pct_A"], res["gap_pct_B"]) >= GAP_MIN * 100:
            res["action"] = "arb_candidate"
            with LOG.open("a") as f:
                f.write(json.dumps(res) + "\n")
            logged += 1
    return {"scanned": len(mints), "both_venues": both, "logged": logged}


def established_pass():
    """§403: CPMM-vs-v4 gaps on tokens dual-listed across Raydium venues
    (universe = intersection of the two discovery caches). Depth-filtered.
    Log-only, same discipline as the PumpSwap track."""
    if not rc.CACHE_F.exists() or not rv4.CACHE_F.exists():
        return {"dual": 0, "logged": 0}
    cpmm_c = json.loads(rc.CACHE_F.read_text())
    v4_c = json.loads(rv4.CACHE_F.read_text())
    dual = [m for m in cpmm_c if m in v4_c and cpmm_c[m] and v4_c[m]]
    logged = 0
    for mint in dual:
        try:
            qc = rc.quote_for_mint(mint, sol_in=TRADE_SOL)
            qv = rv4.quote_for_mint(mint, sol_in=TRADE_SOL)
            if not qc or not qv:
                continue
            if qc["depth_sol"] < MIN_DEPTH_SOL or \
                    qv["depth_sol"] < MIN_DEPTH_SOL:
                continue
            g = (max(qc["tokens_out"], qv["tokens_out"]) /
                 min(qc["tokens_out"], qv["tokens_out"]) - 1)
            net = g - (qc["fee_ppm"] + qv["fee_ppm"]) / 1e6 \
                - PRIOR_SOL / TRADE_SOL
            if net >= GAP_MIN:
                with LOG.open("a") as f:
                    f.write(json.dumps({
                        "action": "arb_candidate", "kind": "cpmm_vs_v4",
                        "mint": mint, "t": time.time(),
                        "cpmm_out": qc["tokens_out"], "v4_out": qv["tokens_out"],
                        "gap_pct": round(g * 100, 2),
                        "net_pct": round(net * 100, 2)}) + "\n")
                logged += 1
        except Exception:
            continue
    return {"dual": len(dual), "logged": logged}


if __name__ == "__main__":
    print("pumpswap track:", json.dumps(run_pass()))
    print("established track:", json.dumps(established_pass()))
