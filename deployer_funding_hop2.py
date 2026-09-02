#!/usr/bin/env python3
"""deployer_funding_hop2.py — §216b: two-hop deployer funding audit.

1-hop result: 0/28 drains. But §206 showed drain capital hops through
2+ single-use relays before consolidating — so the test that matches
crew tradecraft is funder-of-funder (and hop-3) membership in the
blocklist (leave-one-out vs the mint under test).

Resumable via funder_cache.json (same schema; funders are wallets too).
Usage: python3 deployer_funding_hop2.py [per_run]
"""
import json, sys, time
from pathlib import Path
import importlib.util

MON = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "dfa", str(MON / "deployer_funding_audit.py"))
dfa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dfa)

HOPS = 3


def main():
    per_run = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    rows = json.loads((MON / "deployer_funding_audit.json").read_text())
    cache = json.loads(dfa.CACHE_F.read_text()) \
        if dfa.CACHE_F.exists() else {}
    bl = json.loads((MON / "drainer_blocklist.json").read_text())
    blw = set()
    origin = {}
    for sec in ("masters", "killers", "feeders", "funded_next_gen"):
        for w, meta in bl.get(sec, {}).items():
            blw.add(w)
            if isinstance(meta, dict) and meta.get("mint"):
                origin.setdefault(w, set()).add(meta["mint"])

    # build the set of wallets needing resolution: every known funder,
    # chained up to HOPS deep.
    frontier = {r["funder"] for r in rows if r.get("funder")}
    for _ in range(HOPS - 1):
        nxt = set()
        for w in frontier:
            f = cache.get(w, {}).get("funder")
            if f:
                nxt.add(f)
        frontier |= nxt
    todo = sorted({w for w in frontier
                   if not cache.get(w, {}).get("funder")
                   and cache.get(w, {}).get("tries", 0) < 3})
    done = 0
    for w in todo[:per_run]:
        f, sig = dfa.find_funder(w)
        cache[w] = {"funder": f, "sig": sig,
                    "tries": cache.get(w, {}).get("tries", 0) + 1}
        done += 1
        if done % 5 == 0:
            dfa.CACHE_F.write_text(json.dumps(cache))
        time.sleep(0.25)
    dfa.CACHE_F.write_text(json.dumps(cache))
    print(f"resolved {done} this run; {len(todo)-per_run} remaining; "
          f"cache {len(cache)}")
    if todo[per_run:]:
        return

    # analysis: walk each mint's chain up to HOPS, LOO blocklist test
    out = []
    for r in rows:
        m = r["mint"]
        loo = {w for w in blw if m not in origin.get(w, set())}
        chain, w, hit = [], r.get("funder"), None
        for depth in range(1, HOPS + 1):
            if not w:
                break
            chain.append(w)
            if w in loo:
                hit = depth
                break
            w = cache.get(w, {}).get("funder")
        out.append({**r, "chain": chain, "hit_depth": hit})
    drains = [r for r in out if r["drain"]]
    normals = [r for r in out if not r["drain"]]
    print(f"\n=== {HOPS}-HOP DEPLOYER-FUNDING LOO AUDIT ===")
    for d in range(1, HOPS + 1):
        dh = sum(1 for r in drains if r["hit_depth"] is not None
                 and r["hit_depth"] <= d)
        nh = sum(1 for r in normals if r["hit_depth"] is not None
                 and r["hit_depth"] <= d)
        print(f"  <= hop {d}: drains {dh}/{len(drains)}   "
              f"normals {nh}/{len(normals)} ({100*nh/max(len(normals),1):.1f}% FP)")
    print("\ndrain hits:")
    for r in drains:
        if r["hit_depth"]:
            print(f"  {r['mint'][:10]} ret={r['ret']:+.2f} "
                  f"hit@hop{r['hit_depth']} "
                  f"via {r['chain'][r['hit_depth']-1][:10]}")
    (MON / "deployer_funding_hop2.json").write_text(json.dumps(out, indent=1))
    print(f"\nwrote deployer_funding_hop2.json ({len(out)} rows)")


if __name__ == "__main__":
    main()
