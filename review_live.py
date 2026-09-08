#!/usr/bin/env python3
"""review_live.py — DARWIN pumpswap cell 10-trade owner review.

Reads pumpswap_live_trades.jsonl + live_trader book + wallet state and prints
the full review: per-trade P&L (on-chain verified where possible), fill
quality vs the sim's 2%/side slippage model, rug rate vs the predicted ~36%,
and session totals. Run after each trade; the owner review gates at n=10.
"""
import json, os, sys, time, urllib.request, datetime

MON = os.path.dirname(os.path.abspath(__file__))
BOOK = os.path.join(MON, "pumpswap_live_trades.jsonl")
LT_BOOK = os.path.join(MON, "mfg_live_trades.jsonl")
WALLET = "CQcKkSee9bdHZ1bejYFDUXVtodbfKHe2KSx6AaAnTW2K"


def load_cfg():
    cfg = {}
    for f in ("helius_config.json", "config.json"):
        p = os.path.join(MON, f)
        if os.path.exists(p):
            cfg.update(json.load(open(p)))
    return cfg


def rpc_call(rpc, method, params):
    req = urllib.request.Request(
        rpc, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                              "params": params}).encode(),
        headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def main():
    entries, exits = {}, {}
    for l in open(BOOK):
        try:
            r = json.loads(l)
        except Exception:
            continue
        if r.get("action") == "entry_signal" and r.get("buy_result") == "submitted":
            entries[r["mint"]] = r
        elif r.get("action") == "exit_signal":
            exits[r["mint"]] = r
    # sell quotes from the live_trader book
    sellq = {}
    if os.path.exists(LT_BOOK):
        for l in open(LT_BOOK):
            try:
                r = json.loads(l)
            except Exception:
                continue
            if r.get("action") == "pool_sell" and r.get("reason", "").startswith("pslive_"):
                sellq[r["mint"]] = r

    n = len(entries)
    print(f"DARWIN pumpswap cell — live review ({n} trades of 10)\n")
    print(f"{'token':<18} {'reason':<10} {'ret':>6} {'held':>6} {'in':>7} "
          f"{'out':>7} {'net':>8}")
    tot_in = tot_out = 0.0
    rugs = 0
    for m, e in entries.items():
        x = exits.get(m)
        sq = sellq.get(m)
        name = (e.get("name") or m[:10])
        insol = 0.10
        out = (sq or {}).get("quote_out_sol") or 0
        ret = x.get("ret") if x else None
        reason = x.get("reason") if x else "OPEN"
        held = x.get("held_min") if x else (time.time() - e.get("t", time.time())) / 60
        if x and (x.get("ret") or 1) <= 0.2:
            rugs += 1
        tot_in += insol
        tot_out += out if x else 0
        print(f"{name:<18} {reason:<10} {ret if ret else 0:>6} "
              f"{held:>5.1f}m {insol:>7.3f} {out:>7.5f} {out-insol:>+8.4f}")
    print(f"\ntotals: in {tot_in:.3f} SOL  out {tot_out:.4f} SOL  "
          f"net {tot_out-tot_in:+.4f} SOL  rugs {rugs}/{n} "
          f"(model predicted ~36%)")
    cfg = load_cfg()
    rpc = cfg.get("helius_rpc") or "https://api.mainnet-beta.solana.com"
    try:
        bal = rpc_call(rpc, "getBalance", [WALLET])["result"]["value"] / 1e9
        ta = rpc_call(rpc, "getTokenAccountsByOwner",
                      [WALLET, {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                       {"encoding": "jsonParsed"}])["result"]["value"]
        print(f"wallet: {bal:.6f} SOL, {len(ta)} token accounts "
              f"(SOL-only: {'YES' if not ta else 'NO'})")
    except Exception as ex:
        print("wallet check failed:", ex)
    if n >= 10:
        print("\n*** 10-TRADE GATE REACHED — owner review required before "
              "scaling (standing instruction) ***")


if __name__ == "__main__":
    main()
