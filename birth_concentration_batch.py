#!/usr/bin/env python3
"""§446b: batch birth-window concentration over shadow-ledger closes.

Usage: python3 birth_concentration_batch.py <offset> <count>
Appends to birth_concentration_shadow.jsonl (skips mints already done).
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

MON = Path(__file__).resolve().parent
_HK = (MON / "helius_key.txt").read_text().strip() if (MON / "helius_key.txt").exists() else ""
RPC = f"https://mainnet.helius-rpc.com/?api-key={_HK}" if _HK else "https://api.mainnet-beta.solana.com"
WINDOW_S = 60
OUT = MON / "birth_concentration_shadow.jsonl"


def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params}).encode()
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                RPC, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as r:
                out = json.loads(r.read())
            if "result" in out:
                return out["result"]
            time.sleep(0.3 * (attempt + 1))
        except Exception:
            time.sleep(0.3 * (attempt + 1))
    return None


def analyze(mint, curve):
    sigs = rpc("getSignaturesForAddress", [curve, {"limit": 60}]) or []
    sigs = [s for s in sigs if s.get("err") is None]
    sigs.reverse()
    if not sigs:
        return None
    t0 = sigs[0].get("blockTime")
    buys, sells = {}, {}
    creator = None
    for i, s in enumerate(sigs):
        bt = s.get("blockTime")
        if bt is None or bt - t0 > WINDOW_S:
            break
        tx = rpc("getTransaction", [s["signature"], {
                 "encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
        if not tx:
            continue
        msg = tx["transaction"]["message"]
        keys = [k["pubkey"] if isinstance(k, dict) else k
                for k in msg["accountKeys"]]
        if not keys:
            continue
        fp = keys[0]
        if i == 0:
            creator = fp
        meta = tx.get("meta") or {}
        pre = sum(b.get("uiTokenAmount", {}).get("uiAmount") or 0
                  for b in meta.get("preTokenBalances", [])
                  if b.get("mint") == mint and b.get("owner") == fp)
        post = sum(b.get("uiTokenAmount", {}).get("uiAmount") or 0
                   for b in meta.get("postTokenBalances", [])
                   if b.get("mint") == mint and b.get("owner") == fp)
        sol_delta = 0.0
        try:
            idx = keys.index(fp)
            sol_delta = (meta["postBalances"][idx] -
                         meta["preBalances"][idx] +
                         (meta.get("fee") or 0)) / 1e9
        except Exception:
            pass
        if post > pre:
            buys[fp] = buys.get(fp, 0.0) + max(-sol_delta, 0.0)
        elif post < pre:
            sells[fp] = sells.get(fp, 0.0) + max(sol_delta, 0.0)
        time.sleep(0.03)
    tot_buy = sum(buys.values())
    if tot_buy <= 0:
        return None
    ranked = sorted(buys.values(), reverse=True)
    return {"mint": mint,
            "n_buyers": len(buys), "n_sellers": len(sells),
            "tot_buy_sol": round(tot_buy, 4),
            "top1_share": round(ranked[0] / tot_buy, 4),
            "top3_share": round(sum(ranked[:3]) / tot_buy, 4),
            "creator_buy_share": round(buys.get(creator, 0.0) / tot_buy, 4) if creator else None,
            "creator": creator,
            "top1_wallet": max(buys, key=buys.get),
            "top1_eq_creator": (max(buys, key=buys.get) == creator)}


def main():
    offset, count = int(sys.argv[1]), int(sys.argv[2])
    stride = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    # outcomes: last close per mint
    closes = {}
    for l in (MON / "shadow_ledger.jsonl").open():
        try:
            r = json.loads(l)
        except Exception:
            continue
        if r.get("status") == "closed" and r.get("ret") is not None:
            closes[r["mint"]] = r
    # curve map
    cmap = {}
    for l in (MON / "curves.jsonl").open():
        try:
            r = json.loads(l)
        except Exception:
            continue
        if r.get("mint") and r.get("bondingCurveKey"):
            cmap[r["mint"]] = r["bondingCurveKey"]
    done = set()
    if OUT.exists():
        for l in OUT.open():
            try:
                done.add(json.loads(l)["mint"])
            except Exception:
                pass
    mints = [m for m in closes if m in cmap and m not in done]
    batch = mints[offset::stride][:count]
    print(f"eligible={len(mints)} doing {len(batch)} (offset {offset} stride {stride})")
    with OUT.open("a") as f:
        for m in batch:
            r = analyze(m, cmap[m])
            if r:
                r["ret"] = closes[m].get("ret")
                r["peak"] = closes[m].get("peak")
                r["exit_reason"] = closes[m].get("exit_reason")
                f.write(json.dumps(r) + "\n")
                f.flush()
                print(f"{m[:8]} ret={r['ret']:>8} top1={r['top1_share']:>6} cb={r['creator_buy_share']!s:>6} buyers={r['n_buyers']:>3} vol={r['tot_buy_sol']:>8} t1=c:{r['top1_eq_creator']}")
            else:
                print(f"{m[:8]} NO DATA")


if __name__ == "__main__":
    main()
