#!/usr/bin/env python3
"""mfi_init.py — create our own marginfi account (liquidator identity).

Why: the §357 sims showed the STAKED-collateral liquidation class (incl. the
REAL candidate GFxxnJpDAjb3, ~$12.6k SOL debt) fails only because the borrowed
stand-in liquidator account has incompatible asset tags. A fresh account we own
can hold SOL borrows + STAKED collateral, which is a permitted mix.

marginfi_account_initialize (refs/initialize.rs, verified):
  disc = sha256("global:marginfi_account_initialize")[:8], no args
  accounts: [0] group (ro) [1] new account (w, signer) [2] authority (ro, signer)
            [3] fee_payer (w, signer) [4] system program
Cost: rent-exempt for 2320 B (~0.016 SOL) + tx fee. Simulate first, then send.
"""
import base64
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

MON = Path(__file__).resolve().parent
sys.path.insert(0, str(MON))
import importlib.util
_spec = importlib.util.spec_from_file_location("live_trader", str(MON / "live_trader.py"))
lt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lt)

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption

PROG_S = "MFv2hWf31Z9kbCa1snEPYctwafyhdvnV7FZnsebVacA"
PROG = lt.b58dec(PROG_S)
SYSTEM = bytes(32)  # 11111111111111111111111111111111
INIT_DISC = hashlib.sha256(b"global:marginfi_account_initialize").digest()[:8]
# §358: main mrgnlend group — all 204 banks we care about live here. The earlier
# panic was passing a small community group (2v4DXmm, 1064B) that fails the
# deployed program's group struct load. Real init txs on-chain use this group
# with the plain (keypair-signed) initialize ix.
MAIN_GROUP = lt.b58dec("4qp6Fx6tnZkY5Wropq9wUYgtFxXKwE6viZxFHg3rdAG8")
KEY_FILE = MON / "mfi_account_key.json"

sys.path.insert(0, str(MON))
from liq_health import rpc, load_banks  # noqa: E402


def b58e(b: bytes) -> str:
    from liq_health import b58encode
    return b58encode(b)


def build_signed_tx(signers: dict, payer_b: bytes, instructions):
    """Generalized legacy tx: signers = {pubkey_bytes: Ed25519PrivateKey}."""
    keys = [payer_b]
    meta = {payer_b: [True, True]}
    for prog, accs, _ in instructions:
        for k, w, s in accs:
            if k not in meta:
                meta[k] = [w, s]
                keys.append(k)
            else:
                meta[k][0] = meta[k][0] or w
                meta[k][1] = meta[k][1] or s
        if prog not in meta:
            meta[prog] = [False, False]
            keys.append(prog)
    signer_ks = [k for k in keys if meta[k][1]]
    writable = [k for k in keys if not meta[k][1] and meta[k][0]]
    readonly = [k for k in keys if not meta[k][1] and not meta[k][0]]
    ordered = signer_ks + writable + readonly
    idx = {k: i for i, k in enumerate(ordered)}
    bh = lt._rpc("getLatestBlockhash", [{"commitment": "finalized"}])["value"]["blockhash"]
    msg = bytearray()
    msg += bytes([len(signer_ks),
                  sum(1 for k in signer_ks if not meta[k][0]),
                  len(readonly)])
    msg += lt._shortvec(len(ordered))
    for k in ordered:
        msg += k
    msg += lt.b58dec(bh)
    msg += lt._shortvec(len(instructions))
    for prog, accs, data in instructions:
        msg += bytes([idx[prog]])
        msg += lt._shortvec(len(accs))
        for k, _, _ in accs:
            msg += bytes([idx[k]])
        msg += lt._shortvec(len(data)) + data
    sigs = b""
    for k in signer_ks:
        sk = signers.get(k)
        if sk is None:
            raise RuntimeError(f"missing signer key for {b58e(k)}")
        sigs += sk.sign(bytes(msg))
    tx = lt._shortvec(len(signer_ks)) + sigs + bytes(msg)
    return base64.b64encode(bytes(tx)).decode()


def main():
    wallet_key, wallet_addr = lt._load_key()
    wallet_b = lt.b58dec(wallet_addr)

    if KEY_FILE.exists():
        d = json.loads(KEY_FILE.read_text())
        sec = bytes(d["keypair_bytes"])
        acct_key = Ed25519PrivateKey.from_private_bytes(sec[:32])
        acct_addr = d["address"]
        print("existing marginfi account key:", acct_addr)
    else:
        acct_key = Ed25519PrivateKey.generate()
        sec = acct_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        pub = acct_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        acct_addr = b58e(pub)
        KEY_FILE.write_text(json.dumps({
            "address": acct_addr,
            "keypair_bytes": list(sec + pub),
        }))
        print("generated marginfi account keypair:", acct_addr)
    acct_b = lt.b58dec(acct_addr)
    group = MAIN_GROUP

    # already on-chain?
    v = rpc("getAccountInfo", [acct_addr, {"encoding": "base64"}])["result"]["value"]
    if v and v["owner"] == PROG_S:
        print("already initialized on-chain, owner=marginfi. done.")
        return

    print("group:", b58e(group))
    ixs = [(PROG, [
        (group, False, False),
        (acct_b, True, True),
        (wallet_b, False, True),
        (wallet_b, True, True),
        (SYSTEM, False, False),
    ], INIT_DISC)]

    signers = {wallet_b: wallet_key, acct_b: acct_key}
    tx = build_signed_tx(signers, wallet_b, ixs)

    sim = rpc("simulateTransaction", [tx, {"encoding": "base64", "sigVerify": False,
                                         "replaceRecentBlockhash": True}])
    if sim.get("error"):
        print("SIM RPC ERROR (fail-closed):", sim["error"]); return
    err = sim["result"]["value"].get("err")
    print("simulate err:", err)
    if err:
        for l in sim["result"]["value"].get("logs") or []:
            print("  ", l)
        return

    res = rpc("sendTransaction", [tx, {"encoding": "base64", "skipPreflight": False}])
    sig = res.get("result")
    print("sent:", sig)
    if not sig:
        print(json.dumps(res)[:500]); return
    for _ in range(30):
        st = lt._rpc("getSignatureStatuses", [[sig]]).get("value", [None])[0]
        if st and st.get("confirmationStatus") in ("confirmed", "finalized"):
            print("confirmed:", st.get("confirmationStatus"), "err:", st.get("err"))
            break
        time.sleep(2)
    v = rpc("getAccountInfo", [acct_addr, {"encoding": "base64"}])["result"]["value"]
    print("on-chain:", bool(v), "owner:", v["owner"] if v else None,
          "len:", len(base64.b64decode(v["data"][0])) if v else 0)
    print("wallet balance now:", lt.balance_sol(wallet_addr), "SOL")


if __name__ == "__main__":
    main()
