#!/usr/bin/env python3
"""forensic_overhang.py — §214: reconstruct entry-time insider
allocation for historical drains from chain data.

The §213 proxy failed because the pool ledger can't see curve buys.
This goes forensic: for each target mint, take the top never-pool-
bought sellers from the wallet ledger (the §189 killer fingerprint),
then parse each wallet's ATA transaction history for INBOUND token
transfers — the exact amounts they received without buying. Sum =
insider allocation the entry-time overhang screen would have seen.
Denominator: 1e15 raw (pump.fun 1B supply, 6 decimals).

Usage: python3 forensic_overhang.py <mint> [<mint>...]
"""
import json, sys, time, urllib.request
from collections import defaultdict
from pathlib import Path

MON = Path(__file__).resolve().parent
KEY = (MON / "helius_key.txt").read_text().strip()
RPC = f"https://mainnet.helius-rpc.com/?api-key={KEY}"
SUPPLY_RAW = 1e15
TOP_KILLERS = 6
MAX_SIGS_PER_ATA = 40


def rpc(method, params, tries=4):
    body = json.dumps({"jsonrpc": "2.0", "id": 1,
                       "method": method, "params": params}).encode()
    for a in range(tries):
        try:
            req = urllib.request.Request(
                RPC, data=body,
                headers={"Content-Type": "application/json"})
            return json.load(urllib.request.urlopen(req, timeout=30))
        except Exception:
            if a == tries - 1:
                raise
            time.sleep(1.7 * (a + 1))


def never_bought_sellers(mint):
    bought, sold = set(), defaultdict(float)
    for line in (MON / "mfg_wallet_trades.jsonl").open():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("mint") != mint:
            continue
        if r.get("side") == "buy":
            bought.add(r["wallet"])
        elif r.get("side") == "sell":
            sold[r["wallet"]] += r.get("sol", 0) or 0
    killers = [(w, s) for w, s in sold.items() if w not in bought]
    killers.sort(key=lambda kv: -kv[1])
    return killers


def received_raw(mint, owner):
    """Total raw tokens received by owner's ATA for mint (inbound only)."""
    tas = rpc("getTokenAccountsByOwner",
              [owner, {"mint": mint}, {"encoding": "jsonParsed"}])
    total = 0
    for ta in tas.get("result", {}).get("value", []):
        ata = ta["pubkey"]
        sigs = rpc("getSignaturesForAddress",
                   [ata, {"limit": MAX_SIGS_PER_ATA}]).get("result", [])
        time.sleep(1.7)
        for s in sigs:
            if s.get("err"):
                continue
            tx = rpc("getTransaction",
                     [s["signature"], {"encoding": "jsonParsed",
                                       "maxSupportedTransactionVersion": 0}]
                     ).get("result")
            time.sleep(1.7)
            if not tx:
                continue
            meta = tx.get("meta") or {}
            pre = {b["accountIndex"]: float(b["uiTokenAmount"]["amount"])
                   for b in meta.get("preTokenBalances", [])
                   if b.get("mint") == mint}
            for b in meta.get("postTokenBalances", []):
                if b.get("mint") != mint:
                    continue
                i = b["accountIndex"]
                d = float(b["uiTokenAmount"]["amount"]) - pre.get(i, 0.0)
                if d > 0:
                    # credit to an account owned by our target owner?
                    keys = tx["transaction"]["message"]["accountKeys"]
                    if i < len(keys):
                        k = keys[i]
                        pk = k if isinstance(k, str) else k["pubkey"]
                        if pk == ata:
                            total += d
    return total


def main():
    for mint in sys.argv[1:]:
        killers = never_bought_sellers(mint)[:TOP_KILLERS]
        print("=" * 66)
        print(f"{mint[:14]}  top never-bought sellers: {len(killers)}")
        tot = 0
        for w, sol in killers:
            try:
                raw = received_raw(mint, w)
            except Exception as e:
                print(f"  {w[:12]} sold {sol:8.2f} SOL  recv ERROR: {e}")
                continue
            tot += raw
            print(f"  {w[:12]} sold {sol:8.2f} SOL  "
                  f"received {raw/1e9:,.0f} tokens "
                  f"({100*raw/SUPPLY_RAW:.2f}% of supply)")
        print(f"  => reconstructed insider allocation (top {len(killers)}): "
              f"{100*tot/SUPPLY_RAW:.2f}% of supply")


if __name__ == "__main__":
    main()
