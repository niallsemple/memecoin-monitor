#!/usr/bin/env python3
"""Execution-fingerprint extractor for known drainer wallets (§221).

ChatGPT-rotation hypothesis: crews rotate wallet ADDRESSES per mint, but if
they reuse the same bot binary, the execution fingerprint survives:
which programs they call, what tx types/sources Helius labels them,
fee levels, instruction counts, timing gaps, SOL transfer sizes.

Fetches one page (<=100) of Helius parsed txs per wallet — enough for
single-use killer wallets whose whole life is fund -> buy -> drain -> sweep.

Output: fingerprints.json  { group: { wallet: feature_dict } }
State:  fingerprint_state.json (resumable; safe to re-run)

Usage: python3 fingerprint.py [batch_size]
"""
import json
import statistics
import sys
import time
import urllib.request
from pathlib import Path

MON = Path(__file__).resolve().parent
KEY = (MON / "helius_key.txt").read_text().strip()
API = "https://api.helius.xyz/v0/addresses/{addr}/transactions?api-key=" + KEY
OUT = MON / "fingerprints.json"
STATE = MON / "fingerprint_state.json"
PAGE_SLEEP = 0.25


def fetch_txs(addr):
    req = urllib.request.Request(API.format(addr=addr),
                                 headers={"User-Agent": "mfg-fp/1.0"})
    return json.loads(urllib.request.urlopen(req, timeout=25).read())


def med(xs):
    return statistics.median(xs) if xs else None


def extract(txs):
    """txs: Helius parsed tx list (newest first). -> feature dict."""
    if not txs:
        return None
    types, sources, programs = {}, {}, {}
    fees, n_instr, gaps, sol_out = [], [], [], []
    tss = sorted(t.get("timestamp") or 0 for t in txs)
    for a, b in zip(tss, tss[1:]):
        if b > a:
            gaps.append(b - a)
    fee_payer = txs[0].get("feePayer")
    for t in txs:
        ty = t.get("type") or "?"
        types[ty] = types.get(ty, 0) + 1
        so = t.get("source") or "?"
        sources[so] = sources.get(so, 0) + 1
        instrs = t.get("instructions") or []
        n_instr.append(len(instrs))
        for ix in instrs:
            p = ix.get("programId") or "?"
            programs[p] = programs.get(p, 0) + 1
        if t.get("fee"):
            fees.append(t["fee"])
        for nt in t.get("nativeTransfers") or []:
            if nt.get("fromUserAccount") == fee_payer and nt.get("amount"):
                sol_out.append(nt["amount"] / 1e9)
    return {
        "n_tx": len(txs),
        "first_ts": tss[0],
        "last_ts": tss[-1],
        "span_s": tss[-1] - tss[0],
        "gap_med_s": med(gaps),
        "types": types,
        "sources": sources,
        "programs": programs,
        "fee_med_lamports": med(fees),
        "fee_max_lamports": max(fees) if fees else None,
        "instr_med": med(n_instr),
        "sol_out_med": med(sol_out),
    }


def main():
    batch = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    bl = json.loads((MON / "drainer_blocklist.json").read_text())
    fp = json.loads(OUT.read_text()) if OUT.exists() else {}
    state = json.loads(STATE.read_text()) if STATE.exists() else {"done": []}
    done = set(state["done"])

    todo = []
    for grp in ("killers", "feeders", "funded_next_gen", "masters"):
        for w in bl.get(grp, {}):
            if w not in done:
                todo.append((grp, w))
    todo = todo[:batch]
    print(f"fingerprinting {len(todo)} wallets ({len(done)} already done)")

    for i, (grp, w) in enumerate(todo):
        try:
            txs = fetch_txs(w)
            feats = extract(txs)
        except Exception as e:
            print(f"  [{i}] {w[:8]}… ERROR {e}")
            time.sleep(1.0)
            continue
        fp.setdefault(grp, {})[w] = feats
        done.add(w)
        if i % 10 == 0:
            print(f"  [{i}] {grp} {w[:8]}… n_tx={feats['n_tx'] if feats else 0}")
        time.sleep(PAGE_SLEEP)
        # checkpoint every 15 wallets
        if i % 15 == 14:
            OUT.write_text(json.dumps(fp))
            STATE.write_text(json.dumps({"done": sorted(done)}))

    OUT.write_text(json.dumps(fp))
    STATE.write_text(json.dumps({"done": sorted(done)}))
    total = sum(len(v) for v in fp.values())
    empty = sum(1 for v in fp.values() for f in v.values() if not f)
    print(f"saved {total} fingerprints ({empty} empty), done={len(done)}")


if __name__ == "__main__":
    main()
