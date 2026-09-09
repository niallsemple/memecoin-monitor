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
                fees = p.get("fees") or {}
                f24 = fees.get("24h") or 0
                pools.append({
                    "address": p["address"], "name": p.get("name"),
                    "age_h": round(age_h, 1), "tvl": tvl,
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
        else:
            p["days"] = len(cs); p["vol_alive_ratio"] = None; p["dd_from_ath"] = None

    # rank: fee yield with death-risk penalty
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

    ranked = sorted(pools, key=lambda p: -p["risk_adj_yield"])
    rep = {"generated_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime()),
           "note": ("daily_fee_yield = trailing 24h fees / TVL. Trailing, not forward; "
                    "volume-alive and ATH-drawdown penalties discount pools whose fee "
                    "stream is decaying. IL risk not included."),
           "pools": ranked}
    with open("meteora_lp_ranker_report.json", "w") as f:
        json.dump(rep, f, indent=1)

    print(f"\n{'pool':22s} {'tvl':>10s} {'fees24':>9s} {'yield/d':>8s} {'APR':>7s} {'volAlive':>8s} {'ddATH':>7s} {'age':>6s} {'hold':>7s}")
    for p in ranked[:20]:
        va = f"{p['vol_alive_ratio']:.2f}" if p.get("vol_alive_ratio") is not None else "  -"
        dd = f"{p['dd_from_ath']:+.0%}" if p.get("dd_from_ath") is not None else "  -"
        apr = f"{p['apr_api']:.0f}%" if p.get("apr_api") else "  -"
        print(f"{p['name'][:22]:22s} ${p['tvl']:>9,.0f} ${p['fees24']:>8,.0f} "
              f"{p['daily_fee_yield']:>7.2%} {apr:>7s} {va:>8s} {dd:>7s} {p['age_h']/24:>5.1f}d {p.get('holders_x') or 0:>7}")

    tot_tvl = sum(p["tvl"] for p in ranked[:20])
    wavg = sum(p["risk_adj_yield"] * p["tvl"] for p in ranked[:20]) / tot_tvl if tot_tvl else 0
    print(f"\ntop-20 TVL-weighted risk-adj daily yield: {wavg:.3%}  (~{wavg*365:.0%} annualized)")
    return rep


if __name__ == "__main__":
    main()
