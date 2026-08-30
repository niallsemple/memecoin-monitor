#!/usr/bin/env python3
"""True creator via pump.fun bonding-curve account (playbook-2 #3, correct build).

The bonding curve PDA (seeds: ["bonding-curve", mint], program
6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P) stores the creator pubkey at
offset 49 (8-byte discriminator + 5 u64 reserves + 1 bool complete).
One getAccountInfo call per token via Helius standard RPC. No pagination.

Falls back to 'no_curve' for non-pump launches.
"""
import json, time, urllib.request, hashlib
from pathlib import Path

ROOT = Path(__file__).parent
KEY = (ROOT / "helius_key.txt").read_text().strip()
RPC = f"https://mainnet.helius-rpc.com/?api-key={KEY}"
PUMP_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
OUT = ROOT / "creator_scan.json"

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def b58decode(s):
    n = 0
    for c in s:
        n = n * 58 + ALPHABET.index(c)
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    pad = len(s) - len(s.lstrip("1"))
    return b"\x00" * pad + b

def b58encode(b):
    n = int.from_bytes(b, "big")
    s = ""
    while n:
        n, r = divmod(n, 58)
        s = ALPHABET[r] + s
    pad = len(b) - len(b.lstrip(b"\x00"))
    return "1" * pad + (s or "")

# --- ed25519 on-curve check (pure python) ---
P = 2**255 - 19
D = (-121665 * pow(121666, P - 2, P)) % P

def on_curve(pubkey_bytes):
    try:
        y = int.from_bytes(pubkey_bytes, "little") & ((1 << 255) - 1)
        if y >= P:
            return False
        x2 = (y * y - 1) * pow(D * y * y + 1, P - 2, P) % P
        # x^2 = x2 has a solution iff x2 is a quadratic residue
        return pow(x2, (P - 1) // 2, P) == 1 or x2 == 0
    except Exception:
        return False

def find_pda(seeds, program_id):
    prog = b58decode(program_id)
    for bump in range(255, -1, -1):
        h = hashlib.sha256()
        for s in seeds:
            h.update(s)
        h.update(bytes([bump]))
        h.update(prog)
        h.update(b"ProgramDerivedAddress")
        cand = h.digest()
        if not on_curve(cand):
            return cand
    raise RuntimeError("no PDA")

def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params}).encode()
    req = urllib.request.Request(RPC, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode())

def creator_of(mint):
    import base64
    pda = find_pda([b"bonding-curve", b58decode(mint)], PUMP_PROGRAM)
    res = rpc("getAccountInfo", [b58encode(pda),
                                 {"encoding": "base64"}])
    acct = (res.get("result") or {}).get("value")
    if not acct:
        return None
    data = base64.b64decode(acct["data"][0])
    if len(data) < 81:
        return None
    return b58encode(data[49:81])

def main():
    cohort = []
    for f, lab in (("rotation_scan.json", "W"), ("losers_scan.json", "L")):
        for x in json.loads((ROOT / f).read_text()):
            if x["id"].startswith("solana:") and x.get("buyers"):
                cohort.append((lab, x["id"].split(":", 1)[1], x.get("peak_x")))
    done = json.loads(OUT.read_text()) if OUT.exists() else {}
    todo = [c for c in cohort if c[1] not in done]
    print(f"cohort {len(cohort)}, remaining {len(todo)}")
    from collections import defaultdict
    for lab, mint, peak in todo:
        try:
            c = creator_of(mint)
        except Exception as e:
            c = f"ERR:{str(e)[:40]}"
        done[mint] = {"creator": c, "label": lab, "peak_x": peak}
        OUT.write_text(json.dumps(done, indent=1))
        print(f"{lab} {mint[:8]} creator={(c or 'NO_CURVE')[:16]}")
        time.sleep(0.4)
    if all(c[1] in done for c in cohort):
        by = defaultdict(list)
        for m, r in done.items():
            c = r.get("creator")
            if c and not c.startswith("ERR"):
                by[c].append((m[:8], r["label"], r.get("peak_x")))
        rep = {d: v for d, v in by.items() if len(v) >= 2}
        print(f"\n== TRUE CREATORS: unique={len(by)}, repeat={len(rep)} ==")
        for d, v in sorted(rep.items(), key=lambda x: -len(x[1])):
            print(f"  {d[:16]}… -> {v}")
        errs = sum(1 for r in done.values() if not r.get("creator") or str(r["creator"]).startswith("ERR"))
        print(f"no-curve/error: {errs}/{len(done)}")

if __name__ == "__main__":
    main()
