#!/usr/bin/env python3
"""kamino_liq_verify.py — ground-truth pass: RPC getTransaction (jsonParsed,
INCLUDES innerInstructions) for every harvested FLASH_REPAY tx, scanning
outer+inner KLend ixs for the proven liquidate discriminator.
Confirmed liquidations append to kamino_liq_dataset.jsonl (verified=True).
Checkpointed; safe to re-run.
"""
import json, time, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from kamino_tail import rpc, b58decode  # helius RPC + b58

MON = Path(__file__).resolve().parent
KLEND = "KLend2g3cP87fffoy8q1mQqGKjrxjC8boSyAYavgmjD"
LIQ_DISC = bytes([177, 71, 154, 188, 226, 133, 74, 55])
ARB = MON / "kamino_arb_dataset.jsonl"
OUT = MON / "kamino_liq_dataset.jsonl"
DONE = MON / "kamino_liq_verify_done.json"


def scan_tx(tx):
    ixs = list(tx["transaction"]["message"].get("instructions", []))
    for inner in (tx.get("meta") or {}).get("innerInstructions") or []:
        ixs += inner.get("instructions", [])
    for ix in ixs:
        if not isinstance(ix, dict):
            continue
        if ix.get("programId") != KLEND:
            continue
        data = ix.get("data")
        if not data:
            continue
        try:
            raw = b58decode(data)
        except Exception:
            continue
        if raw[:8] == LIQ_DISC:
            accts = ix.get("accounts", [])
            return {"obligation": accts[1] if len(accts) > 1 else None,
                    "liquidator_ix": accts[0] if accts else None}
    return None


def main():
    max_s = float(sys.argv[1]) if len(sys.argv) > 1 else 240
    t0 = time.time()
    done = set(json.load(open(DONE))) if DONE.exists() else set()
    confirmed = set()
    if OUT.exists():
        for l in open(OUT):
            try:
                confirmed.add(json.loads(l)["sig"])
            except Exception:
                pass
    rows = [json.loads(l) for l in open(ARB)]
    n_checked = n_found = 0
    f = open(OUT, "a")
    for r in rows:
        if time.time() - t0 > max_s:
            break
        sig = r["sig"]
        if sig in done or sig in confirmed:
            continue
        done.add(sig)
        n_checked += 1
        try:
            tx = rpc("getTransaction", [sig, {"encoding": "jsonParsed",
                     "maxSupportedTransactionVersion": 0}]).get("result")
        except Exception:
            continue
        if not tx:
            continue
        hit = scan_tx(tx)
        if hit:
            rec = dict(r)
            rec.update({"verified": True, "obligation": hit["obligation"],
                        "liquidator_ix": hit["liquidator_ix"]})
            f.write(json.dumps(rec) + "\n")
            f.flush()
            n_found += 1
            print(f"LIQUIDATION CONFIRMED: {sig[:16]} ob={str(hit['obligation'])[:8]} "
                  f"ts={r['ts']}", flush=True)
        time.sleep(0.12)
    f.close()
    json.dump(sorted(done), open(DONE, "w"))
    print(f"checked {n_checked} (total done {len(done)}/{len(rows)}), "
          f"confirmed {n_found} new liquidations")


if __name__ == "__main__":
    main()
