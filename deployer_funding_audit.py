#!/usr/bin/env python3
"""deployer_funding_audit.py — §216: LOO deployer-funding audit.

Question: does the DEPLOYER's funding wallet separate drains from
normal mints? Identity survives wallet freshness — capital must come
from somewhere, and §198 showed drain-crew funding loops.

For every closed paper mint + live book mint:
  creator  = curves.jsonl creation event traderPublicKey
  funder   = source of the creator wallet's first inbound SOL (>0.05)
             (creator wallets are fresh — few sigs, cheap to walk)
  LOO-hit  = funder in drainer_blocklist, excluding entries whose
             recorded origin mint is the mint under test

Resumable: funder_cache.json persists creator->funder across runs.
Usage: python3 deployer_funding_audit.py [creators_per_run]
"""
import json, sys, time, urllib.request
from collections import defaultdict
from pathlib import Path

MON = Path(__file__).resolve().parent
RPC = "https://mainnet.helius-rpc.com/?api-key=" + \
    (MON / "helius_key.txt").read_text().strip()
CACHE_F = MON / "funder_cache.json"
DRAIN_RET = -0.70
MIN_FUND_SOL = 0.05


def rpc(method, params, tries=3):
    body = json.dumps({"jsonrpc": "2.0", "id": 1,
                       "method": method, "params": params}).encode()
    for a in range(tries):
        try:
            req = urllib.request.Request(RPC, data=body,
                                         headers={"Content-Type":
                                                  "application/json"})
            return json.load(urllib.request.urlopen(req, timeout=25))
        except Exception:
            time.sleep(1.0 * (a + 1))
    return {}


def find_funder(creator):
    # paginate to the TRUE oldest txs — funding is the first tx; a
    # single limit=100 page misses it on active wallets (§216 bug).
    sigs = []
    before = None
    for _page in range(4):                    # cap 4000 sigs
        params = [creator, {"limit": 1000}]
        if before:
            params[1]["before"] = before
        page = rpc("getSignaturesForAddress", params).get("result") or []
        sigs.extend(page)
        if len(page) < 1000:
            break
        before = page[-1]["signature"]
        time.sleep(0.25)
    if not sigs:
        return None, "no sigs"
    for s in list(reversed(sigs))[:4]:
        if s.get("err"):
            continue
        tx = rpc("getTransaction",
                 [s["signature"], {"encoding": "json",
                                   "maxSupportedTransactionVersion": 0}]
                 ).get("result")
        time.sleep(0.25)
        if not tx:
            continue
        keys = [k if isinstance(k, str) else k["pubkey"]
                for k in tx["transaction"]["message"]["accountKeys"]]
        if creator not in keys:
            continue
        i = keys.index(creator)
        d = (tx["meta"]["postBalances"][i]
             - tx["meta"]["preBalances"][i]) / 1e9
        if d > MIN_FUND_SOL:
            for j, k in enumerate(keys):
                dj = (tx["meta"]["postBalances"][j]
                      - tx["meta"]["preBalances"][j]) / 1e9
                if dj < -MIN_FUND_SOL and k != creator:
                    return k, s["signature"]
    return None, "no inbound >0.05 SOL in oldest txs"


def main():
    per_run = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    # universe
    outcomes = {}
    for src in ("mfg_paper_trades_s60nm5fr.jsonl", "mfg_paper_trades.jsonl"):
        p = MON / src
        if p.exists():
            for line in p.open():
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("mint") and r.get("status") == "closed":
                    outcomes[r["mint"]] = ("paper", r.get("ret"))
    pos = json.loads((MON / "live_positions.json").read_text())
    for m, p in pos.items():
        if not p.get("open"):
            outcomes[m] = ("live", p.get("pnl_sol", 0) / max(p.get("size_sol", 1), 1e-9))
    # creators
    creators = {}
    for line in (MON / "curves.jsonl").open():
        if '"create"' not in line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("txType") == "create" and r.get("mint") in outcomes:
            creators[r["mint"]] = r.get("traderPublicKey")
    missing = [m for m in outcomes if m not in creators]
    print(f"universe {len(outcomes)} mints; creator known for {len(creators)}"
          f" (missing {len(missing)})")
    # blocklist + LOO origin map
    bl = json.loads((MON / "drainer_blocklist.json").read_text())
    blw = set()
    origin = {}
    for sec in ("masters", "killers", "feeders", "funded_next_gen"):
        for w, meta in bl.get(sec, {}).items():
            blw.add(w)
            if isinstance(meta, dict) and meta.get("mint"):
                origin.setdefault(w, set()).add(meta["mint"])
    cache = json.loads(CACHE_F.read_text()) if CACHE_F.exists() else {}
    todo = sorted({c for c in creators.values()
                   if c and not cache.get(c, {}).get("funder")})
    done = 0
    for c in todo[:per_run]:
        f, sig = find_funder(c)
        cache[c] = {"funder": f, "sig": sig}
        done += 1
        if done % 5 == 0:
            CACHE_F.write_text(json.dumps(cache))   # incremental
        time.sleep(0.25)
    CACHE_F.write_text(json.dumps(cache))
    print(f"resolved {done} funders this run; cache {len(cache)}")
    if todo[per_run:]:
        print(f"{len(todo)-per_run} creators remaining — rerun to continue")
        return
    # analysis
    rows = []
    for m, (kind, ret) in outcomes.items():
        c = creators.get(m)
        if not c or c not in cache:
            continue
        f = cache[c].get("funder")
        loo_bl = {w for w in blw if m not in origin.get(w, set())}
        rows.append({"mint": m, "kind": kind, "ret": ret,
                     "creator": c, "funder": f,
                     "funder_known": f in loo_bl if f else False,
                     "drain": (ret is not None and (
                         ret <= DRAIN_RET if kind == "paper"
                         else ret <= -0.5))})
    drains = [r for r in rows if r["drain"]]
    normals = [r for r in rows if not r["drain"]]
    d_hit = sum(1 for r in drains if r["funder_known"])
    n_hit = sum(1 for r in normals if r["funder_known"])
    print(f"\n=== DEPLOYER-FUNDING LOO AUDIT ({len(rows)} mints) ===")
    print(f"drains:  {d_hit}/{len(drains)} funded by known-bad wallets")
    print(f"normals: {n_hit}/{len(normals)} (FP)")
    print("\ndrain detail:")
    for r in drains:
        print(f"  {r['mint'][:10]:12s} ret={r['ret']:+.2f} "
              f"creator={r['creator'][:10]} funder={(r['funder'] or '?')[:10]}"
              f" {'<<< KNOWN' if r['funder_known'] else ''}")
    (MON / "deployer_funding_audit.json").write_text(
        json.dumps(rows, indent=1))
    print(f"\nwrote deployer_funding_audit.json ({len(rows)} rows)")


if __name__ == "__main__":
    main()
