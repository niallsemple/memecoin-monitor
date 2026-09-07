#!/usr/bin/env python3
"""§446: birth-window buyer concentration — retroactive validation.

For each e2-trial mint: pull first ~60s of curve txs from RPC, attribute
buy/sell SOL per feePayer wallet, compute top1/top3 buy-volume share,
unique buyers, creator-buy share. Correlate with realized pnl.

Hypothesis: farmed launches show one wallet (or a tiny cluster) doing
most of the first-minute buying; organic winners show distributed flow.
"""
import json
import time
import urllib.request
from pathlib import Path

MON = Path(__file__).resolve().parent
_HK = (MON / "helius_key.txt").read_text().strip() if (MON / "helius_key.txt").exists() else ""
RPC = f"https://mainnet.helius-rpc.com/?api-key={_HK}" if _HK else "https://api.mainnet-beta.solana.com"

MINTS = {
    "5nUeZs7KkqKHNDX47bhgbaAyeNt9hVFT1muFRk8Apump": "9QimR9mocGFKHfrZ5bDbLfdAJ93qF4h3NqZBGfzijaBJ",
    "5vjQ6MVdhuwMENme7KBSVgjjyHah72FXn8i2CweXpump": "ABtxXYXcnHT7zGSKK7KGpRnDJkuL8W2eEAGHhky19v4G",
    "6kpX48Mg7Mpzzo2mn7eWNggqWoYCo4GWexiJJCeZpump": "7UUEzt2gzKWuAr4UrXGZeAemJFqRZQibtuMfGPPs2QU1",
    "86p2DpnL3ymwaR8MtaSZTg8CeFQwLz42moEANU18pump": "A3rUis8mtuTnPc9jmJLV78wMqcZKUj822sUUqtFX9LoM",
    "8JrCjNHXKcyjtAYxUmagRYygB62ooUZJrYHqR5MQpump": "53gBdzqV3RHRur6ktWiY25w4U1mGhfc2vbbkPc5TK8Rq",
    "ARt1UNA4BPPSu67GvqArQ12EVSM6zdUKkKN3wZD3pump": "9KwSfoGR9iBfgeUuks2PHoZVKVbJ8XhHBjCXJe5cdyGN",
    "EW4KWShwwhUCuHTUGiNYM1zt9vjEcUNhdVPrJPFKpump": "6UHAQKnUTzhF3C8JEdMQKr91Xxt6LftPSa8nP3TyHhn1",
    "FA9RHGuSnS94TLusAhiuAfDuir3DDGGcatrWoV4Bpump": "4JBvzhDGcdNvSD3vx3Gd8gEUKxwZnRB6jr9Q1guiuZHS",
    "HXTHzAwsrZ6dbUVPTmTCHFywAPoEirEpqXecdnb8pump": "C6XNahJi2vd2RJQ4W1qwH4ficcNWqwBYzN5GzVJ9Efhp",
    "31p5jLDjpzycXs37amr69UnDdDyzAj2AkPDnidqMpump": "9HJzeamAXiht33snPoSBt5jUFdvc4mwHs168s22bYYzT",
    "F2VJAXjjuyruNKepXMGGx3XhfJfagPuCQZZpNsQ5pump": "H1Up46UBGb4Mjhy63g9YRiFnRQN3LJPBPqPutozzxZoN",
}
WINDOW_S = 60


def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params}).encode()
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                RPC, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as r:
                out = json.loads(r.read())
            if "result" in out:
                return out["result"]
            time.sleep(0.4 * (attempt + 1))
        except Exception:
            time.sleep(0.4 * (attempt + 1))
    return None


def analyze(mint, curve):
    sigs = rpc("getSignaturesForAddress", [curve, {"limit": 60}]) or []
    sigs = [s for s in sigs if s.get("err") is None]
    sigs.reverse()  # ascending time
    if not sigs:
        return None
    t0 = sigs[0].get("blockTime")
    buys, sells = {}, {}
    n_tx = 0
    creator = None
    for i, s in enumerate(sigs):
        bt = s.get("blockTime")
        if bt is None or bt - t0 > WINDOW_S:
            break
        tx = rpc("getTransaction", [s["signature"], {
                 "encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
        if not tx:
            continue
        n_tx += 1
        msg = tx["transaction"]["message"]
        keys = [k["pubkey"] if isinstance(k, dict) else k
                for k in msg["accountKeys"]]
        if not keys:
            continue
        fp = keys[0]
        if i == 0:
            creator = fp
        meta = tx.get("meta") or {}
        # token delta for feePayer on this mint
        pre = sum(b.get("uiTokenAmount", {}).get("uiAmount") or 0
                  for b in meta.get("preTokenBalances", [])
                  if b.get("mint") == mint and b.get("owner") == fp)
        post = sum(b.get("uiTokenAmount", {}).get("uiAmount") or 0
                   for b in meta.get("postTokenBalances", [])
                   if b.get("mint") == mint and b.get("owner") == fp)
        # SOL delta for feePayer (exclude fee)
        sol_delta = 0.0
        try:
            idx = keys.index(fp)
            sol_delta = (meta["postBalances"][idx] -
                         meta["preBalances"][idx] +
                         (meta.get("fee") or 0)) / 1e9
        except Exception:
            pass
        if post > pre:  # buy
            buys[fp] = buys.get(fp, 0.0) + max(-sol_delta, 0.0)
        elif post < pre:  # sell
            sells[fp] = sells.get(fp, 0.0) + max(sol_delta, 0.0)
        time.sleep(0.05)
    tot_buy = sum(buys.values())
    if tot_buy <= 0:
        return None
    ranked = sorted(buys.values(), reverse=True)
    top1 = ranked[0] / tot_buy
    top3 = sum(ranked[:3]) / tot_buy
    creator_buy = buys.get(creator, 0.0) / tot_buy if creator else 0.0
    return {"mint": mint, "n_tx": n_tx, "n_buyers": len(buys),
            "n_sellers": len(sells), "tot_buy_sol": round(tot_buy, 4),
            "top1_share": round(top1, 4), "top3_share": round(top3, 4),
            "creator_buy_share": round(creator_buy, 4),
            "creator": creator,
            "top1_wallet": max(buys, key=buys.get)}


def main():
    pos = json.load(open(MON / "live_positions.json"))
    out = []
    for mint, curve in MINTS.items():
        r = analyze(mint, curve)
        if r:
            p = pos.get(mint, {})
            r["pnl_sol"] = p.get("pnl_sol")
            r["peak_mult"] = p.get("peak_mult")
            out.append(r)
            print(f"{mint[:8]:9} pnl={r['pnl_sol']!s:>9} peak={str(round(p.get('peak_mult') or 0,3)):>7} "
                  f"buyers={r['n_buyers']:>3} top1={r['top1_share']:>6} top3={r['top3_share']:>6} "
                  f"creator_buy={r['creator_buy_share']:>6} vol={r['tot_buy_sol']:>8}")
        else:
            print(f"{mint[:8]:9} NO DATA")
    with (MON / "birth_concentration.jsonl").open("a") as f:
        for r in out:
            f.write(json.dumps(r) + "\n")
    # summary split
    wins = [r for r in out if (r.get("pnl_sol") or 0) > 0]
    losses = [r for r in out if (r.get("pnl_sol") or 0) <= 0]
    def avg(rs, k):
        return round(sum(r[k] for r in rs) / len(rs), 4) if rs else None
    print("\n=== SUMMARY ===")
    print(f"winners n={len(wins)}: avg top1={avg(wins,'top1_share')} top3={avg(wins,'top3_share')} buyers={avg(wins,'n_buyers')} creator_buy={avg(wins,'creator_buy_share')}")
    print(f"losers  n={len(losses)}: avg top1={avg(losses,'top1_share')} top3={avg(losses,'top3_share')} buyers={avg(losses,'n_buyers')} creator_buy={avg(losses,'creator_buy_share')}")


if __name__ == "__main__":
    main()
