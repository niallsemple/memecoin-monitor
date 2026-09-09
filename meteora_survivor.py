#!/usr/bin/env python3
"""Meteora DLMM survivor scanner + aged-coin hold backtest.

Thesis: coins that survive past the newborn rug window (~2h) with stable
liquidity are holdable during dead tape. Meteora's free datapi backfills
full per-pool history (OHLCV from birth), so we can measure the survivor
edge without waiting weeks for our own collector.

Phases:
  1. SCAN  - page /pools sorted by 24h volume, keep SOL-quoted meme pools
             aged >= MIN_AGE_H, tvl >= MIN_TVL, not blacklisted.
  2. HIST  - pull daily OHLCV from birth for each candidate.
  3. BACKT - simulate "buy survivor at close of its first day, hold":
             distribution of forward returns, rug rate (price collapse
             >95%), and which observable filters would have helped.
  4. WATCH - live watchlist: survivors with volume still alive today.

Output: meteora_survivor_report.json + console summary.
"""
import json, time, sys, urllib.request, urllib.error

API = "https://dlmm.datapi.meteora.ag"
MIN_AGE_H = 2.0
MIN_TVL = 25000
PAGES = 12            # 12 x 50 = 600 pools scanned (top by 24h volume)
PAGE_SIZE = 50
MAX_HIST = 60         # pools to pull history for
SOL_MINT = "So11111111111111111111111111111111111111112"
REQ_GAP = 0.12        # stay well under 30 req/s


def get(path, retries=3):
    url = API + path
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(1.5 * (i + 1))
                continue
            return None
        except Exception:
            time.sleep(0.6 * (i + 1))
    return None


def scan_candidates(now_ms):
    cands = []
    for page in range(1, PAGES + 1):
        d = get(f"/pools?sort_key=volume&order_by=desc&page={page}&page_size={PAGE_SIZE}")
        if not d or "data" not in d:
            break
        for p in d["data"]:
            try:
                if p.get("is_blacklisted"):
                    continue
                # SOL-quoted only (token_y = SOL), exclude majors/stables on x side
                ty = p.get("token_y") or {}
                tx = p.get("token_x") or {}
                if ty.get("address") != SOL_MINT:
                    continue
                age_h = (now_ms - (p.get("created_at") or 0)) / 3600000
                tvl = p.get("tvl") or 0
                if age_h < MIN_AGE_H or tvl < MIN_TVL:
                    continue
                vol24 = ((p.get("volume") or {}).get("24h")) or 0
                cands.append({
                    "address": p["address"], "name": p.get("name"),
                    "age_h": round(age_h, 2), "tvl": tvl, "vol24": vol24,
                    "holders_x": tx.get("holders"),
                    "fa_disabled": tx.get("freeze_authority_disabled"),
                    "created_at": p.get("created_at"),
                    "fee_tvl_24h": ((p.get("fee_tvl_ratio") or {}).get("24h")),
                })
            except Exception:
                continue
        time.sleep(REQ_GAP)
    return cands


def pull_daily_history(addr, created_ms, now_ms):
    """Daily candles from birth to now. Chunked at 25d per request."""
    candles = []
    start = int(created_ms / 1000)
    end = int(now_ms / 1000)
    while start < end:
        chunk_end = min(start + 25 * 86400, end)
        d = get(f"/pools/{addr}/ohlcv?timeframe=24h&start_time={start}&end_time={chunk_end}")
        if d and d.get("data"):
            candles.extend(d["data"])
        start = chunk_end
        time.sleep(REQ_GAP)
    # dedupe by timestamp, sort
    uniq = {c["timestamp"]: c for c in candles}
    return [uniq[k] for k in sorted(uniq)]


def backtest(cands, now_ms):
    results = []
    for c in cands[:MAX_HIST]:
        candles = pull_daily_history(c["address"], c["created_at"], now_ms)
        if len(candles) < 2:
            c["hist"] = "insufficient"
            results.append(c)
            continue
        # entry: close of first candle (end of birth day); exit: latest close
        e, x = candles[0], candles[-1]
        if not e["close"] or e["close"] <= 0:
            c["hist"] = "bad_entry_px"
            results.append(c)
            continue
        ret = x["close"] / e["close"] - 1
        hi = max(c2["high"] for c2 in candles if c2["high"])
        dd_now = x["close"] / hi - 1 if hi else 0
        day_vols = [c2["volume"] for c2 in candles]
        peak_vol = max(day_vols) if day_vols else 0
        vol_alive = (day_vols[-1] / peak_vol) if peak_vol else 0
        c.update({
            "hist": "ok", "days": len(candles),
            "ret_since_d0close": round(ret, 4),
            "dd_from_ath": round(dd_now, 4),
            "vol_alive_ratio": round(vol_alive, 4),
            "rugged": ret <= -0.95,
        })
        results.append(c)
    return results


def append_track(watch, now_ms):
    """Forward-tracking ledger: one row per watchlist member per run.
    Entry = first qualification; forward returns measured on later runs."""
    recs = []
    for r in watch:
        recs.append({
            "t": now_ms / 1000, "address": r["address"], "name": r["name"],
            "age_h": r["age_h"], "tvl": r["tvl"], "vol24": r["vol24"],
            "holders_x": r["holders_x"],
            "ret_since_d0close": r.get("ret_since_d0close"),
            "dd_from_ath": r.get("dd_from_ath"),
        })
    with open("meteora_survivor_track.jsonl", "a") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
    return len(recs)


def main():
    now_ms = int(time.time() * 1000)
    print(f"[scan] paging top {PAGES * PAGE_SIZE} DLMM pools by 24h volume...")
    cands = scan_candidates(now_ms)
    print(f"[scan] {len(cands)} survivor candidates (age>=2h, tvl>=${MIN_TVL:,}, SOL-quoted)")
    print(f"[hist] pulling daily candles for up to {MAX_HIST}...")
    results = backtest(cands, now_ms)

    ok = [r for r in results if r.get("hist") == "ok"]
    rep = {"generated_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime()),
           "survivorship_biased": True,
           "bias_note": ("Sample = today's top-600 pools by 24h volume. Dead/rugged pools "
                         "are absent, so backtest returns overstate the edge. Use "
                         "meteora_survivor_track.jsonl forward ledger for the unbiased read."),
           "n_scanned": len(cands), "n_with_history": len(ok), "results": results}
    with open("meteora_survivor_report.json", "w") as f:
        json.dump(rep, f, indent=1)

    if ok:
        n = len(ok)
        wins = sum(1 for r in ok if r["ret_since_d0close"] > 0)
        rugs = sum(1 for r in ok if r["rugged"])
        avg = sum(r["ret_since_d0close"] for r in ok) / n
        print(f"\n[backtest] buy-at-d0-close-and-hold, n={n}")
        print(f"  winrate={wins/n:.0%}  avg_ret={avg:+.1%}  rug(-95%)={rugs} ({rugs/n:.0%})")
        # does a 'volume alive' filter help?
        alive = [r for r in ok if r["vol_alive_ratio"] >= 0.05 and not r["rugged"]]
        if alive:
            wa = sum(1 for r in alive if r["ret_since_d0close"] > 0)
            aa = sum(r["ret_since_d0close"] for r in alive) / len(alive)
            print(f"  [filter: day_vol>=5% of peak] n={len(alive)} win={wa/len(alive):.0%} avg={aa:+.1%}")
        ok.sort(key=lambda r: -r["ret_since_d0close"])
        print("  top5:", [(r["name"], f"{r['ret_since_d0close']:+.0%}") for r in ok[:5]])
        print("  bot5:", [(r["name"], f"{r['ret_since_d0close']:+.0%}") for r in ok[-5:]])

    watch = [r for r in results if r.get("hist") == "ok"
             and not r["rugged"] and r["vol_alive_ratio"] >= 0.05 and r["tvl"] >= MIN_TVL]
    watch.sort(key=lambda r: -(r["vol24"] or 0))
    n_tracked = append_track(watch, now_ms)
    print(f"\n[watchlist] {len(watch)} holdable survivors right now ({n_tracked} rows -> track ledger):")
    for r in watch[:10]:
        print(f"  {r['name']:22s} tvl=${r['tvl']:>10,.0f} vol24=${r['vol24']:>10,.0f} "
              f"age={r['age_h']:.0f}h holders={r['holders_x']} retD0={r['ret_since_d0close']:+.0%}")
    return rep


if __name__ == "__main__":
    main()
