#!/usr/bin/env python3
"""kamino_arb_analyze.py — Phase 2: price per-tx arb P&L + cluster by searcher.

P&L rule: value net flows in USDC/USDT at $1, wSOL at that UTC day's Binance
close (cached). Txs whose nonzero net mints are all priced -> exact-ish P&L.
Others flagged complex=true (multi-token residual) and priced only on the
priced subset (lower bound, sign usually still right since residuals net ~0).

Outputs: kamino_arb_pnl.jsonl (per tx), prints searcher leaderboard.
"""
import json, time, collections, statistics
from pathlib import Path
import urllib.request

MON = Path(__file__).resolve().parent
DS = MON / "kamino_arb_dataset.jsonl"
OUT = MON / "kamino_arb_pnl.jsonl"
SOLCACHE = MON / "sol_daily_px.json"

USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
WSOL = "So11111111111111111111111111111111111111112"
STABLES = {USDC, USDT}


def sol_prices(days):
    cache = json.load(open(SOLCACHE)) if SOLCACHE.exists() else {}
    missing = [d for d in days if d not in cache]
    if missing:
        url = ("https://api.binance.com/api/v3/klines?symbol=SOLUSDT"
               "&interval=1d&limit=30")
        try:
            kl = json.load(urllib.request.urlopen(url, timeout=20))
            for k in kl:
                d = time.strftime("%Y-%m-%d", time.gmtime(k[0] / 1000))
                cache[d] = float(k[4])
            json.dump(cache, open(SOLCACHE, "w"))
        except Exception as e:
            print("binance px fetch failed:", e)
    return cache


def main():
    rows = [json.loads(l) for l in open(DS)]
    days = {time.strftime("%Y-%m-%d", time.gmtime(r["ts"])) for r in rows}
    px = sol_prices(days)
    out = open(OUT, "w")
    per_payer = collections.defaultdict(list)
    n_exact = 0
    for r in rows:
        d = time.strftime("%Y-%m-%d", time.gmtime(r["ts"]))
        sol_px = px.get(d)
        pnl = 0.0
        complex_ = False
        for mint, amt in r["net_by_mint"].items():
            if abs(amt) < 1e-9:
                continue
            if mint in STABLES:
                pnl += amt
            elif mint == WSOL and sol_px:
                pnl += amt * sol_px
            else:
                complex_ = True
        pnl += r["sol_net_lamports"] / 1e9 * (sol_px or 0)
        pnl -= r["fee_lamports"] / 1e9 * (sol_px or 0)
        exact = not complex_ and sol_px is not None
        n_exact += exact
        rec = {"sig": r["sig"], "ts": r["ts"], "payer": r["payer"],
               "pnl_usd": round(pnl, 4), "exact": exact,
               "n_transfers": r["n_transfers"]}
        out.write(json.dumps(rec) + "\n")
        per_payer[r["payer"]].append(pnl)
    out.close()

    print(f"n={len(rows)}  fully-priced={n_exact} ({100*n_exact/len(rows):.0f}%)")
    allp = [p for v in per_payer.values() for p in v]
    pos = sum(1 for p in allp if p > 0)
    print(f"tx-level: green={pos}/{len(allp)} ({100*pos/len(allp):.0f}%) "
          f"mean=${statistics.mean(allp):+.4f} median=${statistics.median(allp):+.4f} "
          f"max=${max(allp):+.2f} min=${min(allp):+.2f}")
    print(f"total est. captured across all searchers: ${sum(allp):+,.2f} over "
          f"{(max(r['ts'] for r in rows)-min(r['ts'] for r in rows))/86400:.1f} days")
    board = sorted(per_payer.items(), key=lambda kv: -sum(kv[1]))
    print("\nTOP 10 SEARCHERS by est. P&L:")
    print(f"{'searcher':<14}{'txs':>6}{'total$':>12}{'mean$':>9}{'green%':>7}")
    for p, v in board[:10]:
        g = sum(1 for x in v if x > 0)
        print(f"{p[:12]:<14}{len(v):>6}{sum(v):>+12,.2f}{statistics.mean(v):>+9.4f}"
              f"{100*g/len(v):>6.0f}%")
    print("\nBOTTOM 5:")
    for p, v in board[-5:]:
        g = sum(1 for x in v if x > 0)
        print(f"{p[:12]:<14}{len(v):>6}{sum(v):>+12,.2f}{statistics.mean(v):>+9.4f}"
              f"{100*g/len(v):>6.0f}%")


if __name__ == "__main__":
    main()
