"""birth_watch.py — §404: birth-venue monitors for Meteora DBC + Raydium
LaunchLab. READ-ONLY. These are pump.fun's competitors: coins born here
are ones our tracker has never seen. Earlier entry + newborn-arb both
start with SEEING the birth.

Method: poll getSignaturesForAddress on each program (Helius rotation via
live_trader._rpc), fetch new txs jsonParsed, and extract the fresh token
mint from meta.postTokenBalances (the non-WSOL mint). No instruction
layout decoding needed for detection — meta gives us the mint directly.

State: birth_watch_state.json (last processed signature per program).
Log:   birth_watch.jsonl — {t, venue, sig, mint, pool_hint}
"""
import base64
import hashlib
import json
import time
from pathlib import Path

MON = Path(__file__).resolve().parent
STATE = MON / "birth_watch_state.json"
LOG = MON / "birth_watch.jsonl"

VENUES = {
    "meteora_dbc": "dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN",
    "raydium_launchlab": "LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj",
}
# Anchor 8-byte instruction discriminators: sha256("global:<name>")[:8]
DISC = {
    "meteora_dbc": hashlib.sha256(
        b"global:initialize_virtual_pool_with_spl_token").digest()[:8],
    "raydium_launchlab": hashlib.sha256(b"global:initialize").digest()[:8],
}
WSOL = "So11111111111111111111111111111111111111112"
PAGE = 20          # signatures per poll per venue
_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _b58d(s):
    n = 0
    for ch in s:
        n = n * 58 + _B58.index(ch)
    b = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\x00" * (len(s) - len(s.lstrip("1"))) + b


def _rpc(method, params):
    import raydium_cpmm as rc
    return rc.rpc(method, params)


def _extract_mint(sig, venue):
    """Return the newborn mint ONLY if this tx actually initializes a pool
    (discriminator match on the venue program's instruction). Swaps and
    other touches are ignored — pass 1 proved they dominate the feed."""
    try:
        tx = _rpc("getTransaction", [sig, {"encoding": "jsonParsed",
                                           "maxSupportedTransactionVersion": 0}])
        if not tx:
            return None
        prog = VENUES[venue]
        disc = DISC[venue]
        msg = tx.get("transaction", {}).get("message", {})
        meta = tx.get("meta") or {}
        # program can be invoked at top level OR via CPI (aggregators,
        # launch UIs) — gSFA fires for both, so scan both levels.
        ixs = list(msg.get("instructions", []))
        for inner in meta.get("innerInstructions") or []:
            ixs.extend(inner.get("instructions", []))
        hit = False
        for ix in ixs:
            if ix.get("programId") == prog and ix.get("data"):
                try:
                    if _b58d(ix["data"]).startswith(disc):
                        hit = True
                        break
                except Exception:
                    continue
        if not hit:
            return None
        for b in meta.get("postTokenBalances") or []:
            m = b.get("mint")
            if m and m != WSOL:
                return m
    except Exception:
        pass
    return None


def run_pass():
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    new_rows = 0
    for venue, prog in VENUES.items():
        try:
            sigs = _rpc("getSignaturesForAddress", [prog, {"limit": PAGE}]) or []
        except Exception:
            continue
        last = st.get(prog)
        fresh = []
        for s in sigs:
            if s["signature"] == last:
                break
            fresh.append(s["signature"])
        if not sigs:
            continue
        st[prog] = sigs[0]["signature"]
        if last is None:
            # first run: mark high-water only, don't backfill the page
            continue
        for sig in reversed(fresh):  # oldest first
            mint = _extract_mint(sig, venue)
            if not mint:
                continue
            row = {"t": time.time(), "venue": venue, "sig": sig,
                   "mint": mint}
            with LOG.open("a") as f:
                f.write(json.dumps(row) + "\n")
            new_rows += 1
    STATE.write_text(json.dumps(st))
    return {"new": new_rows}


if __name__ == "__main__":
    print("pass 1 (prime):", run_pass())
    print("pass 2:", run_pass())
