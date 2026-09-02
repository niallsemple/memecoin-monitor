#!/usr/bin/env python3
"""Cluster killer-wallet execution fingerprints (§221).

Similarity = weighted blend of:
  - program-set Jaccard (0.4)
  - source-histogram cosine (0.3)   (Helius labels: PUMP_FUN, JUPITER, ...)
  - type-histogram cosine (0.15)    (SWAP / TRANSFER / COMPRESSED_NFT...)
  - numeric closeness (0.15): fee_med, instr_med, gap_med (log-ratio)

Union-find clusters above THRESH. Also tests whether master-linked wallets
(feeders / funded_next_gen carry a 'feeds'/'funded_by' tag) land inside
killer clusters — that would tie crews' execution identity across rotation.

Usage: python3 fp_cluster.py [threshold]
"""
import json
import math
import sys
from pathlib import Path

MON = Path(__file__).resolve().parent
THRESH = float(sys.argv[1]) if len(sys.argv) > 1 else 0.80


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cosine(ha, hb):
    keys = set(ha) | set(hb)
    dot = sum(ha.get(k, 0) * hb.get(k, 0) for k in keys)
    na = math.sqrt(sum(v * v for v in ha.values()))
    nb = math.sqrt(sum(v * v for v in hb.values()))
    return dot / (na * nb) if na and nb else 0.0


def logclose(x, y, scale=1.0):
    if not x or not y or x <= 0 or y <= 0:
        return 0.0
    d = abs(math.log(x / y))
    return max(0.0, 1.0 - d / scale)


def sim(fa, fb):
    return (0.40 * jaccard(set(fa["programs"]), set(fb["programs"]))
            + 0.30 * cosine(fa["sources"], fb["sources"])
            + 0.15 * cosine(fa["types"], fb["types"])
            + 0.15 * (logclose(fa.get("fee_med_lamports"), fb.get("fee_med_lamports"))
                      + logclose(fa.get("instr_med"), fb.get("instr_med"))
                      + logclose(fa.get("gap_med_s"), fb.get("gap_med_s"), 2.0)) / 3)


def main():
    fp = json.loads((MON / "fingerprints.json").read_text())
    bl = json.loads((MON / "drainer_blocklist.json").read_text())
    wallets = []
    for grp, d in fp.items():
        for w, f in d.items():
            if f:
                wallets.append((grp, w, f))
    n = len(wallets)
    print(f"{n} wallets with fingerprints, threshold={THRESH}")

    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    edges = 0
    for i in range(n):
        for j in range(i + 1, n):
            s = sim(wallets[i][2], wallets[j][2])
            if s >= THRESH:
                union(i, j)
                edges += 1
    clusters = {}
    for i in range(n):
        clusters.setdefault(find(i), []).append(i)
    multi = [c for c in clusters.values() if len(c) > 1]
    multi.sort(key=len, reverse=True)

    print(f"pairs >= thresh: {edges}; clusters>1: {len(multi)}")
    for c in multi[:12]:
        grps = {}
        masters = set()
        for i in c:
            grp, w, f = wallets[i]
            grps[grp] = grps.get(grp, 0) + 1
            tag = bl.get(grp, {}).get(w, {})
            m = tag.get("feeds") or tag.get("funded_by") or tag.get("tag")
            if m:
                masters.add(m)
        sample = wallets[c[0]][2]
        top_src = sorted(sample["sources"].items(), key=lambda kv: -kv[1])[:3]
        print(f"  cluster n={len(c)} groups={grps} masters={sorted(masters)[:6]}"
              f" top_sources={top_src} fee_med={sample.get('fee_med_lamports')}")

    # cross-group linkage: how many clusters mix killers with master-tagged wallets
    mixed = sum(1 for c in multi
                if len({wallets[i][0] for i in c}) > 1)
    print(f"mixed-group clusters: {mixed}")
    (MON / "fp_clusters.json").write_text(json.dumps(
        {"threshold": THRESH,
         "clusters": [[{"group": wallets[i][0], "wallet": wallets[i][1]}
                       for i in c] for c in multi]}, indent=1))
    print("saved fp_clusters.json")


if __name__ == "__main__":
    main()
