"""exec_journal.py — §407: execution journal. Zero-risk instrumentation.

Every tx we submit is recorded (sig, endpoint host, submit time); a
resolver on the 90s shock cadence marks each landed/failed via
getSignatureStatuses. Output: exec_journal.jsonl

This is the seed of the SOLANA EXECUTION ALPHA layer from the owner's
ChatGPT brief: before optimizing routes by landing probability, MEASURE
landing probability per endpoint from our own flow. §406 quantified the
leak (~0.55 SOL on two positions that couldn't land exits).

Also noted while wiring: RPCS order in live_trader.py is
[publicnode, mainnet-beta, helius] — Helius is tried LAST despite the
§164 comment saying first. Journal will show whether that costs us;
do not reorder until measured.
"""
import json
import time
from pathlib import Path

MON = Path(__file__).resolve().parent
JOURNAL = MON / "exec_journal.jsonl"
MIN_AGE_S = 8        # don't resolve txs younger than this


def _host(url):
    try:
        return url.split("/")[2]
    except Exception:
        return url[:32]


def record_submit(sig, url, context=""):
    row = {"action": "tx_submit", "sig": sig, "endpoint": _host(url),
           "t": time.time(), "context": context, "resolved": False}
    with JOURNAL.open("a") as f:
        f.write(json.dumps(row) + "\n")


def run_pass():
    """Resolve pending submits. Rewrites the journal in place."""
    if not JOURNAL.exists():
        return {"pending": 0}
    rows = []
    for l in JOURNAL.read_bytes().splitlines():
        try:
            rows.append(json.loads(l))
        except Exception:
            continue
    pend = [r for r in rows
            if r.get("action") == "tx_submit" and not r.get("resolved")
            and time.time() - r.get("t", 0) > MIN_AGE_S]
    if not pend:
        return {"pending": 0}
    import raydium_cpmm as rc
    sigs = [r["sig"] for r in pend][-50:]
    try:
        res = rc.rpc("getSignatureStatuses",
                     [sigs, {"searchTransactionHistory": True}]) or {}
    except Exception:
        return {"pending": len(pend)}
    vals = res.get("value") or []
    by_sig = dict(zip(sigs, vals))
    now = time.time()
    changed = False
    for r in rows:
        if r.get("resolved") or r.get("sig") not in by_sig:
            continue
        v = by_sig[r["sig"]]
        if v is None:
            if now - r["t"] > 300:      # never landed after 5 min
                r["resolved"] = True
                r["outcome"] = "dropped"
                changed = True
            continue
        r["resolved"] = True
        r["outcome"] = "failed" if v.get("err") else "landed"
        r["land_slot"] = v.get("slot")
        r["resolve_t"] = now
        r["err"] = (json.dumps(v.get("err"))[:80] if v.get("err") else None)
        changed = True
    if changed:
        JOURNAL.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return {"pending": len(pend), "resolved_now": sum(
        1 for r in pend if r.get("resolved"))}


def stats():
    """Landing rate by endpoint — the number the brief asks for."""
    rows = [json.loads(l) for l in JOURNAL.open()] if JOURNAL.exists() else []
    done = [r for r in rows if r.get("resolved")]
    by = {}
    for r in done:
        e = by.setdefault(r["endpoint"], {"landed": 0, "failed": 0,
                                          "dropped": 0})
        e[r.get("outcome", "dropped")] = e.get(r.get("outcome", "dropped"), 0) + 1
    return by


if __name__ == "__main__":
    print("resolve pass:", run_pass())
    print("stats:", json.dumps(stats(), indent=1))
