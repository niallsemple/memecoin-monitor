#!/usr/bin/env python3
"""Per-trade cost decomposition for hfna_live trades.

Parses hfna_live.jsonl for live_enter/live_exit/real_pnl triples, pulls all
tx signatures from the "out" fields, fetches each tx via Helius
/v0/transactions, and reconciles: wallet_delta == sol_moved_by_trade - tx_costs.

Outputs per trade:
  gross wallet delta, sum(base fees), sum(priority fees), rent deltas,
  net P&L attributed to LP outcome vs costs, and any unexplained residual
  (e.g. the -0.00103 drift seen between probes #2 and #3).
"""
import json, re, os, sys, urllib.request, time

BASE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(BASE, "hfna_live.jsonl")
KEY = open(os.path.join(BASE, "helius_key.txt")).read().strip()
WALLET = "CQcKkSee9bdHZ1bejYFDUXVtodbfKHe2KSx6AaAnTW2K"
SIGRE = re.compile(r"(?:sigs?=)([1-9A-HJ-NP-Za-km-z,]{80,300})")

RPC = f"https://mainnet.helius-rpc.com/?api-key={KEY}"

def rpc_tx(sig):
    """getTransaction jsonParsed — returns native balance diff + fee for WALLET."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getTransaction",
                       "params": [sig, {"encoding": "jsonParsed",
                                        "maxSupportedTransactionVersion": 0}]}).encode()
    req = urllib.request.Request(RPC, data=body, headers={
        "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                res = json.load(r).get("result")
        except Exception as e:
            if attempt == 2:
                print(f"  [warn] tx fetch failed: {e}", file=sys.stderr)
                return None
            time.sleep(2 * (attempt + 1))
            continue
        if res is None:
            return None
        meta = res.get("meta") or {}
        keys = [k["pubkey"] if isinstance(k, dict) else k
                for k in res["transaction"]["message"]["accountKeys"]]
        try:
            i = keys.index(WALLET)
        except ValueError:
            return None
        pre, post = meta.get("preBalances", []), meta.get("postBalances", [])
        if i >= len(pre) or i >= len(post):
            return None
        return {"sig": sig, "fee": meta.get("fee", 0),
                "n_signers": len(res["transaction"].get("signatures", [1])),
                "native_diff": (post[i] - pre[i]) / 1e9,
                "err": meta.get("err")}

def current_locked_rent():
    """Lamports locked in wallet-owned ATAs right now (both token programs).
    Only meaningful when run IMMEDIATELY post-lifecycle (mandate: decomp
    runs right after each exit) — historical windows can't be re-scanned."""
    total = 0
    for prog in ("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                 "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"):
        body = json.dumps({"jsonrpc": "2.0", "id": 1,
                           "method": "getTokenAccountsByOwner",
                           "params": [WALLET, {"programId": prog},
                                      {"encoding": "jsonParsed"}]}).encode()
        req = urllib.request.Request(RPC, data=body, headers={
            "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                for a in json.load(r).get("result", {}).get("value", []):
                    total += a["account"]["lamports"]
        except Exception as e:
            print(f"  [warn] rent scan failed: {e}", file=sys.stderr)
    return total / 1e9

def batch_txs(sigs):
    out = []
    for s in sigs:
        t = rpc_tx(s)
        if t:
            out.append(t)
    return out

def load_trades():
    """Pair enter/exit/pnl events into trade records."""
    events = []
    with open(LOG) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("kind") in ("live_enter", "live_exit", "real_pnl"):
                events.append(ev)
    trades, open_t = [], {}
    for ev in events:
        pool = ev.get("pool")
        if ev["kind"] == "live_enter":
            open_t[pool] = ev
        elif ev["kind"] == "real_pnl" and pool in open_t:
            ent = open_t.pop(pool)
            exit_ev = None
            for e2 in events:
                if (e2["kind"] == "live_exit" and e2.get("pool") == pool
                        and ent["t"] <= e2["t"] <= ev["t"]):
                    exit_ev = e2
            trades.append({"enter": ent, "exit": exit_ev, "pnl": ev})
    return trades, list(open_t.values())

def sigs_of(ev):
    out = (ev or {}).get("out") or ""
    sigs = []
    for m in SIGRE.finditer(out):
        sigs += [s for s in m.group(1).split(",") if len(s) >= 80]
    return sigs

def wallet_sigs_in_window(t0, t1):
    """All wallet tx signatures with blockTime in [t0-10, t1+10]."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getSignaturesForAddress",
                       "params": [WALLET, {"limit": 100}]}).encode()
    req = urllib.request.Request(RPC, data=body, headers={
        "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            rows = json.load(r).get("result") or []
    except Exception as e:
        print(f"  [warn] sigs fetch failed: {e}", file=sys.stderr)
        return []
    return [x["signature"] for x in rows
            if x.get("blockTime") and t0 - 10 <= x["blockTime"] <= t1 + 10]

def analyze_trade(tr):
    ent, ext, pnl = tr["enter"], tr["exit"], tr["pnl"]
    sigs = sigs_of(ent) + sigs_of(ext)
    extra = wallet_sigs_in_window(ent["t"], pnl["t"])
    sigs = list(dict.fromkeys(sigs + extra))  # dedupe, keep order
    wb, wa = pnl.get("wallet_before"), pnl.get("wallet_after")
    rec = {
        "pool": ent["pool"][:8], "t_entry": ent["t"],
        "hold_s": (pnl["t"] - ent["t"]),
        "wallet_before": wb, "wallet_after": wa,
        "wallet_delta": (wa - wb) if (wb is not None and wa is not None) else None,
        "real_pnl_reported": pnl.get("real_pnl"),
        "n_txs": len(sigs),
    }
    if not sigs:
        rec["note"] = "no signatures parsed"
        return rec
    txs = batch_txs(sigs)
    fees = sum(t["fee"] for t in txs) / 1e9
    base_fees = sum(5000 * t.get("n_signers", 1) for t in txs) / 1e9
    prio_fees = fees - base_fees
    native = sum(t["native_diff"] for t in txs)  # exact net SOL moved per tx
    n_ok, n_fail = len(txs), len(sigs) - len(txs)
    rec.update({
        "tx_fees_sol": fees,
        "base_fees": base_fees, "priority_fees": prio_fees,
        "native_diff_sum": native,
        "txs_fetched": n_ok, "txs_missing": n_fail,
    })
    if rec["wallet_delta"] is not None:
        rec["residual_unexplained"] = rec["wallet_delta"] - native
        rec["lp_outcome_approx"] = native + fees
    return rec

def latest_lifecycle_split():
    """Mandate v3 accounting separation for the most recent completed trade:
    ExecutionCost = network(base) + priority + unrecovered rent (scanned NOW)
    TradingPnL    = WalletDelta + ExecutionCost
    Identity: WalletDelta == TradingPnL - ExecutionCost  (by construction,
    residual shown separately so any misfit is visible).
    """
    trades, _ = load_trades()
    if not trades:
        print("no completed trades"); return
    r = analyze_trade(trades[-1])
    rent_now = current_locked_rent()
    exec_cost = (r.get("tx_fees_sol") or 0) + rent_now
    wd = r.get("wallet_delta")
    trading = (wd + exec_cost) if wd is not None else None
    print(f"LIFECYCLE SPLIT — {r['pool']} hold={r['hold_s']:.0f}s")
    print(f"  network base fees : {r.get('base_fees', 0):.7f}")
    print(f"  priority fees     : {r.get('priority_fees', 0):.7f}")
    print(f"  unrecovered rent  : {rent_now:.7f}  (ATAs open NOW)")
    print(f"  ExecutionCost     : {exec_cost:.7f}")
    print(f"  WalletDelta       : {wd:+.7f}" if wd is not None else "  WalletDelta: n/a")
    print(f"  TradingPnL        : {trading:+.7f}" if trading is not None else "")
    print(f"  residual          : {r.get('residual_unexplained'):+.7f}"
          if r.get("residual_unexplained") is not None else "")
    ok = exec_cost <= 0.0001
    print(f"  VERDICT: cost {'≤' if ok else '>'} 0.0001 SOL -> patch "
          f"{'VERIFIED for this lifecycle' if ok else 'NOT verified — investigate'}")

def main():
    trades, open_pos = load_trades()
    print(f"trades with pnl: {len(trades)}   open positions: {len(open_pos)}")
    tot_pnl = tot_fees = tot_resid = 0.0
    for tr in trades[-12:]:
        r = analyze_trade(tr)
        tot_pnl += r.get("real_pnl_reported") or 0
        tot_fees += r.get("tx_fees_sol") or 0
        resid = r.get("residual_unexplained")
        if resid is not None:
            tot_resid += resid
        print(f"{r['pool']}  hold={r['hold_s']:.0f}s  pnl={r.get('real_pnl_reported'):+.6f}  "
              f"txs={r['n_txs']}({r.get('txs_missing',0)}miss) fees={r.get('tx_fees_sol',0):.6f}  "
              f"native={r.get('native_diff_sum',0):+.6f}  "
              f"resid={resid if resid is None else round(resid,6)}")
    print(f"--- totals: pnl={tot_pnl:+.6f}  tx_fees={tot_fees:.6f}  residual={tot_resid:+.6f}")
    print()
    latest_lifecycle_split()

if __name__ == "__main__":
    main()
