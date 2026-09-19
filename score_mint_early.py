#!/usr/bin/env python3
"""score_mint_early.py — paper identity score for one mint (Mac stack).

Wraps existing memecoin-monitor primitives; does not invent new detection:
  creator_scan.creator_of / bonding-curve PDA
  first-WINDOW buyer concentration (birth_concentration style)
  prior launches from mfg_armed_births.jsonl
  overlap vs smart_wallets.json (wallet_vetter)

  python3 score_mint_early.py --json <mint> [<mint>...]
Paper only.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

MON = Path(__file__).resolve().parent
WINDOW_S = 60

import creator_scan as cs  # PDA + creator_of + RPC


def rpc(method, params, tries=4):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(
                cs.RPC, data=body, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=25) as r:
                out = json.loads(r.read())
            if "error" in out:
                last = out["error"]
                time.sleep(0.35 * (i + 1))
                continue
            return out.get("result")
        except Exception as e:
            last = str(e)
            time.sleep(0.35 * (i + 1))
    return None


def curve_addr(mint: str) -> str:
    pda = cs.find_pda([b"bonding-curve", cs.b58decode(mint)], cs.PUMP_PROGRAM)
    return cs.b58encode(pda)


def first_window_flow(mint: str, curve: str) -> dict:
    sigs = rpc("getSignaturesForAddress", [curve, {"limit": 80}]) or []
    sigs = [s for s in sigs if not s.get("err")]
    sigs.reverse()
    if not sigs:
        return {"ok": False, "reason": "no_sigs"}
    t0 = sigs[0].get("blockTime")
    buys, sells = {}, {}
    n_tx = 0
    for s in sigs:
        bt = s.get("blockTime")
        if bt is None or (t0 is not None and bt - t0 > WINDOW_S):
            break
        tx = rpc(
            "getTransaction",
            [s["signature"], {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
        )
        if not tx:
            continue
        n_tx += 1
        msg = tx["transaction"]["message"]
        keys = [k["pubkey"] if isinstance(k, dict) else k for k in msg["accountKeys"]]
        if not keys:
            continue
        fp = keys[0]
        meta = tx.get("meta") or {}
        pre = sum(
            b.get("uiTokenAmount", {}).get("uiAmount") or 0
            for b in meta.get("preTokenBalances", [])
            if b.get("mint") == mint and b.get("owner") == fp
        )
        post = sum(
            b.get("uiTokenAmount", {}).get("uiAmount") or 0
            for b in meta.get("postTokenBalances", [])
            if b.get("mint") == mint and b.get("owner") == fp
        )
        sol_delta = 0.0
        try:
            idx = keys.index(fp)
            sol_delta = (
                meta["postBalances"][idx] - meta["preBalances"][idx] + (meta.get("fee") or 0)
            ) / 1e9
        except Exception:
            pass
        if post > pre:
            buys[fp] = buys.get(fp, 0.0) + max(-sol_delta, 0.0)
        elif post < pre:
            sells[fp] = sells.get(fp, 0.0) + max(sol_delta, 0.0)
        time.sleep(0.05)

    tot = sum(buys.values()) or 0.0
    ranked = sorted(buys.items(), key=lambda kv: -kv[1])
    top1 = ranked[0][1] / tot if ranked and tot else 0.0
    top3 = sum(v for _, v in ranked[:3]) / tot if ranked and tot else 0.0
    return {
        "ok": True,
        "window_s": WINDOW_S,
        "n_tx": n_tx,
        "n_buyers": len(buys),
        "n_sellers": len(sells),
        "tot_buy_sol": round(tot, 4),
        "top1_share": round(top1, 4),
        "top3_share": round(top3, 4),
        "top_buyers": [{"wallet": w, "sol": round(s, 4)} for w, s in ranked[:5]],
    }


def creator_history(creator):
    path = MON / "mfg_armed_births.jsonl"
    if not creator or not path.exists():
        return {"prior_launches": 0, "symbols": []}
    n, syms = 0, []
    with path.open() as f:
        for line in f:
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("creator") == creator:
                n += 1
                if r.get("symbol"):
                    syms.append(r["symbol"])
    return {"prior_launches": n, "symbols": syms[-8:]}


def smart_overlap(wallets):
    path = MON / "smart_wallets.json"
    if not path.exists() or not wallets:
        return {"hits": [], "n_hits": 0, "db_size": 0}
    db = (json.loads(path.read_text()).get("wallets")) or {}
    hits = []
    for w in wallets:
        if w in db:
            v = db[w]
            hits.append(
                {
                    "wallet": w,
                    "verdict": v.get("verdict"),
                    "roi_proxy": v.get("roi_proxy"),
                    "win_rate": v.get("win_rate"),
                    "archetype": v.get("archetype"),
                }
            )
    return {"hits": hits, "n_hits": len(hits), "db_size": len(db)}


def flags_from(score):
    f = []
    flow = score.get("first_window") or {}
    hist = score.get("creator_history") or {}
    if hist.get("prior_launches", 0) >= 3:
        f.append("serial_creator")
    if flow.get("ok") and (flow.get("top1_share") or 0) >= 0.55:
        f.append("concentrated_early_buy")
    if flow.get("ok") and (flow.get("n_buyers") or 0) >= 8 and (flow.get("top1_share") or 1) <= 0.35:
        f.append("distributed_early_flow")
    if (score.get("smart_overlap") or {}).get("n_hits", 0) > 0:
        f.append("smart_wallet_overlap")
    if not score.get("creator"):
        f.append("no_curve_creator")
    return f


def score_mint(mint: str) -> dict:
    out = {
        "mint": mint,
        "source": "memecoin-monitor/score_mint_early",
        "paper_only": True,
        "ts": time.time(),
    }
    try:
        creator = cs.creator_of(mint)
    except Exception as e:
        creator = None
        out["creator_error"] = str(e)[:160]
    out["creator"] = creator
    out["creator_history"] = creator_history(creator)
    try:
        curve = curve_addr(mint)
        out["bonding_curve"] = curve
        out["first_window"] = first_window_flow(mint, curve)
    except Exception as e:
        out["bonding_curve"] = None
        out["first_window"] = {"ok": False, "reason": str(e)[:160]}
    tops = [b["wallet"] for b in (out.get("first_window") or {}).get("top_buyers") or []]
    out["smart_overlap"] = smart_overlap(tops)
    out["flags"] = flags_from(out)
    if "serial_creator" in out["flags"] and "concentrated_early_buy" in out["flags"]:
        out["label"] = "AVOID_farmish"
    elif "distributed_early_flow" in out["flags"]:
        out["label"] = "WATCH_organicish"
    elif "smart_wallet_overlap" in out["flags"]:
        out["label"] = "WATCH_smart_overlap"
    else:
        out["label"] = "WATCH"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mints", nargs="+")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rows = [score_mint(m) for m in args.mints]
    if args.json:
        print(json.dumps(rows if len(rows) > 1 else rows[0], indent=2))
        return
    for r in rows:
        fw = r.get("first_window") or {}
        print(
            f"{r['mint'][:12]}… creator={(r.get('creator') or '?')[:12]}… "
            f"priors={r['creator_history']['prior_launches']} "
            f"buyers={fw.get('n_buyers')} top1={fw.get('top1_share')} "
            f"smart_hits={r['smart_overlap']['n_hits']} "
            f"flags={r['flags']} label={r['label']}"
        )


if __name__ == "__main__":
    main()
