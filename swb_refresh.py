#!/usr/bin/env python3
"""swb_refresh.py — Switchboard on-demand feed refresh bundling (§367).

marginfi SwbPull banks (setup 4) go stale because nobody pays the oracle
network to land updates. To liquidate accounts priced by a stale feed, the
liquidate tx must first land a fresh signed update on that feed.

Switchboard's crossbar API returns PRE-BUILT bincode-serialized instructions
(pullIxns) for a feed set: [0] = secp256k1 signature verification,
[1] = the submit-response ix on SBondMDrcV3K. We decode both (bincode:
program[32] + u64 n_accts + n*(pubkey[32]+is_signer+is_writable) +
u64 data_len + data), swap the payer placeholder (account key ==
system-program id with signer+writable flags) for our wallet, and prepend
both ixs to the liquidate tx.
"""
import json
import struct
import sys
import urllib.request
from pathlib import Path

MON = Path(__file__).resolve().parent
sys.path.insert(0, str(MON))

import importlib.util
_spec = importlib.util.spec_from_file_location("live_trader", str(MON / "live_trader.py"))
lt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lt)

CROSSBAR = "https://crossbar.switchboard.xyz/updates/solana/mainnet"
SECP_PROG = "KeccakSecp256k11111111111111111111111111111"
SYS_PROG = "11111111111111111111111111111111"


def _decode_ix(raw: bytes):
    """bincode solana Instruction -> (program_bytes, [(key,writable,signer)], data)."""
    prog = raw[:32]
    n = struct.unpack("<Q", raw[32:40])[0]
    off = 40
    metas = []
    for _ in range(n):
        metas.append([raw[off:off + 32], bool(raw[off + 33]), bool(raw[off + 32])])
        # stored as [key, writable, signer]; wire bytes are signer@+32, writable@+33
        off += 34
    dlen = struct.unpack("<Q", raw[off:off + 8])[0]
    data = raw[off + 8:off + 8 + dlen]
    return prog, metas, data


def fetch_update_ixs(feed_pks: list, payer_b: bytes):
    """Fetch + decode crossbar update ixs for feeds; payer placeholder swapped
    to payer_b. Returns list of (program, [(key,writable,signer)], data).
    Raises on dead feeds (no live oracle network coverage)."""
    url = f"{CROSSBAR}/{','.join(feed_pks)}"
    resp = json.loads(urllib.request.urlopen(url, timeout=20).read())
    r0 = resp[0]
    if not r0.get("success"):
        errs = "; ".join((x.get("errors") or "")[:120] for x in r0.get("responses", []))
        raise RuntimeError(f"crossbar: feed(s) have no live oracle coverage: {errs}")
    ixs = []
    for ix_hex in r0["pullIxns"]:
        prog, metas, data = _decode_ix(bytes.fromhex(ix_hex))
        for m in metas:
            # crossbar leaves payer as system-program-id placeholder with
            # signer+writable flags set — swap in our wallet
            if m[0] == lt.b58dec(SYS_PROG) and m[1] and m[2]:
                m[0] = payer_b
        ixs.append((prog, [(m[0], m[1], m[2]) for m in metas], data))
    return ixs


if __name__ == "__main__":
    # standalone validation: refresh a live-but-possibly-stale feed and sim it
    import liq_health as lh
    banks = lh.load_banks()
    feed = next(b["oracle"] for b in banks.values()
                if b["setup"] == 4 and b["oracle"].startswith("8w1GuQwSf2w8"))
    payer = lt.b58dec(lt._load_key()[1])
    ixs = fetch_update_ixs([feed], payer)
    print(f"decoded {len(ixs)} ixs:")
    for prog, metas, data in ixs:
        print(f"  prog={lt.b58enc(prog)} accounts={len(metas)} data={len(data)}B head={data[:8].hex()}")
    tx = lt.build_legacy_tx(payer, ixs)
    res = lh.rpc("simulateTransaction", [tx, {"encoding": "base64",
                 "sigVerify": False, "replaceRecentBlockhash": True}])
    val = (res.get("result") or {}).get("value") or {}
    print("err:", val.get("err"))
    for line in (val.get("logs") or [])[-15:]:
        print("  ", line)
