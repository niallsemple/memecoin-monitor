#!/usr/bin/env python3
"""lp_surf_live.py — live LP-skim probe controller (cost-truth probe).

Watches tracked SOL-Y pools at snapshot cadence (~16s) for a gated burst:
  TRIGGER: trailing fee flow >= SPIKE_SOL_H AND momentum drift >= MOM_GATE
  ENTRY:   node bundle addbins <pool> SIZE 0 surf_probe  (active bin only)
  EXITS:   fill_stop (active bin < entry bin) / flow_dead / fee_stall 120s
           / max_hold 30min  ->  node bundle exit <pool> (auto claim+close+unwrap)
  AFTER:   cost_decomp lifecycle split appended to lp_surf_live.jsonl

Probe size per mandate v3: 0.02 SOL. ONE position at a time. This is a
measurement probe, not a profit engine: its job is to return the true
round-trip cost (entry + exit + slippage) that the sim cannot know.

Safety: requires HFNA_LIVE_ARMED file AND absence of STOP_LIVE_TRADING.
DRY=1 env: log triggers, never enters.
"""
import json, os, subprocess, sys, time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from capacity_watch import fees_sol, LP_MULT, SPIKE_SOL_H
from active_bin_sim import (bin_of, active_price, drift_pct, sol_usdc_ref,
                            MOM_GATE_PCT)

SNAPS = os.path.join(BASE, "bin_snapshots.jsonl")
POOLS = os.path.join(BASE, "capacity_pools.json")
BUNDLE = os.path.join(BASE, "lp_exec", "meteora_lp.bundle.cjs")
LOG = os.path.join(BASE, "lp_surf_live.jsonl")
ARM = os.path.join(BASE, "HFNA_LIVE_ARMED")
STOP = os.path.join(BASE, "STOP_LIVE_TRADING")

SIZE = float(os.environ.get("SURF_SIZE", "0.02"))
DRY = os.environ.get("DRY") == "1"
EXIT_SOL_H = 0.02
STRONG_FLOW_SOL_H = float(os.environ.get("SURF_STRONG_FLOW", "0.15"))
MIN_DRIFT_PCT = float(os.environ.get("SURF_MIN_DRIFT", "0.1"))
STALL_S = 120
MAX_HOLD_S = 1800
COOLDOWN_S = 600
POLL_S = 15

def log(rec):
    rec["t"] = time.time()
    with open(LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec)[:300], flush=True)

def fresh_snap(pool_addr):
    """Take a live snapshot via the bundle — controller owns its data freshness
    (poll-loop gaps of ~190s made file-only reads stale mid-burst)."""
    try:
        r = subprocess.run(["node", BUNDLE, "binsjson", pool_addr],
                           capture_output=True, text=True, timeout=60, cwd=BASE)
        line = next((l for l in r.stdout.splitlines()
                     if l.strip().startswith('{"pool"')), None)
        if not line:
            return None
        d = json.loads(line)
        return {"t": d["t"], "pool": d["pool"], "active_bin": d["activeBin"],
                "bin_step": d["binStep"], "prot_fee_y": int(d["protFeeY"]),
                "prot_fee_x": int(d["protFeeX"]), "bins": d["bins"]}
    except Exception:
        return None

def recent(pool_addr, n=8, fresh=True):
    rows = []
    with open(SNAPS) as f:
        for l in f.readlines()[-4000:]:
            try:
                d = json.loads(l)
            except Exception:
                continue
            if d.get("pool") == pool_addr:
                rows.append(d)
    rows = sorted(rows, key=lambda d: d["t"])[-n:]
    if fresh:
        fs = fresh_snap(pool_addr)
        if fs and (not rows or fs["t"] - rows[-1]["t"] > 5):
            rows.append(fs)
    return rows

def flow_now(rows, meta, sol_usdc):
    if len(rows) < 2:
        return 0.0
    fs = fees_sol(rows[-2], rows[-1], meta, sol_usdc)
    dt_h = (rows[-1]["t"] - rows[-2]["t"]) / 3600
    return (fs * LP_MULT / dt_h) if (fs is not None and dt_h > 0) else 0.0

def bundle(*args, timeout=120):
    r = subprocess.run(["node", BUNDLE, *args], capture_output=True,
                       text=True, timeout=timeout, cwd=BASE)
    return r.stdout + r.stderr

USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

def swap_sol_to_usdc(sol_amt):
    """Swap SOL->USDC via Jupiter primitives; returns (sig, usdc_out)."""
    import live_trader as lt
    q = lt.jupiter_quote(USDC_MINT, sol_amt)
    sig = lt._jupiter_submit(q)
    time.sleep(6)
    return sig, int(q.get("outAmount", 0)) / 1e6

def wallet_sol():
    import urllib.request
    key = open(os.path.join(BASE, "helius_key.txt")).read().strip()
    addr = json.load(open(os.path.join(BASE, "live_wallet.json")))["address"]
    req = urllib.request.Request(
        f"https://mainnet.helius-rpc.com/?api-key={key}",
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getBalance",
                         "params": [addr]}).encode(),
        headers={"Content-Type": "application/json",
                 "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)["result"]["value"] / 1e9

def open_position():
    st_path = os.path.join(BASE, "lp_positions.json")
    try:
        st = json.load(open(st_path))
    except Exception:
        return None
    for p in st.get("positions", []):
        if p.get("status") == "open" and p.get("strategy_tag") == "surf_probe":
            return p
    return None

# probe #2+: only pools with positive trailing sim P&L, strongest first.
# STONK probe #1 measured -9.2% round trip at 0.02 SOL — never re-probe
# a pool the router's own sim shows negative.
POOL_PRIORITY = ["EMBER-USDC", "EMBER-SOL", "MET-SOL", "ZEC-SOL",
                 "ANSEM-SOL", "STONK-SOL"]

def main():
    all_metas = {p["addr"]: p for p in json.load(open(POOLS))["pools"]
                 if p.get("y_sym") in ("SOL", "USDC", "USDT", "USDH")}
    metas = {}
    for name in POOL_PRIORITY:          # preserve priority order
        for a, m in all_metas.items():
            if m["name"] == name:
                metas[a] = m
    log({"kind": "start", "size": SIZE, "dry": DRY,
         "pools": [m["name"] for m in metas.values()]})
    last_exit = 0
    while True:
        if os.path.exists(STOP):
            log({"kind": "halt", "why": "STOP_LIVE_TRADING"})
            break
        if not DRY and not os.path.exists(ARM):
            time.sleep(30)
            continue
        sol_usdc = sol_usdc_ref() or 100
        pos = open_position()
        if pos:
            # monitor for exit
            rows = recent(pos["pool"])
            if len(rows) >= 2:
                ab = rows[-1]["active_bin"]
                age = time.time() - pos["ts"]
                fs = fees_sol(rows[-2], rows[-1], metas.get(pos["pool"], {}), sol_usdc)
                why = None
                if ab < pos["minBinId"]:
                    why = "fill_stop"
                elif age > MAX_HOLD_S:
                    why = "max_hold"
                elif fs is not None and fs <= 0:
                    why = None  # stall handled by time check below
                if why is None and flow_now(rows, metas.get(pos["pool"], {}), sol_usdc) < EXIT_SOL_H and age > 60:
                    why = "flow_dead"
                if why:
                    log({"kind": "exit_trigger", "why": why,
                         "pool": pos["pool"], "age_s": age})
                    if not DRY:
                        out = bundle("exit", pos["pool"])
                        log({"kind": "exit_done", "pool": pos["pool"],
                             "out": out[-400:]})
                        time.sleep(10)
                        sw = subprocess.run([sys.executable, "sweep_to_sol.py"],
                                            capture_output=True, text=True,
                                            cwd=BASE, timeout=300)
                        log({"kind": "sweep", "pool": pos["pool"],
                             "out": (sw.stdout + sw.stderr)[-400:]})
                        time.sleep(10)
                        try:
                            post_bal = wallet_sol()
                            pre = None
                            for l in open(LOG).readlines()[::-1]:
                                r2 = json.loads(l)
                                if r2.get("kind") == "entry_trigger" and r2.get("wallet_pre"):
                                    pre = r2["wallet_pre"]
                                    break
                            if pre:
                                log({"kind": "probe_verdict_auto",
                                     "pool": pos["pool"],
                                     "wallet_before": pre,
                                     "wallet_after": post_bal,
                                     "net_sol": round(post_bal - pre, 6),
                                     "net_pct": round((post_bal - pre) / SIZE * 100, 2)})
                        except Exception as e:
                            log({"kind": "verdict_error", "err": str(e)})
                        dc = subprocess.run([sys.executable, "cost_decomp.py"],
                                            capture_output=True, text=True,
                                            cwd=BASE, timeout=180)
                        log({"kind": "decomp", "pool": pos["pool"],
                             "out": dc.stdout[-800:]})
                    last_exit = time.time()
            time.sleep(POLL_S)
            continue
        if time.time() - last_exit < COOLDOWN_S:
            time.sleep(POLL_S)
            continue
        # scan for gated entry (priority order, router sim-P&L must be >= 0)
        router = {}
        try:
            router = {d["name"]: d for d in json.load(
                open(os.path.join(BASE, "router_state.json")))["pools"]}
        except Exception:
            pass
        for addr, meta in metas.items():
            rd = router.get(meta["name"])
            rows = recent(addr)
            if rd and rd.get("trades", 0) >= 3 and rd.get("net", 0) < 0:
                # router says bleeder — but log if flow gate WOULD have fired,
                # so we can measure what the gate is costing us
                if len(rows) >= 5:
                    fh_b = flow_now(rows, meta, sol_usdc)
                    if fh_b >= STRONG_FLOW_SOL_H:
                        log({"kind": "router_block", "pool": addr,
                             "name": meta["name"], "flow_h": round(fh_b, 4),
                             "router_net": rd.get("net"),
                             "router_trades": rd.get("trades")})
                continue
            if len(rows) < 5:
                continue
            fh = flow_now(rows, meta, sol_usdc)
            if fh < SPIKE_SOL_H:
                continue
            d = drift_pct(rows, len(rows) - 1)
            if d is None or d < MOM_GATE_PCT:
                continue
            # probe #5 lesson: weak flow + zero drift = paying to learn nothing.
            # require either a strong burst (>=0.15 SOL/h) or real upward drift.
            if fh < STRONG_FLOW_SOL_H and d < MIN_DRIFT_PCT:
                continue
            pre_bal = None
            try:
                pre_bal = wallet_sol()
            except Exception:
                pass
            log({"kind": "entry_trigger", "pool": addr, "name": meta["name"],
                 "flow_h": round(fh, 4), "drift_pct": round(d, 3),
                 "active_bin": rows[-1]["active_bin"], "wallet_pre": pre_bal})
            if not DRY:
                if meta["y_sym"] == "SOL":
                    out = bundle("addbins", addr, str(SIZE), "0", "surf_probe")
                else:  # USDC-Y: swap first, deposit USDC
                    sig, usdc = swap_sol_to_usdc(SIZE)
                    log({"kind": "usdc_swap", "sig": sig, "usdc": usdc})
                    out = bundle("addusdc", addr, str(round(usdc, 2)), "0",
                                 "surf_probe")
                log({"kind": "entry_done", "pool": addr, "out": out[-400:]})
            break  # one position at a time
        time.sleep(POLL_S)

if __name__ == "__main__":
    main()
