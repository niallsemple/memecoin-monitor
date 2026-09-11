#!/usr/bin/env python3
"""Meteora DLMM LP-yield ranker.

The price side of aged memecoins is a coin flip (median multi-day return 0%).
The FEE side pays regardless of direction. This ranks aged, liquid, SOL-quoted
DLMM pools by what an LP position would actually earn:

    daily_fee_yield = fees_24h / tvl        (per day, on capital)
    annualized      = daily_fee_yield * 365 (the API's apr does similar)

Risk-adjusted against measurable death signals from daily OHLCV history:
    vol_alive_ratio  = last-day volume / peak-day volume  (dying pools -> 0)
    dd_from_ath      = current price / ATH - 1            (post-dump pools)
    days             = age in days

Output: meteora_lp_ranker_report.json + ranked console table.
"""
import json, time, urllib.request, urllib.error

API = "https://dlmm.datapi.meteora.ag"
MIN_AGE_H = 2.0
MIN_TVL = 25000
PAGES = 12
PAGE_SIZE = 50
MAX_HIST = 60
SOL_MINT = "So11111111111111111111111111111111111111112"


def get(path, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(API + path, headers={"User-Agent": "curl/8.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(1.5 * (i + 1)); continue
            return None
        except Exception:
            time.sleep(0.6 * (i + 1))
    return None


def candles_daily(addr, created_ms, now_ms):
    out, start, end = [], int(created_ms / 1000), int(now_ms / 1000)
    while start < end:
        ce = min(start + 25 * 86400, end)
        d = get(f"/pools/{addr}/ohlcv?timeframe=24h&start_time={start}&end_time={ce}")
        if d and d.get("data"):
            out.extend(d["data"])
        start = ce
        time.sleep(0.12)
    u = {c["timestamp"]: c for c in out}
    return [u[k] for k in sorted(u)]


def main():
    now_ms = int(time.time() * 1000)
    pools = []
    for page in range(1, PAGES + 1):
        d = get(f"/pools?sort_key=volume&order_by=desc&page={page}&page_size={PAGE_SIZE}")
        if not d or "data" not in d:
            break
        for p in d["data"]:
            try:
                if p.get("is_blacklisted"):
                    continue
                ty, tx = p.get("token_y") or {}, p.get("token_x") or {}
                if ty.get("address") != SOL_MINT:
                    continue
                age_h = (now_ms - (p.get("created_at") or 0)) / 3600000
                tvl = p.get("tvl") or 0
                if age_h < MIN_AGE_H or tvl < MIN_TVL:
                    continue
                # wide-arm gate (ANSEM post-mortem): DLMM positions cap at ~68
                # bins/tx, so effective width = 68 * binStep bps. Require binStep
                # >= 50 (0.5%/bin -> ~34% floor) so a wide arm is actually wide.
                bs = ((p.get("pool_config") or {}).get("bin_step")) or 0
                if bs < 50:
                    continue
                fees = p.get("fees") or {}
                f24 = fees.get("24h") or 0
                pools.append({
                    "address": p["address"], "name": p.get("name"),
                    "age_h": round(age_h, 1), "tvl": tvl,
                    "bin_step": bs,
                    "vol24": ((p.get("volume") or {}).get("24h")) or 0,
                    "fees24": f24,
                    "daily_fee_yield": f24 / tvl if tvl else 0,
                    "apr_api": p.get("apr"), "has_farm": p.get("has_farm"),
                    "holders_x": tx.get("holders"),
                    "fa_disabled": tx.get("freeze_authority_disabled"),
                    "created_at": p.get("created_at"),
                })
            except Exception:
                continue
        time.sleep(0.12)

    print(f"[scan] {len(pools)} aged SOL-quoted pools (tvl>=${MIN_TVL:,})")
    for p in pools[:MAX_HIST]:
        cs = candles_daily(p["address"], p["created_at"], now_ms)
        if len(cs) >= 2:
            vols = [c["volume"] for c in cs]
            peak = max(vols) if vols else 0
            hi = max((c["high"] for c in cs if c["high"]), default=0)
            p["days"] = len(cs)
            p["vol_alive_ratio"] = round(vols[-1] / peak, 4) if peak else 0
            p["dd_from_ath"] = round(cs[-1]["close"] / hi - 1, 4) if hi else 0
            # §393: recency metrics — the datapi returns a pool's EARLIEST
            # candles; a resurrected pool (dead Jun-Jul, alive Sep) showed
            # "28d age, IL~0, vol_alive 1.0" on dead history (XMR-SOL, found
            # 2026-09-09). All deployment gates must use RECENT candles only.
            now_s = now_ms / 1000
            recent21 = [c for c in cs if now_s - c["timestamp"] <= 21 * 86400]
            p["recent_days_21"] = len(recent21)
            p["live_days_21"] = sum(1 for c in recent21 if (c.get("volume") or 0) > 0)
            recent10 = [c for c in cs if now_s - c["timestamp"] <= 10 * 86400]
            p["max_hl_range_10d"] = round(
                max((c["high"] / c["low"] for c in recent10
                     if c.get("high") and c.get("low")), default=0), 3)
            p["_candles"] = cs
        else:
            p["days"] = len(cs); p["vol_alive_ratio"] = None; p["dd_from_ath"] = None

    # rank: fee yield with death-risk penalty, net of estimated IL drag
    for p in pools:
        y = p["daily_fee_yield"]
        pen = 1.0
        if p.get("vol_alive_ratio") is not None and p["vol_alive_ratio"] < 0.05:
            pen *= 0.3   # volume dying -> future fees won't match trailing 24h
        if p.get("dd_from_ath") is not None and p["dd_from_ath"] < -0.9:
            pen *= 0.5   # post-collapse
        if not p.get("fa_disabled"):
            pen *= 0.5   # freeze authority live = dev can freeze
        p["risk_adj_yield"] = y * pen

        # IL drag from daily candles: constant-product IL per day, 2*sqrt(k)/(1+k)-1.
        # DLMM concentrated positions suffer >= this; treat as a lower bound.
        # §393: RECENT candles only (last 10d) — dead-history candles hide real IL.
        drags = []
        cs = p.get("_candles") or []
        now_s = now_ms / 1000
        cs_recent = [c for c in cs if now_s - c["timestamp"] <= 10 * 86400]
        for i in range(1, len(cs_recent)):
            c0, c1 = cs_recent[i-1]["close"], cs_recent[i]["close"]
            if c0 and c1 and c0 > 0:
                k = c1 / c0
                drags.append(2 * (k ** 0.5) / (1 + k) - 1)
        if len(cs_recent) >= 5 and drags:
            recent = drags[-7:]
            p["il_daily_avg7"] = round(sum(recent) / len(recent), 5)
            p["il_worst_day"] = round(min(drags), 5)
            p["net_daily_lp"] = round(p["risk_adj_yield"] + p["il_daily_avg7"], 5)
        else:
            p["il_daily_avg7"] = None; p["il_worst_day"] = None
            p["net_daily_lp"] = None

    ranked = sorted(pools, key=lambda p: -(p["net_daily_lp"] if p["net_daily_lp"] is not None else p["risk_adj_yield"]))
    for p in ranked:
        p.pop("_candles", None)

    # Deployment-grade watchlist — two tiers (§394, 2026-09-09):
    # Tier S "spicy": the original §393 bar — net >= 2%/d, vol_alive >= 0.5.
    # Tier A "safe majors": same IL/recency/FA/calm gates, but yield gate
    # lowered to >= 0.15%/d net and vol_alive >= 0.05, plus TVL >= $100k.
    # Rationale: the 7-gate audit found safety and yield are mutually exclusive
    # in this market; tier A trades yield for stability and is deployed with
    # larger arms (rent economics fixed by size, see tier_a_lp_model.py).
    base_safe = [p for p in ranked
                 if p.get("days", 0) >= 30
                 and p.get("il_daily_avg7") is not None and p["il_daily_avg7"] > -0.01
                 and p.get("fa_disabled")
                 and p.get("net_daily_lp") is not None
                 and p.get("live_days_21", 0) >= 10
                 and p.get("max_hl_range_10d") and p["max_hl_range_10d"] < 2.0]
    tier_s = [dict(p, tier="S") for p in base_safe
              if p.get("vol_alive_ratio") is not None and p["vol_alive_ratio"] >= 0.5
              and p["net_daily_lp"] >= 0.02]
    tier_a = [dict(p, tier="A") for p in base_safe
              if p.get("vol_alive_ratio") is not None and p["vol_alive_ratio"] >= 0.05
              and p["net_daily_lp"] >= 0.0015
              and p.get("tvl", 0) >= 100000
              and p["net_daily_lp"] < 0.02]
    deploy_grade = sorted(tier_s + tier_a,
                          key=lambda p: -p["net_daily_lp"])
    with open("lp_watchlist.json", "w") as f:
        json.dump({"generated_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime()),
                   "criteria": "S: age>=30d, IL<1%/d(10d), volA>=0.5, fa_off, net>=2%/d, live21>=10, hl10<2x | A: same but volA>=0.05, net>=0.15%/d, tvl>=$100k",
                   "pools": deploy_grade}, f, indent=1)
    with open("lp_watchlist.jsonl", "a") as f:
        f.write(json.dumps({"t": now_ms / 1000, "n": len(deploy_grade),
                            "pools": [p["name"] for p in deploy_grade[:10]]}) + "\n")
    print(f"\n[deploy-grade] {len(deploy_grade)} pools qualify:")
    for p in deploy_grade[:10]:
        print(f"  {p['name'][:24]:24s} ${p['tvl']:>9,.0f} net {p['net_daily_lp']:+.2%}/d "
              f"IL {p['il_daily_avg7']:+.3%}/d age {p['days']}d")

    # forward ledger: daily snapshot of top ranks to measure yield decay
    with open("meteora_lp_track.jsonl", "a") as f:
        for p in ranked[:25]:
            f.write(json.dumps({
                "t": now_ms / 1000, "address": p["address"], "name": p["name"],
                "tvl": p["tvl"], "fees24": p["fees24"],
                "daily_fee_yield": round(p["daily_fee_yield"], 5),
                "risk_adj_yield": round(p["risk_adj_yield"], 5),
                "il_daily_avg7": p["il_daily_avg7"], "il_worst_day": p["il_worst_day"],
                "net_daily_lp": p["net_daily_lp"],
                "vol_alive_ratio": p.get("vol_alive_ratio"), "dd_from_ath": p.get("dd_from_ath"),
            }) + "\n")

    rep = {"generated_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime()),
           "note": ("daily_fee_yield = trailing 24h fees / TVL (trailing, not forward). "
                    "net_daily_lp = risk-adjusted yield + avg daily IL drag (last 7d, "
                    "constant-product lower bound; DLMM concentration makes real IL worse). "
                    "Penalties discount decaying volume, post-collapse pools, live freeze authority."),
           "pools": ranked}
    with open("meteora_lp_ranker_report.json", "w") as f:
        json.dump(rep, f, indent=1)

    print(f"\n{'pool':22s} {'tvl':>10s} {'fees24':>9s} {'yield/d':>8s} {'IL/d7':>8s} {'ILworst':>8s} {'net/d':>8s} {'volAlive':>8s} {'ddATH':>7s} {'age':>6s}")
    for p in ranked[:20]:
        va = f"{p['vol_alive_ratio']:.2f}" if p.get("vol_alive_ratio") is not None else "  -"
        dd = f"{p['dd_from_ath']:+.0%}" if p.get("dd_from_ath") is not None else "  -"
        il = f"{p['il_daily_avg7']:+.2%}" if p.get("il_daily_avg7") is not None else "  -"
        ilw = f"{p['il_worst_day']:+.1%}" if p.get("il_worst_day") is not None else "  -"
        net = f"{p['net_daily_lp']:+.2%}" if p.get("net_daily_lp") is not None else "  -"
        print(f"{p['name'][:22]:22s} ${p['tvl']:>9,.0f} ${p['fees24']:>8,.0f} "
              f"{p['daily_fee_yield']:>7.2%} {il:>8s} {ilw:>8s} {net:>8s} {va:>8s} {dd:>7s} {p['age_h']/24:>5.1f}d")

    netted = [p for p in ranked[:20] if p["net_daily_lp"] is not None]
    if netted:
        pos = [p for p in netted if p["net_daily_lp"] > 0]
        tot_tvl = sum(p["tvl"] for p in netted)
        wavg = sum(p["net_daily_lp"] * p["tvl"] for p in netted) / tot_tvl if tot_tvl else 0
        print(f"\ntop-20 net-of-IL: {len(pos)}/{len(netted)} positive; TVL-weighted net {wavg:+.3%}/day")
    return rep


if __name__ == "__main__":
    main()
