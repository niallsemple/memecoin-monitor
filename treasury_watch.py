#!/usr/bin/env python3
"""treasury_watch.py — §207: watch drain-crew treasury outflows.

Polls every wallet in drainer_blocklist.json['masters'] for transactions
since the last watermark. Classifies outbound SOL flows:

  - burst: >=3 outbound transfers within 10 min with similar amounts
           (±25%) => worker-funding burst; recipients are next-gen
           workers and are auto-added to blocklist 'funded_next_gen'.
  - big single transfer (>100 SOL) => treasury-to-treasury
           consolidation; logged as TREASURY_HOP for manual review
           (auto-adding treasuries risks runaway graph growth).
  - other outbound => logged as OUTFLOW.

State: treasury_watch_state.json (per-master last-seen signature).
Log:   treasury_watch.jsonl (one row per classified event).

Usage: python3 treasury_watch.py [--init]   (--init = watermark only,
no classification — use on first run to skip history.)
"""
import json, sys, time, urllib.request
from pathlib import Path

MON = Path(__file__).resolve().parent
KEY = (MON / "helius_key.txt").read_text().strip()
RPC = f"https://mainnet.helius-rpc.com/?api-key={KEY}"
BL_F = MON / "drainer_blocklist.json"
STATE_F = MON / "treasury_watch_state.json"
LOG_F = MON / "treasury_watch.jsonl"

BURST_MIN_N = 3
BURST_WINDOW_S = 600
BURST_TOL = 0.25
BIG_SOL = 100.0
MIN_SOL = 0.05


def rpc(method, params, tries=4):
    body = json.dumps({"jsonrpc": "2.0", "id": 1,
                       "method": method, "params": params}).encode()
    for a in range(tries):
        try:
            req = urllib.request.Request(
                RPC, data=body,
                headers={"Content-Type": "application/json"})
            return json.load(urllib.request.urlopen(req, timeout=30))
        except Exception as e:
            if a == tries - 1:
                raise
            time.sleep(1.7 * (a + 1))


def log(row):
    row["ts"] = time.time()
    with LOG_F.open("a") as f:
        f.write(json.dumps(row) + "\n")


def main():
    init = "--init" in sys.argv
    bl = json.loads(BL_F.read_text())
    masters = bl["masters"]
    state = json.loads(STATE_F.read_text()) if STATE_F.exists() else {}
    events = []
    for addr, meta in masters.items():
        tag = meta.get("tag", "?") if isinstance(meta, dict) else "?"
        try:
            sigs = rpc("getSignaturesForAddress",
                       [addr, {"limit": 20}])["result"]
        except Exception as e:
            log({"event": "rpc_error", "master": addr, "tag": tag,
                 "error": str(e)[:120]})
            continue
        if not sigs:
            continue
        newest = sigs[0]["signature"]
        last = state.get(addr)
        if init or last is None:
            state[addr] = newest
            continue
        fresh = []
        for s in sigs:
            if s["signature"] == last:
                break
            fresh.append(s)
        state[addr] = newest
        for s in reversed(fresh):          # oldest first
            if s.get("err"):
                continue
            time.sleep(1.7)
            try:
                tx = rpc("getTransaction",
                         [s["signature"],
                          {"encoding": "jsonParsed",
                           "maxSupportedTransactionVersion": 0}])["result"]
            except Exception:
                continue
            if not tx:
                continue
            keys = [k if isinstance(k, str) else k["pubkey"]
                    for k in tx["transaction"]["message"]["accountKeys"]]
            for k, a, b in zip(keys, tx["meta"]["preBalances"],
                               tx["meta"]["postBalances"]):
                d = (b - a) / 1e9
                if d > MIN_SOL and k != addr and k not in masters:
                    events.append({"master": addr, "tag": tag,
                                   "to": k, "sol": round(d, 4),
                                   "bt": tx["blockTime"],
                                   "sig": s["signature"]})
        time.sleep(1.7)
    # classify
    bursts, hops = [], []
    for e in events:
        if e["sol"] >= BIG_SOL:
            hops.append(e)
            log({"event": "TREASURY_HOP", **e})
    by_master = {}
    for e in events:
        if e["sol"] < BIG_SOL:
            by_master.setdefault(e["master"], []).append(e)
    new_workers = 0
    for m, evs in by_master.items():
        evs.sort(key=lambda x: x["bt"] or 0)
        for i, e in enumerate(evs):
            win = [x for x in evs
                   if abs((x["bt"] or 0) - (e["bt"] or 0)) <= BURST_WINDOW_S
                   and abs(x["sol"] - e["sol"]) <= BURST_TOL * e["sol"]]
            kind = "WORKER_STAKE" if len(win) >= BURST_MIN_N else "OUTFLOW"
            log({"event": kind, "burst_n": len(win), **e})
            if kind == "WORKER_STAKE":
                fn = bl.setdefault("funded_next_gen", {})
                if e["to"] not in fn:
                    fn[e["to"]] = {"funded_by": m,
                                   "stake_sol": e["sol"],
                                   "seen": time.strftime(
                                       "%Y-%m-%d %H:%M UTC",
                                       time.gmtime(e["bt"] or 0)),
                                   "source": "treasury_watch"}
                    new_workers += 1
        if len(evs) >= BURST_MIN_N:
            bursts.append((m, len(evs)))
    if new_workers:
        B1 = json.loads(BL_F.read_text())  # keep any concurrent edits'
        B1["funded_next_gen"].update(
            {k: v for k, v in bl["funded_next_gen"].items()
             if k not in B1.get("funded_next_gen", {})})
        B1_F = BL_F
        B1_F.write_text(json.dumps(B1, indent=1))
    STATE_F.write_text(json.dumps(state, indent=1))
    summary = {"event": "run_summary", "init": init,
               "masters_polled": len(masters), "raw_events": len(events),
               "treasury_hops": len(hops), "burst_masters": bursts,
               "new_workers": new_workers}
    log(summary)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
