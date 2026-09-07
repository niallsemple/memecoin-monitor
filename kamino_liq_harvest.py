#!/usr/bin/env python3
"""kamino_liq_harvest.py — Phase 1: historical Kamino liquidation dataset.

Walks Helius enhanced-transaction history for the KLend program backward,
keeps txs containing a liquidate_obligation instruction, and records:
  sig, slot, ts, fee_payer (= liquidator candidate), obligation,
  tokenTransfers (in/out per party), nativeTransfers, fee, success.

Output: kamino_liq_dataset.jsonl (append, dedup by sig on reruns).
Checkpoint: kamino_liq_harvest_state.json (oldest sig processed).

Usage: python3 kamino_liq_harvest.py [max_seconds] [target_count]
"""
import json, time, sys, hashlib
from pathlib import Path
import urllib.request

MON = Path(__file__).resolve().parent
KEY = (MON / "helius_key.txt").read_text().strip()
API = f"https://api.helius.xyz/v0/addresses"
KLEND = "KLend2g3cP87fffoy8q1mQqGKjrxjC8boSyAYavgmjD"
OUT = MON / "kamino_liq_dataset.jsonl"
STATE = MON / "kamino_liq_harvest_state.json"

ALPH = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
# proven in §460/§461 sims: LiquidateObligationAndRedeemReserveCollateral (V1 flat)
LIQ_DISC = bytes([177, 71, 154, 188, 226, 133, 74, 55])

def b58encode(b: bytes) -> str:
    n = int.from_bytes(b, "big"); s = ""
    while n:
        n, r = divmod(n, 58); s = ALPH[r] + s
    return "1" * (len(b) - len(b.lstrip(b"\0"))) + (s or "")

def b58decode(s: str) -> bytes:
    n = 0
    for c in s:
        n = n * 58 + ALPH.index(c)
    b = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\0" * (len(s) - len(s.lstrip("1"))) + b

def fetch_page(before=None, limit=100):
    url = f"{API}/{KLEND}/transactions?api-key={KEY}&limit={limit}"
    if before:
        url += f"&before={before}"
    req = urllib.request.Request(url, headers={"User-Agent": "darwin-labs/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def tx_has_liquidate(tx):
    """Detector: Helius semantic type LIQUIDATE, else raw-disc scan of outer ixs
    (this endpoint omits innerInstructions, so the type label is primary)."""
    if tx.get("type") == "LIQUIDATE":
        ob = liq = None
        for ix in tx.get("instructions", []):
            if ix.get("programId") == KLEND and ix.get("accounts"):
                accts = ix["accounts"]
                if len(accts) > 1:
                    liq, ob = accts[0], accts[1]
        return {"obligation": ob, "liquidator_ix": liq}
    for ix in tx.get("instructions", []):
        if ix.get("programId") != KLEND:
            continue
        data = ix.get("data")
        if not data:
            continue
        try:
            raw = b58decode(data)
        except Exception:
            continue
        if raw[:8] == LIQ_DISC:
            accts = ix.get("accounts", [])
            return {"obligation": accts[1] if len(accts) > 1 else None,
                    "liquidator_ix": accts[0] if accts else None}
    return None

def main():
    max_s = float(sys.argv[1]) if len(sys.argv) > 1 else 240
    target = int(sys.argv[2]) if len(sys.argv) > 2 else 500
    t0 = time.time()
    seen = set()
    if OUT.exists():
        for l in open(OUT):
            try:
                seen.add(json.loads(l)["sig"])
            except Exception:
                pass
    before = None
    if STATE.exists():
        before = json.load(open(STATE)).get("oldest_sig")
    n_new = n_scan = n_arb = 0
    f = open(OUT, "a")
    arb_f = open(MON / "kamino_arb_dataset.jsonl", "a")
    while time.time() - t0 < max_s and n_new < target:
        try:
            page = fetch_page(before)
        except Exception as e:
            print("fetch error:", str(e)[:120]); break
        if not page:
            print("history exhausted"); break
        for tx in page:
            n_scan += 1
            sig = tx.get("signature")
            if sig in seen or tx.get("transactionError"):
                continue
            hit = tx_has_liquidate(tx)
            if hit:
                rec = {
                    "sig": sig, "slot": tx.get("slot"), "ts": tx.get("timestamp"),
                    "fee_payer": tx.get("feePayer"),
                    "liquidator_ix": hit["liquidator_ix"],
                    "obligation": hit["obligation"],
                    "fee_lamports": tx.get("fee"),
                    "token_transfers": [
                        {"mint": t.get("mint"), "from": t.get("fromUserAccount"),
                         "to": t.get("toUserAccount"),
                         "amount": t.get("tokenAmount")}
                        for t in tx.get("tokenTransfers", [])],
                    "native_transfers": [
                        {"from": t.get("fromUserAccount"), "to": t.get("toUserAccount"),
                         "amount": t.get("amount")}
                        for t in tx.get("nativeTransfers", [])],
                }
                f.write(json.dumps(rec) + "\n")
                seen.add(sig)
                n_new += 1
            elif tx.get("type") == "FLASH_REPAY_RESERVE_LIQUIDITY" and arb_f:
                # arb/unknown-flash population: net flow per mint to fee payer
                payer = tx.get("feePayer")
                net = {}
                for t in tx.get("tokenTransfers", []):
                    m = t.get("mint")
                    if not m:
                        continue
                    amt = t.get("tokenAmount") or 0
                    if t.get("toUserAccount") == payer:
                        net[m] = net.get(m, 0) + amt
                    if t.get("fromUserAccount") == payer:
                        net[m] = net.get(m, 0) - amt
                sol_net = sum(t.get("amount", 0) for t in tx.get("nativeTransfers", [])
                              if t.get("toUserAccount") == payer) \
                        - sum(t.get("amount", 0) for t in tx.get("nativeTransfers", [])
                              if t.get("fromUserAccount") == payer)
                arb_f.write(json.dumps({
                    "sig": sig, "slot": tx.get("slot"), "ts": tx.get("timestamp"),
                    "payer": payer, "fee_lamports": tx.get("fee"),
                    "net_by_mint": net, "sol_net_lamports": sol_net,
                    "n_transfers": len(tx.get("tokenTransfers", []))}) + "\n")
                n_arb += 1
        before = page[-1].get("signature")
        f.flush()
        if arb_f:
            arb_f.flush()
        print(f"scanned {n_scan}, liquidations {n_new}, arb/flash {n_arb}, "
              f"oldest ts {page[-1].get('timestamp')} ({time.time()-t0:.0f}s)")
        time.sleep(0.05)
    f.close()
    if arb_f:
        arb_f.close()
    json.dump({"oldest_sig": before, "ts": time.time()}, open(STATE, "w"))
    print(f"DONE: {n_new} new liquidations from {n_scan} KLend txs "
          f"(dataset total {len(seen)})")

if __name__ == "__main__":
    main()
