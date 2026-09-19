#!/usr/bin/env python3
"""wallet_vetter.py — build the smart-wallet DB from the trade ledger.

Streams mfg_wallet_trades.jsonl (wallet/side/sol/t per trade) and computes
per-wallet round-trip stats, then applies the vetting gates from
memecoin-research/05-synthesis.md (Q3 + copy-trading pass):

  REJECT  median hold < 2 min         -> sniper/insider bot, uncopyable (Cielo rule)
  REJECT  round trips < 30            -> insufficient history (wash-risk)
  REJECT  win rate > 80%              -> too good: insider/bot/wash flag
  COPYABLE win 40-75%, roi_proxy > 0, span >= 14d, 5-20 trades/day
  WATCH   everything else with >= 30 trips

roi_proxy = total sell SOL / total buy SOL - 1 across round trips.
(The ledger has SOL legs, not token amounts — this is a proxy, honest
about it, and conservative since partial sells undercount.)

Usage:
  python3 wallet_vetter.py [--limit N] [--out smart_wallets.json]
  python3 wallet_vetter.py --ledger broad_trades.jsonl \
      --out smart_wallets_broad.json   # graduated-token feed
"""
import argparse
import json
import statistics as st
import time
from collections import defaultdict
from pathlib import Path

MON = Path(__file__).resolve().parent

MIN_TRIPS = 30
MIN_SPAN_D = 14
COPY_WIN_LO, COPY_WIN_HI, REJECT_WIN = 0.40, 0.75, 0.80
SNIPER_HOLD_MIN = 2.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="cap ledger lines (testing)")
    ap.add_argument("--min-span-days", type=float, default=MIN_SPAN_D,
                    help="COPYABLE longevity gate; ledger currently spans "
                         "~13d, so pass 7 for interim builds")
    ap.add_argument("--out", default=str(MON / "smart_wallets.json"))
    ap.add_argument("--ledger", default=str(MON / "mfg_wallet_trades.jsonl"),
                    help="trade ledger to vet (broad_trades.jsonl for the "
                         "graduated-token feed)")
    a = ap.parse_args()
    ledger = Path(a.ledger)

    # wallet -> mint -> {"buy_sol":, "sell_sol":, "first_buy":, "last_sell":}
    legs = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, None, None]))
    t0 = time.time()
    n = 0
    with ledger.open() as f:
        for line in f:
            n += 1
            if a.limit and n > a.limit:
                break
            try:
                r = json.loads(line)
            except Exception:
                continue
            w, m, side = r.get("wallet"), r.get("mint"), r.get("side")
            t, sol = r.get("t"), r.get("sol")
            if not (w and m and side and t and isinstance(sol, (int, float))):
                continue
            L = legs[w][m]
            if side == "buy":
                L[0] += sol
                L[2] = t if L[2] is None else min(L[2], t)
            elif side == "sell":
                L[1] += sol
                L[3] = t if L[3] is None else max(L[3], t)
            if n % 2_000_000 == 0:
                print(f"  …{n/1e6:.0f}M lines, {len(legs)} wallets, "
                      f"{time.time()-t0:.0f}s", flush=True)

    db, rej = {}, defaultdict(int)
    for w, mints in legs.items():
        trips = [(m, L) for m, L in mints.items() if L[0] > 0 and L[1] > 0]
        if len(trips) < MIN_TRIPS:
            rej["few_trips"] += 1
            continue
        wins = sum(1 for _, L in trips if L[1] > L[0])
        win_rate = wins / len(trips)
        roi = sum(L[1] for _, L in trips) / max(1e-12, sum(L[0] for _, L in trips)) - 1
        holds = [(L[3] - L[2]) / 60 for _, L in trips if L[2] and L[3] and L[3] > L[2]]
        med_hold = st.median(holds) if holds else None
        first = min(L[2] for _, L in trips if L[2])
        last = max(max(x for x in (L[2], L[3]) if x) for _, L in trips)
        span_d = (last - first) / 86400 or 0.01
        tpd = len(trips) / span_d
        rec = {"trips": len(trips), "win_rate": round(win_rate, 3),
               "roi_proxy": round(roi, 3), "med_hold_min":
               round(med_hold, 2) if med_hold is not None else None,
               "span_d": round(span_d, 1), "trades_per_day": round(tpd, 1)}
        if med_hold is not None and med_hold < SNIPER_HOLD_MIN:
            rec["verdict"], rec["archetype"] = "REJECT", "sniper_bot"
            rej["sniper"] += 1
        elif win_rate > REJECT_WIN:
            rec["verdict"], rec["archetype"] = "REJECT", "too_good_flag"
            rej["win>80"] += 1
        elif COPY_WIN_LO <= win_rate <= COPY_WIN_HI and roi > 0 \
                and span_d >= a.min_span_days and 5 <= tpd <= 20:
            rec["verdict"], rec["archetype"] = "COPYABLE", "consistent_trader"
        else:
            rec["verdict"], rec["archetype"] = "WATCH", "unproven"
        db[w] = rec

    out = {"built": time.time(), "ledger": ledger.name, "ledger_lines": n,
           "wallets_total": len(legs),
           "min_span_days": a.min_span_days,
           "vetted": len(db), "reject_reasons": dict(rej), "wallets": db}
    Path(a.out).write_text(json.dumps(out))
    vc = defaultdict(int)
    for r in db.values():
        vc[r["verdict"]] += 1
    print(f"\nvetted {len(db)} wallets from {len(legs)} "
          f"({n/1e6:.1f}M lines in {time.time()-t0:.0f}s)")
    print(f"verdicts: {dict(vc)}")
    print(f"rejects pre-gate: {dict(rej)}")
    top = sorted(((w, r) for w, r in db.items() if r["verdict"] == "COPYABLE"),
                 key=lambda x: -x[1]["roi_proxy"])[:15]
    if top:
        print("\ntop COPYABLE by roi_proxy:")
        for w, r in top:
            print(f"  {w[:12]}… win={r['win_rate']:.0%} roi={r['roi_proxy']:+.0%} "
                  f"hold={r['med_hold_min']}m trips={r['trips']} "
                  f"span={r['span_d']}d tpd={r['trades_per_day']}")
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
