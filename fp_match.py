#!/usr/bin/env python3
"""Score arbitrary wallets against crew fingerprint centroids (§222).

Loads fingerprints.json + fp_clusters.json, builds a centroid per cluster
(union of programs, summed histograms, median numerics), then scores any
wallet by fetching one Helius parsed-tx page and blending similarity to the
nearest centroids.

Validation mode (--validate K): re-fetches K known killers (should score
HIGH) and K organic early-seller controls from green live-close mints
(should score LOW), prints both distributions + separation.

Usage:
  python3 fp_match.py WALLET [WALLET...]   # score specific wallets
  python3 fp_match.py --validate 15        # killers vs controls separation
"""
import json
import math
import random
import statistics
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

MON = Path(__file__).resolve().parent
KEY = (MON / "helius_key.txt").read_text().strip()
API = "https://api.helius.xyz/v0/addresses/{addr}/transactions?api-key=" + KEY


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def cosine(ha, hb):
    keys = set(ha) | set(hb)
    dot = sum(ha.get(k, 0) * hb.get(k, 0) for k in keys)
    na = math.sqrt(sum(v * v for v in ha.values()))
    nb = math.sqrt(sum(v * v for v in hb.values()))
    return dot / (na * nb) if na and nb else 0.0


def logclose(x, y, scale=1.0):
    if not x or not y or x <= 0 or y <= 0:
        return 0.0
    return max(0.0, 1.0 - abs(math.log(x / y)) / scale)


def numeric(f):
    return (f.get("fee_med_lamports"), f.get("instr_med"), f.get("gap_med_s"))


def sim(fa, fb):
    nums = (logclose(fa.get("fee_med_lamports"), fb.get("fee_med_lamports"))
            + logclose(fa.get("instr_med"), fb.get("instr_med"))
            + logclose(fa.get("gap_med_s"), fb.get("gap_med_s"), 2.0)) / 3
    return (0.40 * jaccard(set(fa["programs"]), set(fb["programs"]))
            + 0.30 * cosine(fa["sources"], fb["sources"])
            + 0.15 * cosine(fa["types"], fb["types"])
            + 0.15 * nums)


def fetch_extract(addr):
    req = urllib.request.Request(API.format(addr=addr),
                                 headers={"User-Agent": "mfg-fp/1.0"})
    txs = json.loads(urllib.request.urlopen(req, timeout=25).read())
    if not txs:
        return None
    types, sources, programs = Counter(), Counter(), Counter()
    fees, n_instr, gaps, sol_out = [], [], [], []
    tss = sorted(t.get("timestamp") or 0 for t in txs)
    for a, b in zip(tss, tss[1:]):
        if b > a:
            gaps.append(b - a)
    fp0 = txs[0].get("feePayer")
    for t in txs:
        types[t.get("type") or "?"] += 1
        sources[t.get("source") or "?"] += 1
        instrs = t.get("instructions") or []
        n_instr.append(len(instrs))
        for ix in instrs:
            programs[ix.get("programId") or "?"] += 1
        if t.get("fee"):
            fees.append(t["fee"])
        for nt in t.get("nativeTransfers") or []:
            if nt.get("fromUserAccount") == fp0 and nt.get("amount"):
                sol_out.append(nt["amount"] / 1e9)
    med = lambda xs: statistics.median(xs) if xs else None
    return {"n_tx": len(txs), "types": dict(types), "sources": dict(sources),
            "programs": dict(programs), "fee_med_lamports": med(fees),
            "instr_med": med(n_instr), "gap_med_s": med(gaps),
            "sol_out_med": med(sol_out)}


def load_centroids():
    fp = json.loads((MON / "fingerprints.json").read_text())
    cl = json.loads((MON / "fp_clusters.json").read_text())
    cents = []
    for ci, cluster in enumerate(cl["clusters"]):
        feats = [fp[m["group"]][m["wallet"]] for m in cluster
                 if fp.get(m["group"], {}).get(m["wallet"])]
        if not feats:
            continue
        prog, src, typ = Counter(), Counter(), Counter()
        for f in feats:
            prog.update(f["programs"])
            src.update(f["sources"])
            typ.update(f["types"])
        cents.append({
            "id": ci, "n": len(feats),
            "programs": dict(prog), "sources": dict(src), "types": dict(typ),
            "fee_med_lamports": statistics.median(
                f["fee_med_lamports"] for f in feats if f.get("fee_med_lamports")),
            "instr_med": statistics.median(
                f["instr_med"] for f in feats if f.get("instr_med")),
            "gap_med_s": statistics.median(
                f["gap_med_s"] for f in feats if f.get("gap_med_s")),
        })
    return cents


def score(feat, cents, topk=3):
    if not feat:
        return 0.0, None
    scored = sorted(((sim(feat, c), c["id"], c["n"]) for c in cents),
                    reverse=True)
    return scored[0][0], scored[:topk]


def main():
    cents = load_centroids()
    print(f"{len(cents)} cluster centroids loaded")
    if sys.argv[1] == "--validate":
        k = int(sys.argv[2]) if len(sys.argv) > 2 else 15
        bl = json.loads((MON / "drainer_blocklist.json").read_text())
        killers = list(bl["killers"].keys())
        random.seed(7)
        ksample = random.sample(killers, min(k, len(killers)))
        # controls: early sellers on green-close mints, not blocklisted
        blocked = set()
        for g in ("killers", "feeders", "funded_next_gen", "masters"):
            blocked |= set(bl[g].keys())
        pos = json.loads((MON / "live_positions.json").read_text())
        green = [m for m, p in pos.items()
                 if not p.get("open") and (p.get("pnl_sol") or 0) > 0]
        cand = []
        seen = set()
        with (MON / "mfg_wallet_trades.jsonl").open() as f:
            for line in f:
                r = json.loads(line)
                if (r["mint"] in green and r["side"] == "sell"
                        and r["wallet"] not in blocked
                        and r["wallet"] not in seen):
                    seen.add(r["wallet"])
                    cand.append(r["wallet"])
        random.shuffle(cand)
        csample = cand[:k]
        print(f"scoring {len(ksample)} known killers vs {len(csample)} organic controls")
        ks, cs = [], []
        for w in ksample:
            f = fetch_extract(w)
            s, top = score(f, cents)
            ks.append(s)
            time.sleep(0.25)
        for w in csample:
            f = fetch_extract(w)
            s, top = score(f, cents)
            cs.append(s)
            time.sleep(0.25)
        print("killers :", " ".join(f"{s:.2f}" for s in sorted(ks, reverse=True)))
        print("controls:", " ".join(f"{s:.2f}" for s in sorted(cs, reverse=True)))
        if ks and cs:
            print(f"killer median={statistics.median(ks):.3f}  "
                  f"control median={statistics.median(cs):.3f}  "
                  f"control max={max(cs):.3f}")
        json.dump({"killers": ks, "controls": cs},
                  (MON / "fp_validate.json").open("w"))
    else:
        for w in sys.argv[1:]:
            f = fetch_extract(w)
            s, top = score(f, cents)
            print(f"{w[:12]}… n_tx={f['n_tx'] if f else 0} score={s:.3f} top={top}")
            time.sleep(0.25)


if __name__ == "__main__":
    main()
