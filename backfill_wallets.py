#!/usr/bin/env python3
"""Backfill wallet-ledger history for closed live positions (§187).

Pages Helius parsed txs backward per pool until older than the
position's entry time (minus margin). Dedupes by signature so it is
safe to re-run. Uses the main watermark file only for mints it fully
completes (sets watermark to newest sig seen).

Usage: python3 backfill_wallets.py [batch_size] [max_pages]
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

MON = Path(__file__).resolve().parent
KEY = (MON / "helius_key.txt").read_text().strip()
API = "https://api.helius.xyz/v0/addresses/{addr}/transactions?api-key=" + KEY
LEDGER = MON / "mfg_wallet_trades.jsonl"
WATER = MON / "mfg_wallet_watermarks.json"
WSOL = "So11111111111111111111111111111111111111112"
MIN_SOL = 1e-6


def parse_tx(tx, mint, pool_addr):
    wallet = tx.get("feePayer")
    ts = tx.get("timestamp")
    sig = tx.get("signature")
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
            if frm == pool_addr and to == wallet:
                tok_buy = True
            elif to == pool_addr and frm == wallet:
                tok_sell = True
    side = sol = None
    if tok_buy and sol_buy > MIN_SOL:
        side, sol = "buy", sol_buy
    elif tok_sell and sol_sell > MIN_SOL:
        side, sol = "sell", sol_sell
    elif alt_dir and alt_sol > MIN_SOL:
        side, sol = alt_dir, alt_sol
        wallet = alt_wallet or wallet
    if side and wallet:
        return {"t": ts, "mint": mint, "wallet": wallet,
                "side": side, "sol": round(sol, 9), "sig": sig}
    return None


def fetch_page(pool_addr, before=None):
    url = API.format(addr=pool_addr) + (f"&before={before}" if before else "")
    req = urllib.request.Request(url, headers={"User-Agent": "mfg/1.0"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read())


def backfill(mint, pool_addr, floor_ts, known_sigs, max_pages):
    rows, newest = [], None
    before = None
    for _ in range(max_pages):
        try:
            txs = fetch_page(pool_addr, before)
        except Exception:
            break
        if not txs:
            break
        oldest_ts = None
        for tx in txs:
            sig = tx.get("signature")
            if newest is None:
                newest = sig
            oldest_ts = tx.get("timestamp")
            if sig in known_sigs:
                continue
            r = parse_tx(tx, mint, pool_addr)
            if r:
                rows.append(r)
                known_sigs.add(sig)
            before = sig
        if oldest_ts and oldest_ts < floor_ts:
            break
        if len(txs) < 100:
            break
        time.sleep(0.15)
    return rows, newest


def main():
    batch = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    pools = json.loads((MON / "mint_pools.json").read_text())
    pos = json.loads((MON / "live_positions.json").read_text())
    done_file = MON / "backfill_done.json"
    done = json.loads(done_file.read_text()) if done_file.exists() else []
    known_sigs = set()
    if LEDGER.exists():
        for line in LEDGER.open():
            if line.strip():
                known_sigs.add(json.loads(line)["sig"])
    todo = [m for m in pools
            if pools[m] and m not in done and m in pos][:batch]
    print(f"backfilling {len(todo)} mints (batch={batch}, pages={max_pages})")
    wm = json.loads(WATER.read_text()) if WATER.exists() else {}
    for m in todo:
        t0 = time.time()
        floor = pos[m]["entry_t"] - 600
        rows, newest = backfill(m, pools[m], floor, known_sigs, max_pages)
        if rows:
            with LEDGER.open("a") as f:
                for r in sorted(rows, key=lambda r: r["t"] or 0):
                    f.write(json.dumps(r) + "\n")
        if newest and pools[m] not in wm:
            wm[pools[m]] = newest
            WATER.write_text(json.dumps(wm))
        done.append(m)
        done_file.write_text(json.dumps(done))
        print(f"  {m[:8]}… +{len(rows)} rows ({time.time()-t0:.0f}s)")
    print(f"done={len(done)}/36, ledger sigs={len(known_sigs)}")


if __name__ == "__main__":
    main()
