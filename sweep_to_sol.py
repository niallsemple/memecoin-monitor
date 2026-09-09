#!/usr/bin/env python3
"""Sweep every non-SOL token in the wallet to SOL via Jupiter, then close
empty ATAs. Owner directive: after LP exits the wallet holds ONLY SOL.

Usage: python3 sweep_to_sol.py
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_trader as lt


def main():
    addr = json.loads(open("live_wallet.json").read())["address"]
    accs = (lt._rpc("getTokenAccountsByOwner",
                    [addr, {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                     {"encoding": "jsonParsed"}]) or {}).get("value", [])
    mints = {}
    for a in accs:
        info = a["account"]["data"]["parsed"]["info"]
        amt = int(info["tokenAmount"]["amount"])
        if amt > 0:
            mints[info["mint"]] = mints.get(info["mint"], 0) + amt
    print(f"[sweep] {len(mints)} token(s) with balance")
    for mint, raw in mints.items():
        try:
            res = lt.pool_sell(mint, raw, reason="lp_sweep")
            print(f"[sweep] sell {mint[:8]} raw={raw}: {json.dumps(res)[:220]}")
        except Exception as e:
            print(f"[sweep] sell FAILED {mint[:8]}: {e}")
        time.sleep(1)
    try:
        close = lt.close_token_accounts(sweep_empty=True, reason="lp_sweep")
        print(f"[sweep] close: {close.get('result')}")
    except Exception as e:
        print(f"[sweep] close FAILED: {e}")
    left = (lt._rpc("getTokenAccountsByOwner",
                    [addr, {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                     {"encoding": "jsonParsed"}]) or {}).get("value", [])
    nonzero = [a for a in left if int(a["account"]["data"]["parsed"]["info"]["tokenAmount"]["amount"]) > 0]
    bal = lt.balance_sol(addr)
    print(f"[sweep] final: {bal:.6f} SOL, {len(nonzero)} non-empty token accounts, {len(left)} total ATAs")
    ok = len(nonzero) == 0
    print(f"[sweep] SOL-only: {'YES' if ok else 'NO — residual tokens remain'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
