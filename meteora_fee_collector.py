#!/usr/bin/env python3
"""
meteora_fee_collector.py — snapshot top Meteora DLMM pools by 30m fee/TVL.

Purpose (protocol-payout research, ChatGPT memo #32 priority 2):
  Instead of predicting memecoin DIRECTION, predict FEE GENERATION and
  test LP fee-capture: does fee_tvl_ratio at short windows stay high long
  enough after launch for a narrow-range LP to beat IL + rug loss?

Each run appends one JSONL row per pool to meteora_fee_snapshots.jsonl:
  {t, pool, name, launchpad, age_h, tvl, dyn_fee_pct, base_fee_pct,
   bin_step, ftr_30m, ftr_1h, ftr_24h, vol_30m, vol_1h, fees_30m, fees_24h,
   x_holders, x_mc, x_verified, freeze_disabled}

Sources top ~150 pools by 30m fee/TVL (where live action is) plus any pool
seen in the last cycle that's still young (<48h) — so decay trajectories of
recently-hot pools keep being tracked even after they drop off the board.

Usage: python3 meteora_fee_collector.py
"""
import json, os, time, urllib.request

MON = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(MON, "meteora_fee_snapshots.jsonl")
API = "https://dlmm.datapi.meteora.ag/pools"
UA = {"User-Agent": "darwin-labs/1.0"}
TOP_PAGES = 15         # 15 x ~10 = ~150 hottest pools (API caps page size at 10)
YOUNG_H = 48


def get(url, tries=3):
    err = None
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except Exception as e:
            err = e
            time.sleep(2 ** a)
    print(f"api fail: {err}")
    return None


def snap(p, now):
    ftr = p.get("fee_tvl_ratio") or {}
    vol = p.get("volume") or {}
    fees = p.get("fees") or {}
    cfg = p.get("pool_config") or {}
    tx = p.get("token_x") or {}
    return {
        "t": now,
        "pool": p.get("address"),
        "name": p.get("name"),
        "launchpad": p.get("launchpad"),
        "age_h": round((now - (p.get("created_at") or now * 1000) / 1000) / 3600, 2),
        "tvl": p.get("tvl"),
        "dyn_fee_pct": p.get("dynamic_fee_pct"),
        "base_fee_pct": cfg.get("base_fee_pct"),
        "bin_step": cfg.get("bin_step"),
        "ftr_30m": ftr.get("30m"), "ftr_1h": ftr.get("1h"), "ftr_24h": ftr.get("24h"),
        "vol_30m": vol.get("30m"), "vol_1h": vol.get("1h"),
        "fees_30m": fees.get("30m"), "fees_24h": fees.get("24h"),
        "x_holders": tx.get("holders"),
        "x_mc": tx.get("market_cap"),
        "x_verified": tx.get("is_verified"),
        "freeze_disabled": tx.get("freeze_authority_disabled"),
    }


def main():
    now = time.time()
    seen = {}

    # 1) hottest pools right now
    for pg in range(1, TOP_PAGES + 1):
        q = get(f"{API}?page={pg}&limit=50&sort_key=fee_tvl_ratio&order_by=desc")
        if not q:
            break
        for p in q.get("data") or []:
            if p.get("address"):
                seen[p["address"]] = p

    # 2) keep tracking recently-hot young pools (decay trajectories)
    young = set()
    if os.path.exists(OUT):
        cutoff = now - 6 * 3600
        with open(OUT) as f:
            for l in f:
                try:
                    r = json.loads(l)
                except Exception:
                    continue
                if r.get("t", 0) > cutoff and (r.get("age_h") or 1e9) < YOUNG_H:
                    young.add(r.get("pool"))
    for addr in sorted(young - set(seen)):
        q = get(f"{API}/{addr}")
        p = (q or {}).get("data") if isinstance(q, dict) else None
        if isinstance(p, dict) and p.get("address"):
            seen[p["address"]] = p

    n = 0
    with open(OUT, "a") as f:
        for p in seen.values():
            f.write(json.dumps(snap(p, now)) + "\n")
            n += 1
    print(f"meteora snapshot: {n} pools ({len(young - set(seen))} young tracked)")

    # ---- Project 0 Orders watch (memo #32 priority 1): feature shipped in
    # mrgn-0.1.8 (mainnet ETA late March 2026) but ZERO Order accounts found
    # on mainnet 2026-09-08. Count each cycle; when >0, build the keeper
    # economics decode (surplus + rent + execution_max_fee per execution).
    try:
        key = open(os.path.join(MON, "helius_key.txt")).read().strip()
        url = f"https://mainnet.helius-rpc.com/?api-key={key}"
        body = json.dumps({"jsonrpc": "2.0", "id": 1,
                           "method": "getProgramAccounts",
                           "params": ["MFv2hWf31Z9kbCa1snEPYctwafyhdvnV7FZnsebVacA",
                                      {"filters": [{"memcmp": {"offset": 0,
                                       "bytes": "PXZJQQ2HEmx"}}],   # account:Order
                                       "dataSlice": {"offset": 0, "length": 0},
                                       "encoding": "base64"}]}).encode()
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            q = json.load(r)
        cnt = len(q.get("result") or [])
        with open(os.path.join(MON, "p0_orders_watch.jsonl"), "a") as f:
            f.write(json.dumps({"t": now, "order_accounts": cnt}) + "\n")
        print(f"p0 orders watch: {cnt} Order accounts on mainnet"
              + ("  *** FEATURE LIVE — START KEEPER DECODE ***" if cnt else ""))
    except Exception as e:
        print(f"p0 orders watch failed: {str(e)[:80]}")

    # quick leaderboard for logs
    top = sorted(seen.values(),
                 key=lambda p: (p.get("fee_tvl_ratio") or {}).get("30m") or 0,
                 reverse=True)[:5]
    for p in top:
        ftr = (p.get("fee_tvl_ratio") or {}).get("30m") or 0
        age = (now - (p.get("created_at") or 0) / 1000) / 3600
        print(f"  {p.get('name','?')[:22]:<24} f/T30m={ftr*100:6.2f}%  "
              f"age={age:6.1f}h  tvl=${p.get('tvl') or 0:,.0f}  "
              f"launchpad={p.get('launchpad')}")


if __name__ == "__main__":
    main()
