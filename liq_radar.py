#!/usr/bin/env python3
"""
DARWIN liquidation radar — Tier 1 shortlist scanner (paper/recon only).

Per §341/§342: marginfi v2 has ~165k MarginfiAccounts; full health decode on
all of them per pass is wasteful. Tier 1 fetches only the balance region
(offset 72, 16 slots x 104 bytes) sharded 16 ways by authority-pubkey first
nibble, and shortlists accounts carrying ANY active liability (borrow).

Tier 2 (not built yet) will compute health for the shortlist using Bank
configs + oracle prices.

Layout (§342, empirically verified):
  slot i at offset 72 + i*104 (relative to account data start)
  active: slot+0 (u8) | bank_pk: slot+1..32 | asset_shares: slot+40..55
  liability_shares: slot+56..71 | last_update: slot+88..95
"""
import json
import time
import hashlib
import base64
import urllib.request
from pathlib import Path

MON = Path(__file__).resolve().parent
KEY = (MON / "helius_key.txt").read_text().strip()
RPC = f"https://mainnet.helius-rpc.com/?api-key={KEY}"
PROG = "MFv2hWf31Z9kbCa1snEPYctwafyhdvnV7FZnsebVacA"
LOG_PATH = str(MON / "liq_radar_log.jsonl")

ALPHA = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BAL_OFF = 72
STRIDE = 104
SLOTS = 16
REGION_LEN = STRIDE * SLOTS  # 1664


def b58encode(b: bytes) -> str:
    n = int.from_bytes(b, "big")
    s = ""
    while n:
        n, r = divmod(n, 58)
        s = ALPHA[r] + s
    return "1" * (len(b) - len(b.lstrip(b"\0"))) + s


def disc(name: str) -> str:
    return b58encode(hashlib.sha256(f"account:{name}".encode()).digest()[:8])


def rpc(method: str, params: list, timeout: int = 300) -> dict:
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    req = urllib.request.Request(RPC, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def scan_shard(byte_val: int) -> dict:
    """One 1/256 shard: all MarginfiAccounts whose authority's first byte
    equals byte_val. (memcmp needs exact bytes; 256 shards x ~650 accounts
    keeps each response ~1MB / sub-second.)"""
    t0 = time.time()
    resp = rpc("getProgramAccounts", [PROG, {
        "encoding": "base64",
        "dataSlice": {"offset": BAL_OFF, "length": REGION_LEN},
        "filters": [
            {"memcmp": {"offset": 0, "bytes": disc("MarginfiAccount")}},
            {"memcmp": {"offset": 40, "bytes": b58encode(bytes([byte_val]))}},
        ],
    }])
    err = resp.get("error")
    if err:
        return {"shard": byte_val, "error": str(err)[:300]}
    rows = resp.get("result") or []
    borrowers = []
    active_total = 0
    for r in rows:
        raw = base64.b64decode(r["account"]["data"][0])
        has_liab = False
        n_active = 0
        for i in range(SLOTS):
            o = i * STRIDE
            if o + STRIDE > len(raw):
                break
            if raw[o] != 1:
                continue
            n_active += 1
            liab = int.from_bytes(raw[o + 56:o + 72], "little", signed=True)
            if liab != 0:
                has_liab = True
        active_total += n_active
        if has_liab:
            borrowers.append(r["pubkey"])
    return {
        "shard": byte_val,
        "accounts": len(rows),
        "active_slots": active_total,
        "borrowers": len(borrowers),
        "borrower_pks": borrowers[:200],
        "secs": round(time.time() - t0, 1),
    }


def scan_all() -> dict:
    shards = []
    for b in range(256):
        shards.append(scan_shard(b))
    ok = [s for s in shards if "error" not in s]
    rec = {
        "ts": time.time(),
        "kind": "liq_radar_tier1",
        "accounts": sum(s.get("accounts", 0) for s in ok),
        "borrowers": sum(s.get("borrowers", 0) for s in ok),
        "shards_ok": len(ok),
        "total_secs": round(sum(s.get("secs", 0) for s in ok), 1),
        "shards": [{k: v for k, v in s.items() if k != "borrower_pks"} for s in shards],
    }
    # persist full borrower lists separately (shortlist for Tier 2)
    all_borrowers = [pk for s in ok for pk in s.get("borrower_pks", [])]
    rec["borrower_pks"] = all_borrowers
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "probe":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        r = scan_shard(n)
        print(json.dumps({k: v for k, v in r.items() if k != "borrower_pks"}, indent=1))
    else:
        r = scan_all()
        print(json.dumps({k: v for k, v in r.items() if k not in ("borrower_pks", "shards")}, indent=1))
