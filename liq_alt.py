#!/usr/bin/env python3
"""liq_alt.py — one-time setup: our own address lookup tables holding the
main-group marginfi key universe (§370). The full §337 recipe references
~30 marginfi keys (banks, oracle pairs, vault PDAs, Kamino reserves) that
Jupiter's ALTs don't cover; without our own tables the v0 tx exceeds the
1232-byte packet limit. Saves table addresses to liq_alts.json.

Run:  python3 liq_alt.py            # dry run: count keys, print plan
      python3 liq_alt.py create     # create tables + extend on-chain
"""
import base64
import hashlib
import json
import struct
import sys
import time
from pathlib import Path

MON = Path(__file__).resolve().parent
sys.path.insert(0, str(MON))

import importlib.util
_spec = importlib.util.spec_from_file_location("live_trader", str(MON / "live_trader.py"))
lt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lt)

import liq_health as lh
from liq_sim import acct_raw, PROG

ALT_PROG = lt.b58dec("AddressLookupTab1e1111111111111111111111111")
SYS = lt.b58dec("1" * 32)
GROUP_S = "4qp6Fx6tnZkY5Wropq9wUYgtFxXKwE6viZxFHg3rdAG8"
STATE = MON / "liq_alts.json"
MAX_PER_TABLE = 256
EXTEND_CHUNK = 25        # keep each extend tx well under 1232 bytes

SETUP_COUNT = {8: 1, 13: 2, 14: 2, 17: 2, 19: 3, 20: 4, 21: 4,
               22: 3, 23: 4, 24: 4, 25: 3, 26: 2}
TAG_COUNT = {0: 2, 1: 2, 2: 5, 3: 3, 4: 3, 5: 3, 6: 3}
KAMINO_SETUPS = {6, 7}


def pda_bump(seeds, prog):
    for bump in range(255, -1, -1):
        h = hashlib.sha256()
        for s in seeds:
            h.update(s)
        h.update(bytes([bump]))
        h.update(prog)
        h.update(b"ProgramDerivedAddress")
        d = h.digest()
        if not lt._on_curve(d):
            return d, bump
    raise RuntimeError("no bump")


def collect_keys():
    group = lt.b58dec(GROUP_S)
    keys = []
    seen = set()

    def add(b):
        assert len(b) == 32, f"non-32-byte key slipped in: {lt.b58enc(b)}"
        if b != bytes(32) and b not in seen:
            seen.add(b)
            keys.append(b)

    for s in ("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",      # token prog
              "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",      # ATA prog
              "Sysvar1nstructions1111111111111111111111111",
              "ComputeBudget111111111111111111111111111111",
              "KLend2g3cP87fffoy8q1mQqGKjrxjC8boSyAYavgmjD",
              "SBondMDrcV3K4kxZR1HNVT7osZxAHVHgYXL5Ze1oMUv",      # SWB on-demand (liq_sim.swb_prog_id)
              "A91fDng3SdKxBMPq4DxUSE4LKqBR1g6tf3rC8ypvogRy",      # our mfi acct
              GROUP_S):
        add(lt.b58dec(s))
    banks = lh.load_banks()
    n_main = 0
    for bpk in banks:
        raw = acct_raw(bpk)
        if raw[41:73] != group:
            continue
        n_main += 1
        setup, tag = raw[609], raw[785]
        count = SETUP_COUNT.get(setup) or TAG_COUNT.get(tag) or 2
        bb = lt.b58dec(bpk)
        add(bb)
        for k in range(min(count, 5)):
            add(raw[610 + 32 * k:642 + 32 * k])
        add(lt.pda([b"liquidity_vault_auth", bb], PROG))
        add(lt.pda([b"liquidity_vault", bb], PROG))
        add(lt.pda([b"insurance_vault", bb], PROG))
        if setup in KAMINO_SETUPS:   # refresh_reserve bundle accounts
            reserve = raw[642:674]
            add(reserve)
            r_raw = acct_raw(lt.b58enc(reserve))
            add(r_raw[32:64])        # lending market
            for off in (5112, 5160, 5192, 5224):
                add(r_raw[off:off + 32])
    print(f"main-group banks: {n_main}, total keys: {len(keys)}")
    return keys


def confirm(sig, timeout=45):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = lh.rpc("getSignatureStatuses", [[sig]])
        v = (st.get("result") or {}).get("value") or [None]
        if v and v[0]:
            if v[0].get("err"):
                raise RuntimeError(f"tx failed on-chain: {v[0]['err']}")
            if v[0].get("confirmationStatus") in ("confirmed", "finalized"):
                return
        time.sleep(1.5)
    raise RuntimeError(f"confirm timeout {sig}")


def send(ixs, label):
    payer = lt.b58dec(lt._load_key()[1])
    last_err = None
    for attempt in range(4):
        tx = lt.build_legacy_tx(payer, ixs)
        res = lh.rpc("sendTransaction", [tx, {"encoding": "base64"}])
        if "error" not in res:
            sig = res["result"]
            confirm(sig)
            print(f"  {label}: {sig}")
            return sig
        last_err = res["error"]
        # retry any preflight sim failure (blockhash expiry, RPC node lag
        # behind a just-confirmed create, etc.) — the tx never landed
        time.sleep(3)
    raise RuntimeError(f"{label} send failed after retries: {last_err}")


def create_tables(keys):
    auth_s = lt._load_key()[1]
    auth = lt.b58dec(auth_s)
    slot = lh.rpc("getSlot", [{"commitment": "finalized"}])["result"]
    chunks = [keys[i:i + MAX_PER_TABLE]
              for i in range(0, len(keys), MAX_PER_TABLE)]
    print(f"plan: {len(chunks)} tables, "
          f"{sum((len(c) + EXTEND_CHUNK - 1) // EXTEND_CHUNK for c in chunks)} extend txs")
    tables = []
    done_extends = {}
    if STATE.exists():
        prev = json.loads(STATE.read_text())
        if prev.get("keys_fingerprint") == hashlib.sha256(b"".join(keys)).hexdigest()[:16]:
            tables = prev.get("tables", [])
            done_extends = prev.get("done_extends", {})
            print(f"resuming: {len(tables)} tables already created")
    bal0 = (lh.rpc("getBalance", [auth_s])["result"])["value"]
    for ti, chunk in enumerate(chunks):
        if ti < len(tables):
            table_s = tables[ti]
            table = lt.b58dec(table_s)
        else:
            fresh = lh.rpc("getSlot", [{"commitment": "finalized"}])["result"]
            table, bump = pda_bump([auth, struct.pack("<Q", fresh)], ALT_PROG)
            create = (ALT_PROG, [(table, True, False), (auth, False, True),
                                 (auth, True, True), (SYS, False, False)],
                      struct.pack("<IQB", 0, fresh, bump))
            send([create], f"create table {ti} -> {lt.b58enc(table)}")
            tables.append(lt.b58enc(table))
        for ci in range(0, len(chunk), EXTEND_CHUNK):
            if done_extends.get(str(ti), 0) > ci:
                continue
            part = chunk[ci:ci + EXTEND_CHUNK]
            ext = (ALT_PROG, [(table, True, False), (auth, False, True),
                              (auth, True, True), (SYS, False, False)],
                   struct.pack("<IQ", 2, len(part)) + b"".join(part))
            send([ext], f"extend table {ti} +{len(part)} ({ci + len(part)}/{len(chunk)})")
            done_extends[str(ti)] = ci + len(part)
            STATE.write_text(json.dumps({
                "tables": tables, "done_extends": done_extends,
                "keys_fingerprint": hashlib.sha256(b"".join(keys)).hexdigest()[:16],
                "key_count": len(keys), "created_slot": slot,
                "ts": time.time()}, indent=1))
    bal1 = (lh.rpc("getBalance", [auth_s])["result"])["value"]
    print(f"SOL spent: {(bal0 - bal1) / 1e9:.4f}")
    STATE.write_text(json.dumps({
        "tables": tables, "done_extends": done_extends,
        "keys_fingerprint": hashlib.sha256(b"".join(keys)).hexdigest()[:16],
        "key_count": len(keys), "created_slot": slot,
        "ts": time.time()}, indent=1))
    print(f"saved {STATE}")


if __name__ == "__main__":
    keys = collect_keys()
    if len(sys.argv) > 1 and sys.argv[1] == "create":
        create_tables(keys)
    else:
        n_tables = (len(keys) + MAX_PER_TABLE - 1) // MAX_PER_TABLE
        n_extends = sum((len(keys[i:i + MAX_PER_TABLE]) + EXTEND_CHUNK - 1) // EXTEND_CHUNK
                        for i in range(0, len(keys), MAX_PER_TABLE))
        print(f"DRY: {n_tables} tables, {n_extends} extend txs, "
              f"~{n_tables + n_extends} txs total. Run with 'create' to execute.")
