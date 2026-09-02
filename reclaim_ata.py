#!/usr/bin/env python3
"""Reclaim rent locked in leftover SPL token accounts (§168).

Every trade creates an ATA (pump.fun graduates are Token-2022). After a
99.9% sell the ATA keeps dust + ~0.002 SOL of locked rent. This script:
  - zero-balance accounts  -> CloseAccount (refund rent)
  - dust accounts (<=0.2% of original buy) -> Burn dust + CloseAccount
  - LUTN (full unsold position from the failed drain exit) -> SKIPPED,
    flagged for owner decision.
Every tx is simulated first; kill switch respected; 1.6s RPC spacing.

Usage:
  python3 reclaim_ata.py          # scan + live reclaim
  python3 reclaim_ata.py --dry    # scan only, no transactions
"""
import json
import struct
import sys
import time
import importlib.util

spec = importlib.util.spec_from_file_location("lt", "live_trader.py")
lt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lt)

T22_S = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
T22_B = lt.b58dec(T22_S)
CLS_S = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
CLS_B = lt.b58dec(CLS_S)
IX_CLOSE = bytes([9])
IX_BURN = 8
BATCH = 8          # account pairs per tx
# §169 bug fix: "dust" must be RELATIVE to the booked position size.
# Absolute thresholds are meaningless across mints (a full live position
# can be 29M raw for one mint and 18.6B for another). BXiwv's OPEN
# position (1.72B raw) was burned as "dust" under the old absolute 5B
# cutoff — a ~0.127 SOL self-inflicted loss. Never again:
#   - any mint with an OPEN book position -> never touch
#   - any mint NOT in the book at all    -> never touch
#   - closable dust = raw <= 0.5% of booked tokens OR raw == 0
DUST_FRAC = 0.005


def scan(address):
    """Returns (closable, skipped, total_lamports) or None on RPC failure."""
    accounts = []
    for prog in (T22_S, CLS_S):
        r = lt._rpc("getTokenAccountsByOwner", [
            address, {"programId": prog}, {"encoding": "jsonParsed"}])
        time.sleep(1.6)
        if r is None or "value" not in (r or {}):
            return None
        for a in r["value"]:
            info = a["account"]["data"]["parsed"]["info"]
            accounts.append({
                "pubkey": a["pubkey"],
                "mint": info["mint"],
                "raw": int(info["tokenAmount"]["amount"]),
                "lamports": a["account"]["lamports"],
                "prog": prog,
            })
    closable, skipped = [], []
    book = json.load(open("live_positions.json"))
    open_mints = {m for m, p in book.items() if p.get("open")}
    for a in accounts:
        bk = book.get(a["mint"])
        if a["mint"] in open_mints:
            skipped.append((a, "OPEN POSITION — never touch"))
        elif bk is None:
            skipped.append((a, "not in book — unknown origin"))
        elif a["raw"] == 0 or a["raw"] <= max(1, int(bk.get("tokens", 0) * DUST_FRAC)):
            closable.append(a)
        else:
            skipped.append((a, f"raw {a['raw']:,} exceeds dust frac of booked {bk.get('tokens', 0):,}"))
    return closable, skipped, sum(a["lamports"] for a in closable)


def main():
    dry = "--dry" in sys.argv
    key, address = lt._load_key()
    payer_b = lt.b58dec(address)

    bal0 = lt.balance_sol(address)
    time.sleep(1.6)
    res = scan(address)
    if res is None:
        print("RPC scan failed — aborting (no transactions sent)")
        return
    closable, skipped, lamports = res
    print(f"wallet {address}")
    print(f"balance before: {bal0:.6f} SOL")
    print(f"closable accounts: {len(closable)} "
          f"({sum(1 for a in closable if a['raw']==0)} empty, "
          f"{sum(1 for a in closable if a['raw']>0)} dust) "
          f"— reclaimable rent: {lamports/1e9:.5f} SOL")
    for a, why_skip in skipped:
        print(f"SKIPPED: {a['mint'][:12]}… raw {a['raw']:,} — {why_skip}")
    if dry or not closable:
        print("dry-run / nothing to do — no transactions sent")
        return

    ok, why = lt.live_enabled()
    if not ok:
        print(f"live gate closed ({why}) — aborting reclaim")
        return

    sigs = []
    for i in range(0, len(closable), BATCH):
        batch = closable[i:i + BATCH]
        ixs = []
        for a in batch:
            prog_b = T22_B if a["prog"] == T22_S else CLS_B
            ata_b, mint_b = lt.b58dec(a["pubkey"]), lt.b58dec(a["mint"])
            if a["raw"] > 0:
                ixs.append((prog_b,
                            [(ata_b, True, False), (mint_b, True, False),
                             (payer_b, False, True)],
                            bytes([IX_BURN]) + struct.pack("<Q", a["raw"])))
            ixs.append((prog_b,
                        [(ata_b, True, False), (payer_b, True, False),
                         (payer_b, False, True)],
                        IX_CLOSE))
        tx_b64 = lt.build_legacy_tx(payer_b, ixs)
        time.sleep(1.6)
        sim = lt._rpc("simulateTransaction", [tx_b64, {"encoding": "base64"}])
        if not sim or sim.get("value", {}).get("err"):
            print(f"batch {i//BATCH}: SIMULATION FAILED {sim} — skipped")
            continue
        time.sleep(1.6)
        sig = lt._rpc("sendTransaction", [tx_b64, {"encoding": "base64"}])
        if not sig:
            print(f"batch {i//BATCH}: no signature — skipped")
            continue
        landed = lt._tx_success(sig)
        print(f"batch {i//BATCH}: {len(batch)} accounts, sig {sig[:20]}… landed={landed}")
        sigs.append(sig)
        time.sleep(1.6)

    time.sleep(2.0)
    bal1 = lt.balance_sol(address)
    print(f"\nbalance after: {bal1:.6f} SOL  (delta {bal1 - bal0:+.6f})")
    row = {"action": "ata_reclaim", "accounts": len(closable),
           "skipped": [a["mint"] for a, _ in skipped], "sigs": sigs,
           "bal_before": bal0, "bal_after": bal1,
           "delta": round(bal1 - bal0, 9), "ts": time.time()}
    with open("mfg_live_trades.jsonl", "a") as f:
        f.write(json.dumps(row) + "\n")
    print("logged to mfg_live_trades.jsonl")


if __name__ == "__main__":
    main()
