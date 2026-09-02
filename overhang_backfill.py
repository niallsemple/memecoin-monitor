#!/usr/bin/env python3
"""overhang_backfill.py — §213: historical proxy validation of the
overhang screen across the full paper book.

The live overhang screen (getTokenLargestAccounts) reads current state
— unusable on historical mints. Proxy from the wallet ledger instead:
wallets that SOLD via the pool but NEVER BOUGHT via the pool are
insider-allocation wallets by definition (§189 fingerprint). Their
share of total sell volume approximates what the entry-time overhang
screen would have seen (biased LOW for mints where insiders still hold,
and it observes the full life rather than entry instant — labeled).

Ledger rows carry SOL amounts only, so the proxy is SOL-denominated:
  insider_share = SOL sold by never-bought wallets / total sell SOL

Universe: closed paper mints (fr book + broad book). Drains = ret<=-0.7.
Usage: python3 overhang_backfill.py
"""
import json
from collections import defaultdict
from pathlib import Path

MON = Path(__file__).resolve().parent
DRAIN_RET = -0.70


def main():
    mints = {}
    for src in ("mfg_paper_trades_s60nm5fr.jsonl", "mfg_paper_trades.jsonl"):
        p = MON / src
        if not p.exists():
            continue
        for line in p.open():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("mint") and r.get("status") == "closed":
                mints[r["mint"]] = r

    bought = defaultdict(set)
    sell_sol = defaultdict(lambda: defaultdict(float))
    tot_sell = defaultdict(float)
    tot_buy = defaultdict(float)
    for line in (MON / "mfg_wallet_trades.jsonl").open():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        m = r.get("mint")
        if m not in mints:
            continue
        w, s, sol = r.get("wallet"), r.get("side"), r.get("sol", 0) or 0
        if s == "buy":
            bought[m].add(w)
            tot_buy[m] += sol
        elif s == "sell":
            sell_sol[m][w] += sol
            tot_sell[m] += sol

    rows = []
    for m, r in mints.items():
        insider_sol = sum(v for w, v in sell_sol.get(m, {}).items()
                          if w not in bought[m])
        n_ins = sum(1 for w in sell_sol.get(m, {}) if w not in bought[m])
        ts = tot_sell.get(m, 0.0)
        rows.append({
            "mint": m, "ret": r.get("ret"), "peak": r.get("peak"),
            "insider_sol": round(insider_sol, 2),
            "insider_n": n_ins,
            "sell_share": round(insider_sol / ts, 4) if ts > 0 else None,
            "buy_ratio": round(insider_sol / tot_buy[m], 4)
            if tot_buy.get(m, 0) > 0 else None,
            "drain": (r.get("ret") or 0) <= DRAIN_RET})

    drains = [r for r in rows if r["drain"]]
    normals = [r for r in rows if not r["drain"] and r["sell_share"] is not None]
    print("=" * 68)
    print(f"OVERHANG PROXY BACKFILL — {len(rows)} mints "
          f"({len(drains)} drains, {len(normals)} normals with sells)")
    print("=" * 68)
    print(f"\n{'sell_share thresh':>18} {'catch drains':>13} {'FP normals':>11}")
    for t in (0.05, 0.10, 0.20, 0.30, 0.40, 0.50):
        tp = sum(1 for r in drains
                 if r["sell_share"] is not None and r["sell_share"] >= t)
        fp = sum(1 for r in normals if r["sell_share"] >= t)
        print(f"{t:>17.0%} {tp:>7}/{len(drains):<5} {fp:>6}/{len(normals)}"
              f"  ({100*fp/max(len(normals),1):.1f}% FP)")
    print("\nDrains detail (sorted by insider sell share):")
    for r in sorted(drains, key=lambda x: -(x["sell_share"] or 0)):
        print(f"  {r['mint'][:10]:12s} ret={r['ret']:+.2f} "
              f"share={r['sell_share']} insider_sol={r['insider_sol']:>8} "
              f"n={r['insider_n']} buy_ratio={r['buy_ratio']}")
    print("\nTop normal-mint shares (FP risk):")
    for r in sorted(normals, key=lambda x: -(x["sell_share"] or 0))[:12]:
        print(f"  {r['mint'][:10]:12s} ret={r['ret']:+.2f} "
              f"share={r['sell_share']} insider_sol={r['insider_sol']:>8} "
              f"n={r['insider_n']}")
    (MON / "overhang_backfill.json").write_text(
        json.dumps(rows, indent=1))
    print(f"\nwrote overhang_backfill.json ({len(rows)} rows)")


if __name__ == "__main__":
    main()
