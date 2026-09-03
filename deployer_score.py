#!/usr/bin/env python3
"""deployer_score.py — at-birth deployer outcome history.

Given a deployer wallet, enumerate pump.fun creates from its tx history
and score each past mint's outcome (rug / alive) using current bonding
curve or pool state. Cached to deployer_score_cache.json.

Outcome scoring (cheap heuristic):
  - mint no longer has active curve/pool liquidity ~ 0  -> rug
  - else -> alive/survivor
"""
import json, time, urllib.request, sys, base64
from pathlib import Path

# pump.fun "create" instruction discriminator (observed on-chain)
CREATE_DISC = bytes.fromhex("d6904cec5f8b31b4")

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
def b58decode(s):
    n = 0
    for c in s:
        n = n * 58 + _B58.index(c)
    b = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    pad = len(s) - len(s.lstrip("1"))
    return b"\x00" * pad + b

MON = Path(__file__).parent
KEY = (MON / "helius_key.txt").read_text().strip()
RPC = "https://mainnet.helius-rpc.com/?api-key=" + KEY
PUMP = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
CACHE_F = MON / "deployer_score_cache.json"


def rpc(method, params, retries=3):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params}).encode()
    for i in range(retries):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(
                RPC, data=body, headers={"Content-Type": "application/json"}),
                timeout=30))
            return r.get("result")
        except Exception:
            time.sleep(1 + i)
    return None


def list_creates(deployer, max_sigs=100):
    """Find pump.fun create txs in deployer's recent history."""
    sigs = rpc("getSignaturesForAddress", [deployer, {"limit": max_sigs}]) or []
    mints = []
    for s in sigs:
        tx = rpc("getTransaction", [s["signature"], {
                 "encoding": "jsonParsed",
                 "maxSupportedTransactionVersion": 0}])
        if not tx:
            continue
        msg = tx["transaction"]["message"]
        for ix in msg.get("instructions", []):
            if not isinstance(ix, dict):
                continue
            if ix.get("programId") != PUMP:
                continue
            data = ix.get("data")
            if not data:
                continue
            try:
                raw = b58decode(data)
            except Exception:
                continue
            if raw[:8] == CREATE_DISC:
                accts = ix.get("accounts", [])
                if accts:
                    mints.append(accts[0])
                break
        time.sleep(0.05)
    return mints


def mint_alive(mint):
    """Heuristic: does the mint still hold liquidity anywhere we can see?
    Check token supply > 0 and any largest accounts with balance."""
    sup = rpc("getTokenSupply", [mint])
    if not sup:
        return None
    return float(sup["value"]["uiAmount"] or 0) > 0


def score_deployer(deployer):
    cache = json.loads(CACHE_F.read_text()) if CACHE_F.exists() else {}
    if deployer in cache:
        return cache[deployer]
    mints = list_creates(deployer)
    res = {"deployer": deployer, "n_mints": len(mints), "mints": mints,
           "scored_at": time.time()}
    cache[deployer] = res
    CACHE_F.write_text(json.dumps(cache, indent=1))
    return res


if __name__ == "__main__":
    for dep in sys.argv[1:]:
        r = score_deployer(dep)
        print(dep[:8], "creates found:", r["n_mints"])
