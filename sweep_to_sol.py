#!/usr/bin/env python3
"""Sweep every non-SOL token in the wallet to SOL, then close all ATAs.

Covers BOTH token programs: legacy SPL (Tokenkeg...) and Token-2022
(TokenzQd... — pump.fun/PumpSwap mints). Owner directive: wallet holds ONLY SOL.

Per token: quote the full balance via Jupiter; if the quote is worth more than
MIN_SELL_SOL, sell via pool_sell; otherwise treat as dust. Residual dust
(<=1% of original, or the whole balance when unsellable) is BURNED and the
account closed, recovering rent.

Usage: python3 sweep_to_sol.py
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_trader as lt

PROGRAMS = {
    "spl": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "t2022": "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
}
PROG_BYTES = {"spl": lt.TOKENKEG, "t2022": lt.TOKEN2022}
MIN_SELL_SOL = 0.003   # 09-13: raised from 0.0005 — below ~0.003 SOL a
                       # Jupiter sell's priority fee + slippage eats the
                       # proceeds (observed: 0.0002 SOL fee on 0.0015 SOL
                       # dust sells). Dust now goes straight to burn+close.


def scan(addr, prog):
    return (lt._rpc("getTokenAccountsByOwner",
                    [addr, {"programId": prog},
                     {"encoding": "jsonParsed"}]) or {}).get("value", [])


def quote_sol(mint, raw):
    try:
        q = lt.jupiter_quote_sell(mint, raw)
        return int(q.get("outAmount", 0)) / 1e9
    except Exception:
        return 0.0


def main():
    addr = json.loads(open("live_wallet.json").read())["address"]
    total_sold = total_burned = total_closed = 0

    for tag, prog in PROGRAMS.items():
        accs = scan(addr, prog)
        mints = {}
        for a in accs:
            info = a["account"]["data"]["parsed"]["info"]
            amt = int(info["tokenAmount"]["amount"])
            if amt > 0:
                mints[info["mint"]] = mints.get(info["mint"], 0) + amt
        if mints:
            print(f"[sweep:{tag}] {len(mints)} token(s) with balance")
        for mint, raw in mints.items():
            est = quote_sol(mint, raw)
            if est >= MIN_SELL_SOL:
                try:
                    res = lt.pool_sell(mint, raw, reason="lp_sweep")
                    print(f"[sweep:{tag}] sell {mint[:8]} raw={raw} ~{est:.5f} SOL: "
                          f"{json.dumps(res)[:200]}")
                    total_sold += 1
                except Exception as e:
                    print(f"[sweep:{tag}] sell FAILED {mint[:8]}: {e}")
                time.sleep(1)
                est_left = quote_sol(mint, 10**9)  # probe residual value per unit
            # dust burn + close: residual after sell, or whole balance if unsellable
            try:
                left = 0
                for a in scan(addr, prog):
                    i = a["account"]["data"]["parsed"]["info"]
                    if i["mint"] == mint:
                        left += int(i["tokenAmount"]["amount"])
                if left > 0:
                    dust_val = quote_sol(mint, left)
                    if dust_val < MIN_SELL_SOL:
                        bc = lt.close_token_accounts(
                            mints={mint}, dust_ceiling={mint: left},
                            reason="lp_sweep_dust", prog=PROG_BYTES[tag])
                        print(f"[sweep:{tag}] burn+close {mint[:8]} raw={left} "
                              f"(~{dust_val:.6f} SOL): {bc.get('result')}")
                        total_burned += 1
                    else:
                        print(f"[sweep:{tag}] WARNING {mint[:8]} residual worth "
                              f"{dust_val:.5f} SOL — left in wallet")
            except Exception as e:
                print(f"[sweep:{tag}] dust burn FAILED {mint[:8]}: {e}")
            time.sleep(0.5)
        # close zero-balance accounts for this program (rent reclaim)
        try:
            close = lt.close_token_accounts(sweep_empty=True, reason="lp_sweep",
                                            prog=PROG_BYTES[tag])
            print(f"[sweep:{tag}] close empty: {close.get('result')}")
        except Exception as e:
            print(f"[sweep:{tag}] close empty FAILED: {e}")

    # final verification across both programs
    nonzero = 0
    total_accs = 0
    for tag, prog in PROGRAMS.items():
        left = scan(addr, prog)
        total_accs += len(left)
        nonzero += sum(1 for a in left
                       if int(a["account"]["data"]["parsed"]["info"]["tokenAmount"]["amount"]) > 0)
    bal = lt.balance_sol(addr)
    print(f"[sweep] final: {bal:.6f} SOL, {nonzero} non-empty token accounts, "
          f"{total_accs} total ATAs | sold={total_sold} burned={total_burned}")
    ok = nonzero == 0
    print(f"[sweep] SOL-only: {'YES' if ok else 'NO — residual tokens remain'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
