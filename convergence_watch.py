#!/usr/bin/env python3
"""convergence_watch.py — the "3+ smart wallets = signal" detector.

Research (05-synthesis.md, Q3 #9): one vetted wallet buying = noise;
three or more independent vetted wallets buying the same mint inside a
window = signal. Scans the recent tail of the trade ledger(s) for buys
by COPYABLE/WATCH wallets from the vetted DB(s) and emits a convergence
alert per qualifying mint to edge_convergence.jsonl, plus a compact
record to edge_candidates.jsonl that exec_dry.py prefers over raw
liquidity rank.

Usage:
  python3 convergence_watch.py [--minutes 120] [--min-wallets 3]
      [--wallet-verdicts COPYABLE,WATCH]
      [--db smart_wallets.json[,smart_wallets_broad.json]]
      [--ledger mfg_wallet_trades.jsonl[,broad_trades.jsonl]]
      [--candidates-out edge_candidates.jsonl]
"""
import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

MON = Path(__file__).resolve().parent
OUT = MON / "edge_convergence.jsonl"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=120)
    ap.add_argument("--min-wallets", type=int, default=3)
    ap.add_argument("--wallet-verdicts", default="COPYABLE,WATCH")
    ap.add_argument("--db", default=str(MON / "smart_wallets.json"),
                    help="comma-separated vetted wallet DBs (merged)")
    ap.add_argument("--ledger", default=str(MON / "mfg_wallet_trades.jsonl"),
                    help="comma-separated trade ledgers to scan")
    ap.add_argument("--candidates-out", default=str(MON / "edge_candidates.jsonl"),
                    help="exec_dry-priority candidates output ('' disables)")
    a = ap.parse_args()

    ok = set(a.wallet_verdicts.split(","))
    watched = set()
    for p in a.db.split(","):
        p = Path(p.strip())
        if not p.exists():
            continue
        db = json.loads(p.read_text())
        watched |= {w for w, r in db.get("wallets", {}).items()
                    if r.get("verdict") in ok}
    if not watched:
        print("no vetted wallets — run wallet_vetter.py first")
        return

    cutoff = time.time() - a.minutes * 60
    hits = defaultdict(set)          # mint -> {wallets}
    first_seen = {}
    for lp in a.ledger.split(","):
        lp = Path(lp.strip())
        if not lp.exists():
            continue
        with lp.open() as f:
            for line in f:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("side") != "buy" or r.get("t", 0) < cutoff:
                    continue
                w, m = r.get("wallet"), r.get("mint")
                if w in watched and m:
                    hits[m].add(w)
                    first_seen.setdefault(m, r["t"])

    n_alerts = 0
    for mint, ws in sorted(hits.items(), key=lambda x: -len(x[1])):
        if len(ws) >= a.min_wallets:
            rec = {"t": time.time(), "mint": mint, "n_wallets": len(ws),
                   "wallets": sorted(ws), "first_buy_t": first_seen[mint],
                   "window_min": a.minutes}
            with OUT.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            if a.candidates_out:
                cand = {"t": rec["t"], "mint": mint, "n_wallets": len(ws),
                        "src": "convergence"}
                with Path(a.candidates_out).open("a") as f:
                    f.write(json.dumps(cand) + "\n")
            n_alerts += 1
            print(f"CONVERGENCE {mint[:16]}… — {len(ws)} vetted wallets "
                  f"in {a.minutes:.0f}m")
    print(f"\n{len(watched)} vetted wallets watched, "
          f"{len(hits)} mints touched, {n_alerts} convergence alerts "
          f"→ {OUT.name}")


if __name__ == "__main__":
    main()
