#!/usr/bin/env python3
"""Wallet-attributed trade ledger for qualified tokens (§181, EDGE #6).

The main tape (mfg_trades.jsonl) is balance-delta derived — no wallets.
This module pulls Helius PARSED transactions for a token's PumpSwap pool
address and extracts per-trade: timestamp, wallet (feePayer), side, SOL.

Forward-only, watermarked per pool — each call fetches only new txs.
Scope: gate-qualified mints only (s60nm5fr opens), not the whole chain.

Standalone test:
  python3 wallet_ledger.py <mint> <pool_addr>
"""
import json
import time
import urllib.request
from pathlib import Path

MON = Path(__file__).resolve().parent
KEY = (MON / "helius_key.txt").read_text().strip()
API = "https://api.helius.xyz/v0/addresses/{addr}/transactions?api-key=" + KEY
LEDGER = MON / "mfg_wallet_trades.jsonl"
WATER = MON / "mfg_wallet_watermarks.json"
WSOL = "So11111111111111111111111111111111111111112"


def _watermarks():
    if WATER.exists():
        try:
            return json.loads(WATER.read_text())
        except Exception:
            pass
    return {}


RPC_URL = f"https://mainnet.helius-rpc.com/?api-key={KEY}"


def _rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1,
                       "method": method, "params": params}).encode()
    req = urllib.request.Request(RPC_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read()) \
        .get("result")


def _parse_rpc_tx(tx, mint):
    """jsonParsed getTransaction → ledger row (§225 RPC fallback).

    Helius parsed API went 403 mid-shift 2026-09-02; RPC jsonParsed has no
    tokenTransfers convenience view, so derive: side from the fee payer's
    token-delta sign on `mint`; size from their native SOL delta + fee
    (Jupiter unwraps WSOL to native on sells; buys wrap native in)."""
    meta = tx.get("meta") or {}
    if meta.get("err"):
        return None
    msg = tx["transaction"]["message"]
    keys = [k["pubkey"] if isinstance(k, dict) else k
            for k in msg["accountKeys"]]
    wallet = keys[0]
    pre = post = 0
    for b in meta.get("preTokenBalances") or []:
        if b.get("mint") == mint and b.get("owner") == wallet:
            pre += int(b["uiTokenAmount"]["amount"])
    for b in meta.get("postTokenBalances") or []:
        if b.get("mint") == mint and b.get("owner") == wallet:
            post += int(b["uiTokenAmount"]["amount"])
    d_tok = post - pre
    if d_tok == 0:
        return None
    i = keys.index(wallet)
    d_sol = (meta["postBalances"][i] - meta["preBalances"][i]
             + meta.get("fee", 0)) / 1e9
    if d_tok > 0:
        side, sol = "buy", -d_sol       # spent SOL
    else:
        side, sol = "sell", d_sol       # received SOL
    if sol <= 1e-6:
        return None
    return {"t": tx.get("blockTime"), "mint": mint, "wallet": wallet,
            "side": side, "sol": round(sol, 9),
            "sig": tx["transaction"]["signatures"][0]}


def fetch_new_rpc(pool_addr, mint, max_sigs=400):
    """RPC fallback for fetch_new: sigs until watermark, parse each."""
    wm = _watermarks()
    seen_before = wm.get(pool_addr)
    params = [pool_addr, {"limit": 100}]
    if seen_before:
        params[1]["until"] = seen_before
    sigs, newest = [], None
    while len(sigs) < max_sigs:
        try:
            r = _rpc("getSignaturesForAddress", params)
        except Exception:
            break
        if not r:
            break
        if newest is None:
            newest = r[0]["signature"]
        sigs += [s["signature"] for s in r]
        if len(r) < 100:
            break
        params[1]["before"] = r[-1]["signature"]
        time.sleep(0.4)
    rows = []
    for sig in sigs[:max_sigs]:
        try:
            tx = _rpc("getTransaction",
                      [sig, {"encoding": "jsonParsed",
                             "maxSupportedTransactionVersion": 0}])
        except Exception:
            continue
        if tx:
            row = _parse_rpc_tx(tx, mint)
            if row:
                rows.append(row)
        time.sleep(0.15)
    return rows, newest


def fetch_new(pool_addr, mint, max_pages=20):
    """Fetch parsed txs newer than the watermark. Returns (rows, newest_sig)."""
    wm = _watermarks()
    seen_before = wm.get(pool_addr)          # sig of newest tx already stored
    rows, newest = [], None
    before = None
    for _ in range(max_pages):
        url = API.format(addr=pool_addr) + (f"&before={before}" if before else "")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "mfg/1.0"})
            txs = json.loads(urllib.request.urlopen(req, timeout=20).read())
        except Exception:
            # §225: parsed API 403s since 2026-09-02 — fall back to the
            # RPC path (sigs until watermark + jsonParsed owner deltas).
            if before is None:
                return fetch_new_rpc(pool_addr, mint)
            break
        if not txs:
            break
        done = False
        for tx in txs:
            sig = tx.get("signature")
            if newest is None:
                newest = sig
            if sig == seen_before:
                done = True
                break
            wallet = tx.get("feePayer")
            ts = tx.get("timestamp")
            # PumpSwap WSOL leg rides as tokenTransfers (mint=WSOL).
            # Direct swaps: WSOL/token move between feePayer and pool.
            # Aggregator routes: token counterparty is an intermediate
            # owner — fall back to the token leg's non-pool side as the
            # wallet and the largest pool-side WSOL transfer as size.
            sol_buy = sol_sell = 0.0
            tok_buy = tok_sell = False
            alt_wallet, alt_sol, alt_dir = None, 0.0, None
            for tt in tx.get("tokenTransfers") or []:
                frm, to = tt.get("fromUserAccount"), tt.get("toUserAccount")
                amt = tt.get("tokenAmount") or 0
                if tt.get("mint") == WSOL:
                    if to == pool_addr:
                        if frm == wallet:
                            sol_buy += amt
                        if amt > alt_sol:
                            alt_sol, alt_dir, alt_wallet = amt, "buy", frm
                    elif frm == pool_addr:
                        if to == wallet:
                            sol_sell += amt
                        if amt > alt_sol:
                            alt_sol, alt_dir, alt_wallet = amt, "sell", to
                elif tt.get("mint") == mint:
                    if frm == pool_addr:
                        if to == wallet:
                            tok_buy = True
                        elif alt_wallet is None or to != alt_wallet:
                            pass
                        if to != wallet and alt_dir == "buy":
                            alt_wallet = alt_wallet or to
                    elif to == pool_addr:
                        if frm == wallet:
                            tok_sell = True
            side = None
            sol = 0.0
            MIN_SOL = 1e-6
            if tok_buy and sol_buy > MIN_SOL:
                side, sol = "buy", sol_buy
            elif tok_sell and sol_sell > MIN_SOL:
                side, sol = "sell", sol_sell
            elif alt_dir and alt_sol > MIN_SOL:
                # aggregator-shaped swap: token moved pool<->someone
                side, sol = alt_dir, alt_sol
                wallet = alt_wallet or wallet
            if side and wallet:
                rows.append({"t": ts, "mint": mint, "wallet": wallet,
                             "side": side, "sol": round(sol, 9),
                             "sig": sig})
            before = sig
        if done or len(txs) < 100:
            break
        time.sleep(0.4)
    return rows, newest


def update(mint, pool_addr):
    """Watermark-aware ledger append. Returns number of new rows."""
    rows, newest = fetch_new(pool_addr, mint)
    if newest:
        wm = _watermarks()
        wm[pool_addr] = newest
        WATER.write_text(json.dumps(wm))
    if rows:
        with LEDGER.open("a") as f:
            for r in reversed(rows):       # oldest first
                f.write(json.dumps(r) + "\n")
    return len(rows)


if __name__ == "__main__":
    import sys
    mint, pool = sys.argv[1], sys.argv[2]
    n = update(mint, pool)
    print(f"{n} new wallet-attributed trades for {mint[:8]}…")
    if LEDGER.exists():
        lines = LEDGER.read_text().strip().split("\n")
        print(f"ledger total: {len(lines)} rows")
        for l in lines[-3:]:
            print(" ", l[:160])
