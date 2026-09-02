#!/usr/bin/env python3
"""crew_fp_audit.py — §212: leave-one-out forward FP audit for the
crew tripwire (G2B).

The blocklist was partly harvested FROM historical mints, so counting
blocklist wallets on those same mints is leaky. Honest forward test:
for each paper mint M, count only blocklist wallets whose FIRST-seen
mint in the ledger is NOT M (i.e., wallets we would have known about
from OTHER mints before M launched). Flag at >=30 within 120s of paper
entry; compare flag rate on deep-drain vs normal outcomes.

Single ledger pass. Usage: python3 crew_fp_audit.py
"""
import json, time
from collections import defaultdict
from pathlib import Path

MON = Path(__file__).resolve().parent
WINDOW = 120
THRESH = 30
DRAIN_RET = -0.70          # paper "deep drain" definition


def main():
    # paper universe with outcomes
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
            if r.get("mint") and r.get("entry_t") and r.get("status") == "closed":
                mints[r["mint"]] = r
    bl = json.loads((MON / "drainer_blocklist.json").read_text())
    blw = set()
    for sec in ("masters", "killers", "feeders", "funded_next_gen"):
        blw |= set(bl.get(sec, {}).keys())

    # one ledger pass: first-seen mint per wallet; per-mint early hits
    first_mint = {}
    early = defaultdict(set)
    t0 = time.time()
    n = 0
    for line in (MON / "mfg_wallet_trades.jsonl").open():
        if not line.strip():
            continue
        n += 1
        try:
            r = json.loads(line)
        except Exception:
            continue
        w, m, t = r.get("wallet"), r.get("mint"), r.get("t", 0)
        if w in blw and w not in first_mint:
            first_mint[w] = m
        if m in mints and w in blw:
            e = mints[m]["entry_t"]
            if e <= t <= e + WINDOW:
                early[m].add(w)
    print(f"ledger pass: {n} rows in {time.time()-t0:.1f}s; "
          f"{len(mints)} paper mints, {len(blw)} blocklist wallets")

    rows = []
    for m, r in mints.items():
        loo = {w for w in early.get(m, ()) if first_mint.get(w) != m}
        rows.append({"mint": m, "ret": r.get("ret"),
                     "peak": r.get("peak"), "loo_crew": len(loo),
                     "raw_crew": len(early.get(m, ())),
                     "drain": (r.get("ret") or 0) <= DRAIN_RET})
    drains = [r for r in rows if r["drain"]]
    normals = [r for r in rows if not r["drain"]]
    fp = [r for r in normals if r["loo_crew"] >= THRESH]
    tp = [r for r in drains if r["loo_crew"] >= THRESH]
    print(f"\nLOO crew tripwire @ >= {THRESH} in {WINDOW}s:")
    print(f"  drains (ret <= {DRAIN_RET}): {len(drains)}, "
          f"caught: {len(tp)} ({100*len(tp)/max(len(drains),1):.0f}%)")
    print(f"  normal mints: {len(normals)}, "
          f"false positives: {len(fp)} "
          f"({100*len(fp)/max(len(normals),1):.1f}%)")
    print("\n  caught drains:")
    for r in tp:
        print(f"    {r['mint'][:10]} ret={r['ret']:+.2f} "
              f"loo_crew={r['loo_crew']} (raw {r['raw_crew']})")
    print("  false positives:")
    for r in sorted(fp, key=lambda x: -x["loo_crew"])[:10]:
        print(f"    {r['mint'][:10]} ret={r['ret']:+.2f} "
              f"peak={r['peak']} loo_crew={r['loo_crew']}")
    print("\n  missed drains:")
    for r in drains:
        if r["loo_crew"] < THRESH:
            print(f"    {r['mint'][:10]} ret={r['ret']:+.2f} "
                  f"loo_crew={r['loo_crew']} (raw {r['raw_crew']})")
    # distribution of loo counts on normals (calibration curve)
    dist = defaultdict(int)
    for r in normals:
        dist[min(r["loo_crew"], 30)] += 1
    print("\n  LOO crew-count distribution on normal mints:")
    for k in sorted(dist):
        print(f"    {k}{'+' if k==30 else '':>3}: {dist[k]}")
    out = MON / "crew_fp_audit.json"
    out.write_text(json.dumps({"threshold": THRESH, "window": WINDOW,
                               "rows": rows}, indent=1))
    print(f"\nwrote {out.name} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
