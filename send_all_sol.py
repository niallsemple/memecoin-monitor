#!/usr/bin/env python3
"""send_all_sol.py — one-shot: transfer (almost) all SOL to a recipient.

Manual legacy-transaction build (no solana-py on this box):
SystemProgram::Transfer, 1 signer, recent blockhash, Ed25519 sign,
sendTransaction base64. Leaves FEE_BUFFER lamports for the tx fee.
"""
import base64, json, sys, time, urllib.request
from pathlib import Path

MON = Path(__file__).resolve().parent
sys.path.insert(0, str(MON))
import live_trader as lt  # reuses wallet + rpc plumbing

SYSTEM_PROGRAM = bytes(32)  # 11111111111111111111111111111111
FEE_BUFFER = 5_000  # exact fee: sender must end at 0 (dust < rent-exempt is rejected)         # lamports kept back for fee + margin


def b58decode(s):
    alpha = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = 0
    for ch in s:
        n = n * 58 + alpha.index(ch)
    out = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    pad = len(s) - len(s.lstrip("1"))
    return b"\x00" * pad + out


def shortvec(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params}).encode()
    req = urllib.request.Request(
        lt.RPCS[0], data=body,
        headers={"Content-Type": "application/json",
                 "User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=25).read())


def main():
    dest = sys.argv[1]
    dest_bytes = b58decode(dest)
    assert len(dest_bytes) == 32, "bad recipient address"

    key, address = lt._load_key()
    from_bytes = b58decode(address)

    bal = rpc("getBalance", [address, {"commitment": "confirmed"}])[
        "result"]["value"]
    amount = bal - FEE_BUFFER
    if amount <= 0:
        sys.exit(f"balance {bal} lamports too small to send")
    print(f"from {address} balance {bal/1e9:.6f} SOL")
    print(f"send {amount/1e9:.6f} SOL -> {dest}")

    bh = rpc("getLatestBlockhash", [{"commitment": "finalized"}])[
        "result"]["value"]["blockhash"]
    bh_bytes = b58decode(bh)

    keys = [from_bytes, dest_bytes, SYSTEM_PROGRAM]
    header = bytes([1, 0, 1])                       # 1 sig, 0 ro-signed, 1 ro-unsigned
    accts = shortvec(len(keys)) + b"".join(keys)
    ix_data = shortvec(12) + (2).to_bytes(4, "little") + amount.to_bytes(8, "little")
    ix = bytes([2]) + shortvec(2) + bytes([0, 1]) + ix_data
    msg = header + accts + bh_bytes + shortvec(1) + ix

    sig = key.sign(msg)
    tx = shortvec(1) + sig + msg
    res = rpc("sendTransaction",
              [base64.b64encode(tx).decode(),
               {"encoding": "base64", "skipPreflight": False,
                "preflightCommitment": "confirmed"}])
    if "error" in res:
        sys.exit(f"send failed: {res['error']}")
    sig_s = res["result"]
    print(f"submitted: {sig_s}")
    for _ in range(20):
        st = rpc("getSignatureStatuses", [[sig_s]]).get("result", {})
        v = (st.get("value") or [None])[0]
        if v and v.get("confirmationStatus") in ("confirmed", "finalized"):
            print("confirmed:", v.get("confirmationStatus"),
                  "err:", v.get("err"))
            break
        time.sleep(2)
    nb = rpc("getBalance", [address, {"commitment": "confirmed"}])[
        "result"]["value"]
    print(f"new balance: {nb/1e9:.6f} SOL")


if __name__ == "__main__":
    main()
