#!/usr/bin/env python3
"""Insider-overhang screen (§190, EDGE: drain precursors).

Killer fingerprint from §189: a wallet holding a large token balance
that NEVER bought through the pool dumps it all in one transaction.
Those holders are visible before they act: getTokenLargestAccounts.

For a mint: fetch top-20 token accounts, resolve owners, exclude the
pool's own base token account, cross-reference owners against the
wallet-ledger buyer set (pool buyers). Whales with big supply share
and no pool-buy history = insider overhang.

overhang% = supply share held by non-buyer whales (top-20 coverage).

Usage: python3 insider_screen.py <mint> [mint...]
"""
import json
import sys
import time
import base64
import urllib.request
from pathlib import Path

MON = Path(__file__).resolve().parent
RPCS = ["https://mainnet.helius-rpc.com/?api-key="
        + (MON / "helius_key.txt").read_text().strip(),
        "https://api.mainnet-beta.solana.com"]
POOLS = json.loads((MON / "mint_pools.json").read_text()) if (MON / "mint_pools.json").exists() else {}
LEDGER = MON / "mfg_wallet_trades.jsonl"


def rpc(method, params, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(
                RPCS[0],
                data=json.dumps({"jsonrpc": "2.0", "id": 1,
                                 "method": method, "params": params}).encode(),
                headers={"Content-Type": "application/json"})
            return json.load(urllib.request.urlopen(req, timeout=25))
        except Exception:
            time.sleep(1.7 * (i + 1))
    return {}


def ledger_buyers(mint):
    buyers = set()
    if not LEDGER.exists():
        return buyers
    for line in LEDGER.open():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["mint"] == mint and r["side"] == "buy":
            buyers.add(r["wallet"])
    return buyers


def screen(mint):
    supply_r = rpc("getTokenSupply", [mint])
    supply = float(supply_r.get("result", {}).get("value", {}).get("amount", 0))
    if not supply:
        return {"mint": mint, "error": "no supply"}
    la = rpc("getTokenLargestAccounts", [mint])
    accts = la.get("result", {}).get("value", [])
    if not accts:
        return {"mint": mint, "error": "no largest accounts"}
    addrs = [a["address"] for a in accts]
    time.sleep(1.7)
    owners_r = rpc("getMultipleAccounts", [addrs, {"encoding": "base64"}])
    owners = {}
    for addr, acc in zip(addrs, owners_r.get("result", {}).get("value", [])):
        if acc and acc.get("data"):
            raw = base64.b64decode(acc["data"][0])
            # SPL token account: owner pubkey at bytes 32..64
            import hashlib  # noqa - base58 below without lib
            owners[addr] = b58encode(raw[32:64])
    buyers = ledger_buyers(mint)
    pool = POOLS.get(mint)
    rows = []
    overhang = 0.0
    for a in accts:
        amt = float(a["amount"])
        share = amt / supply
        owner = owners.get(a["address"], "?")
        is_pool = (a["address"] == pool) or (owner == pool)
        is_buyer = owner in buyers
        insider = (not is_pool) and (not is_buyer) and share >= 0.005
        if insider:
            overhang += share
        rows.append({"share": round(share * 100, 2), "owner": owner[:10],
                     "pool": is_pool, "buyer": is_buyer, "insider": insider})
    return {"mint": mint, "supply": supply, "overhang_pct": round(overhang * 100, 2),
            "insiders": [r for r in rows if r["insider"]], "top": rows[:6]}


_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def b58encode(b):
    n = int.from_bytes(b, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = _B58[r] + out
    pad = 0
    for c in b:
        if c == 0:
            pad += 1
        else:
            break
    return "1" * pad + (out or "")


if __name__ == "__main__":
    for mint in sys.argv[1:]:
        s = screen(mint)
        if "error" in s:
            print(f"{mint[:8]}… ERROR {s['error']}")
            continue
        print(f"{mint[:8]}… overhang={s['overhang_pct']}%  insiders={len(s['insiders'])}")
        for r in s["top"]:
            tag = "POOL" if r["pool"] else ("buyer" if r["buyer"] else "INSIDER" if r["insider"] else "nonbuyer")
            print(f"    {r['share']:>6}%  {r['owner']}…  {tag}")
        time.sleep(1.7)
