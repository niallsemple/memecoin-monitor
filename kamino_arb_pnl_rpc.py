#!/usr/bin/env python3
"""kamino_arb_pnl_rpc.py — exact arb P&L via RPC postTokenBalances - preTokenBalances
for the fee payer (owner-attributed, no transfer-attribution bias).
Prices: USDC/USDT=$1, wSOL=Binance daily close (cached). Residual mints -> complex.
Appends kamino_arb_pnl2.jsonl; checkpoint kamino_arb_pnl2_done.json.
"""
import json, time, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from kamino_tail import rpc  # helius RPC

MON = Path(__file__).resolve().parent
DS = MON / "kamino_arb_dataset.jsonl"
OUT = MON / "kamino_arb_pnl2.jsonl"
DONE = MON / "kamino_arb_pnl2_done.json"
SOLCACHE = MON / "sol_daily_px.json"

USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
WSOL = "So11111111111111111111111111111111111111112"
STABLES = {USDC, USDT}


def payer_deltas(tx, payer):
    """mint -> signed amount delta for token accounts owned by payer."""
    pre, post = {}, {}
    meta = tx.get("meta") or {}
    for b in meta.get("preTokenBalances") or []:
        if b.get("owner") == payer:
            pre[(b["accountIndex"], b["mint"])] = float(
                b["uiTokenAmount"].get("uiAmount") or 0)
    for b in meta.get("postTokenBalances") or []:
        if b.get("owner") == payer:
            post[(b["accountIndex"], b["mint"])] = float(
                b["uiTokenAmount"].get("uiAmount") or 0)
    by_mint = {}
    for k in set(pre) | set(post):
        d = post.get(k, 0) - pre.get(k, 0)
        if abs(d) > 1e-12:
            by_mint[k[1]] = by_mint.get(k[1], 0) + d
    # native SOL delta
    sol = 0.0
    msg = tx["transaction"]["message"]
    keys = [k["pubkey"] if isinstance(k, dict) else k for k in msg["accountKeys"]]
    if payer in keys:
        i = keys.index(payer)
        sol = (meta["postBalances"][i] - meta["preBalances"][i]
               - meta.get("fee", 0)) / 1e9  # fee already deducted; add back then subtract net
        sol = (meta["postBalances"][i] - meta["preBalances"][i]) / 1e9
    return by_mint, sol


def main():
    max_s = float(sys.argv[1]) if len(sys.argv) > 1 else 240
    t0 = time.time()
    done = set(json.load(open(DONE))) if DONE.exists() else set()
    px = json.load(open(SOLCACHE)) if SOLCACHE.exists() else {}
    rows = [json.loads(l) for l in open(DS)]
    n = 0
    f = open(OUT, "a")
    for r in rows:
        if time.time() - t0 > max_s:
            break
        sig = r["sig"]
        if sig in done:
            continue
        done.add(sig)
        try:
            tx = rpc("getTransaction", [sig, {"encoding": "jsonParsed",
                     "maxSupportedTransactionVersion": 0}]).get("result")
        except Exception:
            continue
        if not tx:
            continue
        payer = r["payer"]
        deltas, sol_net = payer_deltas(tx, payer)
        d = time.strftime("%Y-%m-%d", time.gmtime(r["ts"]))
        sol_px = px.get(d)
        pnl, complex_ = 0.0, False
        for m, amt in deltas.items():
            if m in STABLES:
                pnl += amt
            elif m == WSOL and sol_px:
                pnl += amt * sol_px
            else:
                complex_ = True
        if sol_px:
            pnl += sol_net * sol_px  # includes -fee
        f.write(json.dumps({"sig": sig, "ts": r["ts"], "payer": payer,
                            "pnl_usd": round(pnl, 5), "complex": complex_,
                            "sol_net": round(sol_net, 7),
                            "mints": len(deltas)}) + "\n")
        f.flush()
        n += 1
        time.sleep(0.1)
    f.close()
    json.dump(sorted(done), open(DONE, "w"))
    print(f"priced {n} (total {len(done)}/{len(rows)})")


if __name__ == "__main__":
    main()
