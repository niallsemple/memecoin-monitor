#!/usr/bin/env python3
"""
DARWIN shadow searcher v0 — paper-only atomic-arb opportunity logger.

Per docs/DARWIN_FLASH_LOANS.md: build a shadow/paper searcher that records
every opportunity with a realistic simulated outcome BEFORE risking anything.

v0 scope: USDC -> SOL -> USDC atomic round trip quoted through Jupiter v6
(aggregator quotes embed venue spread + price impact). For each candidate
size q we compute:

    Profit(q) = out2_usdc - q - priority_fee_usdc - tip_usdc - flash_fee(=0)

and log the full size ladder so q* = argmax Profit(q) falls out of data.

No trades are constructed, signed or sent. Read-only HTTP quotes.
"""
import json
import time
import urllib.request
import urllib.parse
import sys
from pathlib import Path

USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"   # 6 decimals
SOL = "So11111111111111111111111111111111111111112"     # 9 decimals
QUOTE_API = "https://lite-api.jup.ag/swap/v1/quote"
SLIPPAGE_BPS = 50

# cost model (conservative, usdc)
PRIORITY_FEE_USDC = 0.002   # ~10k lamports at SOL~$200
TIP_USDC = 0.0              # no Jito tip in v0 model
FLASH_FEE_USDC = 0.0        # Project 0 zero-fee flash loans per docs

SIZES_USDC = [500, 1_000, 2_000, 5_000, 10_000, 22_000, 40_000, 75_000]
LOG_PATH = str(Path(__file__).resolve().parent / "shadow_arb_log.jsonl")


def quote(input_mint: str, output_mint: str, amount_raw: int) -> dict:
    qs = urllib.parse.urlencode({
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": str(amount_raw),
        "slippageBps": str(SLIPPAGE_BPS),
    })
    req = urllib.request.Request(f"{QUOTE_API}?{qs}", headers={"User-Agent": "darwin-shadow/0.1"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def scan_once() -> dict:
    rows = []
    for q in SIZES_USDC:
        try:
            leg1 = quote(USDC, SOL, int(q * 1e6))
            sol_out = int(leg1["outAmount"])
            leg2 = quote(SOL, USDC, sol_out)
            usdc_back = int(leg2["outAmount"]) / 1e6
            gross = usdc_back - q
            net = gross - PRIORITY_FEE_USDC - TIP_USDC - FLASH_FEE_USDC
            rows.append({
                "size_usdc": q,
                "sol_out": sol_out / 1e9,
                "usdc_back": round(usdc_back, 4),
                "gross_usdc": round(gross, 4),
                "net_usdc": round(net, 4),
                "net_bps": round(net / q * 1e4, 3),
                "route1": leg1.get("routePlan", [{}])[0].get("swapInfo", {}).get("label"),
                "route2": leg2.get("routePlan", [{}])[0].get("swapInfo", {}).get("label"),
            })
        except Exception as e:
            rows.append({"size_usdc": q, "error": str(e)[:200]})
        time.sleep(0.4)  # be polite to the quote API
    ok = [r for r in rows if "net_usdc" in r]
    best = max(ok, key=lambda r: r["net_usdc"]) if ok else None
    rec = {
        "ts": time.time(),
        "kind": "shadow_arb_scan",
        "pair": "USDC-SOL-USDC",
        "n_sizes": len(ok),
        "best": best,
        "any_positive": bool(best and best["net_usdc"] > 0),
        "ladder": rows,
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


if __name__ == "__main__":
    rec = scan_once()
    b = rec.get("best")
    if b:
        print(f"best size ${b['size_usdc']:,}: net {b['net_usdc']:+.4f} USDC ({b['net_bps']:+.2f} bps)")
    print(f"any_positive={rec['any_positive']}  n_sizes={rec['n_sizes']}")
    for r in rec["ladder"]:
        if "net_usdc" in r:
            print(f"  ${r['size_usdc']:>7,} -> {r['usdc_back']:>10,.2f}  net {r['net_usdc']:+8.4f} ({r['net_bps']:+6.2f} bps) via {r['route1']}/{r['route2']}")
        else:
            print(f"  ${r['size_usdc']:>7,} -> ERROR {r['error']}")
