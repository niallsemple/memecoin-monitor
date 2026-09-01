"""live_trader.py — live execution path for the memecoin-monitor system.

SAFETY MODEL (two hard gates, BOTH required for a real transaction):
  1. manual_signoff.json must exist in this directory AND contain
     {"live": true}. The OWNER creates this file. The agent never does.
  2. The file STOP_LIVE_TRADING must NOT exist. Drop that file here to
     halt everything instantly (checked before every single trade).

Default mode is DRY-RUN: quotes are fetched and logged, nothing is
signed or submitted. The wallet secret never leaves this machine:
Jupiter returns an unsigned transaction; we sign locally with the
ed25519 key from live_wallet.json and submit via public RPC.

Coverage: Jupiter Ultra/v6 works for PumpSwap (graduated) tokens.
Bonding-curve (pre-graduation) swaps are NOT built here yet — entries
on the curve need the pump.fun program path (§109 work).

All decisions append to mfg_live_trades.jsonl, including dry-runs and
refusals, so the paper record and the live record stay comparable.
"""
import base64
import json
import os
import time
import urllib.request
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

MON = Path(__file__).resolve().parent
WALLET_F = MON / "live_wallet.json"
SIGNOFF_F = MON / "manual_signoff.json"     # owner-created; agent never touches
KILL_F = MON / "STOP_LIVE_TRADING"          # drop this file = instant halt
LEDGER = MON / "mfg_live_trades.jsonl"

SOL = "So11111111111111111111111111111111111111112"
RPCS = ["https://solana-rpc.publicnode.com",
        "https://api.mainnet-beta.solana.com"]
JUP_Q = "https://lite-api.jup.ag/swap/v1/quote"
JUP_S = "https://lite-api.jup.ag/swap/v1/swap"

# Position sizing: fixed fraction of balance, hard caps.
FRAC = 0.05              # 5% of wallet balance per entry
MAX_SOL = 0.20           # never more than 0.2 SOL on one entry
MIN_BAL_KEEP = 0.05      # always keep this much for fees/rent
SLIPPAGE_BPS = 1500      # memecoin reality; tight slips just fail
PRIOR_FEE_MICROLAMPORTS = 200_000  # ~0.0002 SOL priority fee

_state = {"rpc": 0}


def _log(row):
    row["ts"] = time.time()
    with LEDGER.open("a") as f:
        f.write(json.dumps(row) + "\n")


def _rpc(method, params):
    for _ in range(4):
        url = RPCS[_state["rpc"] % len(RPCS)]
        _state["rpc"] += 1
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps({"jsonrpc": "2.0", "id": 1,
                                 "method": method, "params": params}).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=25) as r:
                out = json.loads(r.read())
            if "error" in out:
                time.sleep(2.0)
                continue
            return out.get("result")
        except Exception:
            time.sleep(2.0)
    return None


def _load_key():
    d = json.loads(WALLET_F.read_text())
    sec = bytes(d["keypair_bytes"])
    return Ed25519PrivateKey.from_private_bytes(sec[:32]), d["address"]


def live_enabled():
    """Both gates must pass. Returns (bool, reason)."""
    if KILL_F.exists():
        return False, "kill-switch file present"
    if not SIGNOFF_F.exists():
        return False, "no manual_signoff.json (owner has not enabled live)"
    try:
        if not json.loads(SIGNOFF_F.read_text()).get("live"):
            return False, "manual_signoff.json live flag is not true"
    except Exception:
        return False, "manual_signoff.json unreadable"
    return True, "live"


def balance_sol(address):
    r = _rpc("getBalance", [address])
    return (r or {}).get("value", 0) / 1e9


def position_size_sol(address):
    bal = balance_sol(address)
    size = min(bal * FRAC, MAX_SOL)
    size = min(size, bal - MIN_BAL_KEEP)
    return max(0.0, round(size, 4)), bal


def jupiter_quote(mint, amount_sol, side="buy"):
    """side=buy: SOL->mint. side=sell: mint->SOL (amount_sol ignored then;
    pass raw token amount via amount_sol=None handled by caller)."""
    if side == "buy":
        params = (f"inputMint={SOL}&outputMint={mint}"
                  f"&amount={int(amount_sol * 1e9)}"
                  f"&slippageBps={SLIPPAGE_BPS}")
    else:
        raise ValueError("sell path needs raw token amount")
    with urllib.request.urlopen(f"{JUP_Q}?{params}", timeout=20) as r:
        return json.loads(r.read())


def _sign_versioned_tx(tx_b64, key):
    """Sign a Jupiter v0 transaction locally. Jupiter txs need exactly one
    signature (the fee payer = us) at signatures[0]."""
    raw = bytearray(base64.b64decode(tx_b64))

    def read_shortvec(buf, i):
        val = shift = 0
        while True:
            b = buf[i]; i += 1
            val |= (b & 0x7F) << shift
            if not b & 0x80:
                return val, i
            shift += 7

    n_sigs, i = read_shortvec(raw, 0)
    msg = bytes(raw[i + 64 * n_sigs:])
    sig = key.sign(msg)
    out = bytearray()
    # rewrite signature array (n_sigs almost always 1)
    out += bytes([n_sigs])
    out += sig
    out += raw[i + 64: i + 64 * n_sigs]      # any remaining sigs (unused)
    out += msg
    return base64.b64encode(bytes(out)).decode()


def buy(mint, reason="signal"):
    """One live (or dry-run) entry. Returns the ledger row."""
    ok, why = live_enabled()
    size, bal = position_size_sol(json.loads(WALLET_F.read_text())["address"])
    row = {"action": "buy", "mint": mint, "reason": reason,
           "size_sol": size, "balance_sol": round(bal, 4),
           "mode": "live" if ok else "dry-run", "gate": why}
    if size <= 0:
        row["result"] = "refused: zero size (balance too low)"
        _log(row)
        return row
    try:
        q = jupiter_quote(mint, size, "buy")
        row["quote_out"] = q.get("outAmount")
        row["quote_price_impact"] = q.get("priceImpactPct")
    except Exception as e:
        row["result"] = f"quote failed: {e}"
        _log(row)
        return row
    if not ok:
        row["result"] = f"dry-run ok ({why})"
        _log(row)
        return row
    try:
        key, address = _load_key()
        req = urllib.request.Request(
            JUP_S,
            data=json.dumps({
                "quoteResponse": q, "userPublicKey": address,
                "wrapAndUnwrapSol": True,
                "prioritizationFeeLamports": PRIOR_FEE_MICROLAMPORTS,
            }).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=25) as r:
            swap = json.loads(r.read())
        signed = _sign_versioned_tx(swap["swapTransaction"], key)
        sig = _rpc("sendTransaction", [signed, {"encoding": "base64"}])
        row["result"] = "submitted"
        row["sig"] = sig
    except Exception as e:
        row["result"] = f"submit failed: {e}"
    _log(row)
    return row


if __name__ == "__main__":
    ok, why = live_enabled()
    d = json.loads(WALLET_F.read_text())
    size, bal = position_size_sol(d["address"])
    print(f"address : {d['address']}")
    print(f"balance : {bal:.4f} SOL")
    print(f"mode    : {'LIVE' if ok else 'DRY-RUN'} ({why})")
    print(f"next buy size: {size} SOL")
