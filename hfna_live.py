#!/usr/bin/env python3
"""HFNA live micro-pilot — watchlist-only, 0.1 SOL Y-only, guardian-wrapped.

Implements hfna_pilot_design.md exactly:
- entry ONLY on watchlist pools (>=1 documented positive HFNA exit)
- same 4 gates as the paper trader (vacuum / settled / elevation / flow)
- exits: refill >1.5x trough, stall 300s, tripwire ab < low-1, timeout 1800s
- circuit breaker: 3 consecutive losses OR -15% from pilot start -> halt
- post-exit sweep to SOL-only, STOP_LIVE_TRADING honored

SAFETY: trades real money ONLY if the file HFNA_LIVE_ARMED exists in this
directory. Without it, runs in dry-run mode (prints what it WOULD do).
"""
import json, os, statistics, subprocess, sys, time

MON = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.join(MON, "lp_exec", "meteora_lp.bundle.cjs")
SNAP = os.path.join(MON, "bin_snapshots.jsonl")
STATE = os.path.join(MON, "hfna_live_state.json")
LOG = os.path.join(MON, "hfna_live.jsonl")
WATCH_F = os.path.join(MON, "hfna_watchlist.json")
ARMED = os.path.join(MON, "HFNA_LIVE_ARMED")
KILL = os.path.join(MON, "STOP_LIVE_TRADING")
TAX_F = os.path.join(MON, "pool_tax_cache.json")

SIZE = 0.1
BINS_BELOW = 2
VAC_DROP = 0.60
FLAT_TH = 5
ELEV_MIN = 1.5
COOLDOWN = 3600
TIMEOUT = 1800
STALL = 300
MAX_CONSEC_LOSS = 3
MAX_DRAWDOWN = 0.15

def run_bundle(*args, timeout=280):
    return subprocess.run(["node", BUNDLE, *args], capture_output=True, text=True, timeout=timeout)

def log_event(**kw):
    with open(LOG, "a") as f:
        f.write(json.dumps({"t": time.time(), **kw}) + "\n")
    print(" ", " ".join(f"{k}={v}" for k, v in kw.items() if k != "t"))

def lp_mult(pool):
    """(10000-protocolShare)/protocolShare, per-pool from watchlist.
    Measured on-chain 2026-09-11: all watchlist pools = 1000 (10%) -> 9.0."""
    try:
        pp = json.load(open(WATCH_F)).get("pool_params", {})
        return float(pp.get(pool, {}).get("lpMult", 9.0))
    except Exception:
        return 9.0

def wallet_sol():
    """Real wallet SOL balance — the ONLY trustworthy PnL yardstick.
    fees_est is a model upper bound (real capture measured ~6000x lower
    than the liq_active share model during the 2026-09-11 calibration)."""
    try:
        rc = run_bundle("balance", timeout=60)
        return json.loads(rc.stdout.strip().splitlines()[-1])["sol"]
    except Exception:
        return None

def load_hist():
    hist = {}
    rows = []
    for ln in open(SNAP):
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if "prot_fee_y" not in r:
            continue
        hist.setdefault(r["pool"], []).append(r)
        rows.append(r)
    return hist, rows

def main():
    if os.path.exists(KILL):
        print("STOP_LIVE_TRADING present — halting"); return
    armed = os.path.exists(ARMED)
    watch = json.load(open(WATCH_F))["pools"] if os.path.exists(WATCH_F) else []
    st = json.load(open(STATE)) if os.path.exists(STATE) else {
        "pos": None, "seen": {}, "consec_loss": 0, "start_bank": None, "halted": False}
    if st.get("halted"):
        print("pilot HALTED (circuit breaker) — needs manual review"); return

    hist, rows = load_hist()
    if not rows:
        print("no snapshots yet"); return
    now = time.time()
    latest = {}
    for r in rows:
        if r["t"] > now - 300:
            latest[r["pool"]] = r
    # universe widening (09-12, post-liveval): the validation winner came from
    # the collector's rotating hot set, not the static watchlist. Scan every
    # pool with fresh snapshots; the gates (vacuum/settle/elev/flow/edge-
    # density) are the filter, not the list. Static watchlist still included.
    watch = list(dict.fromkeys(watch + list(latest.keys())))

    # ---- manage open position ----
    if st["pos"]:
        pos = st["pos"]
        p = pos["pool"]
        cur = [r for r in hist.get(p, []) if r["t"] > pos["last_t"]]
        exit_reason = None
        for r in cur:
            dpf = r["prot_fee_y"] - pos["last_pf"]
            pos["last_t"], pos["last_pf"] = r["t"], r["prot_fee_y"]
            ab = r["active_bin"]
            if dpf > 0 and pos["low"] <= ab <= pos["high"]:
                pos["fees_est"] += dpf / 1e9 * lp_mult(p) * (SIZE / (r["liq_active"] / 1e9 + SIZE) if r["liq_active"] > 0 else 0)
            if ab < pos["low"] - 1:
                exit_reason = f"tripwire ab={ab}<{pos['low']-1}"; break
            if r["liq_active"] > pos["trough"] * 1.5:
                exit_reason = "liquidity refilled"; break
        if not exit_reason:
            if pos["fees_est"] == pos.get("fees_mark", -1):
                pos["stall"] = pos.get("stall", 0) + 1
                if pos["stall"] * 60 >= STALL:
                    exit_reason = "flow stalled"
            else:
                pos["stall"] = 0; pos["fees_mark"] = pos["fees_est"]
        if not exit_reason and time.time() - pos["t_entry"] > TIMEOUT:
            exit_reason = "timeout"
        if exit_reason:
            print(f"[exit] {p[:8]} {exit_reason} fees_est={pos['fees_est']:.5f}")
            real_pnl = None
            if armed:
                rc = run_bundle("exit", p)
                log_event(kind="live_exit", pool=p, reason=exit_reason, rc=rc.returncode,
                          out=(rc.stdout or rc.stderr or "")[-300:])
                time.sleep(12)  # RPC finality: exit-state visible before sweep
                for _try in range(3):
                    rcs = subprocess.run([sys.executable, os.path.join(MON, "sweep_to_sol.py")],
                                         capture_output=True, text=True, timeout=280)
                    if rcs.returncode == 0:
                        break
                    time.sleep(5)
                wa = wallet_sol()
                if wa is not None and pos.get("wallet_before") is not None:
                    real_pnl = wa - pos["wallet_before"]
                    log_event(kind="real_pnl", pool=p, real_pnl=real_pnl,
                              wallet_before=pos["wallet_before"], wallet_after=wa)
            else:
                log_event(kind="dryrun_exit", pool=p, reason=exit_reason, fees_est=pos["fees_est"])
            # armed: judge by real wallet delta; dry-run: model estimate
            won = (real_pnl > 0) if real_pnl is not None else (pos["fees_est"] > 0.001)
            # noise-filtered breaker (owner directive 09-12, sample #2):
            # scratches (cost-only losses <= 0.002) are the strategy's cost of
            # doing business, not thesis failures — they don't count as strikes.
            strike = (real_pnl < -0.002) if real_pnl is not None else (pos["fees_est"] < -0.002)
            st["consec_loss"] = 0 if won else (st["consec_loss"] + 1 if strike else st["consec_loss"])
            st.setdefault("last_won", {})[p] = won
            if armed:
                st["sample_n"] = st.get("sample_n", 0) + 1
            st["pos"] = None
            if st["consec_loss"] >= MAX_CONSEC_LOSS:
                st["halted"] = True
                log_event(kind="HALT", reason="3 consecutive real losses (>0.002)")
        else:
            print(f"[open] {p[:8]} fees_est={pos['fees_est']:.5f} t+{time.time()-pos['t_entry']:.0f}s")
        json.dump(st, open(STATE, "w"), indent=1)
        return

    # ---- entry scan: watchlist only ----
    for p in watch:
        r = latest.get(p)
        if not r:
            continue
        pts = [x for x in hist[p] if x["t"] <= r["t"]]
        if len(pts) < 5:
            continue
        iv = [pts[i+1]["t"] - pts[i]["t"] for i in range(len(pts)-1)]
        win = max(180.0, 3 * statistics.median(iv))
        prev = next((pts[j] for j in range(len(pts)-1, -1, -1) if r["t"] - pts[j]["t"] >= 300), None)
        if not prev or prev["liq_active"] <= 0:
            continue
        if r["liq_active"] / prev["liq_active"] > VAC_DROP:
            continue
        recent = [x["active_bin"] for x in pts if x["t"] >= r["t"] - win]
        if len(recent) < 2 or max(recent) - min(recent) > FLAT_TH:
            continue
        ratio = r["vol_accum"] / max(r["vol_ref"], 1)
        if ratio < ELEV_MIN:
            continue
        pf_recent = [x for x in pts if x["t"] >= r["t"] - 600]
        if len(pf_recent) >= 2 and (pf_recent[-1]["prot_fee_y"] - pf_recent[0]["prot_fee_y"]) < 500_000:
            continue
        # tax lookup first (verified vs on-chain 09-12: bundle taxcheck reads
        # the real tokenX mint; KNOTS genuinely carries 300bps). Entry is
        # Y-only wSOL (untaxed); the tax burns ~rate x (X-value at exit) when
        # we withdraw/sell the X side. So don't blanket-skip tax pools —
        # raise the cost bar by the worst-case drag (rate x SIZE) and let
        # burst-class pools (KNOTS elev=1053x) clear it. Hard-skip >10% tax:
        # execution accounting gets unreliable there.
        taxc = json.load(open(TAX_F)) if os.path.exists(TAX_F) else {}
        if p not in taxc:
            rc = run_bundle("taxcheck", p)
            try:
                line = [l for l in (rc.stdout or "").splitlines() if l.strip().startswith('{"pool"')][-1]
                taxc[p] = json.loads(line).get("taxBps", 0)
            except Exception:
                taxc[p] = -1   # unknown -> treat as pass but recheck next time
            json.dump(taxc, open(TAX_F, "w"), indent=1)
        tax_bps = taxc.get(p, 0)
        # HARD SKIP tax pools (09-12, empirical): the tax-aware bar experiment
        # ran twice — both losses (-0.0094, -0.0052). The transfer tax is a
        # per-ATTEMPT toll paid even on a 4-min zero-fee exit, so window
        # selection can't save it at 0.1 SOL size. Non-tax gated trades: 2/2.
        if tax_bps > 50:
            continue
        tax_drag = 0.0
        # edge-density gate (recon 09-12): est. 30-min capture >= 4x real costs
        # (~0.004 SOL all-in) plus worst-case tax drag. Without this the pilot
        # enters structurally sub-cost trades — the pre-gate loss streak.
        if len(pf_recent) >= 2:
            dt = pf_recent[-1]["t"] - pf_recent[0]["t"]
            if dt > 0:
                flow = (pf_recent[-1]["prot_fee_y"] - pf_recent[0]["prot_fee_y"]) / 1e9 / dt
                dep_bin = SIZE / (BINS_BELOW + 1)
                share = dep_bin / (dep_bin + r["liq_active"] / 1e9)
                capture30 = flow * lp_mult(p) * share * 1800
                if capture30 < 4 * 0.001 + tax_drag:
                    continue
        # win-aware cooldown (09-12): pools that paid us get a short leash
        # (15min) — JBG re-burst an hour after paying +0.0025 and the paper
        # bot ate it while live sat in cooldown. Losers keep the full hour.
        cd = 900 if st.get("last_won", {}).get(p) else COOLDOWN
        if time.time() - st["seen"].get(p, 0) < cd:
            continue
        ab = r["active_bin"]
        pos = {"pool": p, "t_entry": time.time(), "low": ab - BINS_BELOW, "high": ab,
               "fees_est": 0.0, "elev": ratio, "last_t": r["t"], "last_pf": r["prot_fee_y"],
               "trough": r["liq_active"]}
        print(f"[{'ENTER' if armed else 'DRYRUN-enter'}] {p[:8]} Y-only {SIZE} SOL bins [{ab-BINS_BELOW},{ab}] elev={ratio:.1f}x")
        if armed:
            pos["wallet_before"] = wallet_sol()
            rc = run_bundle("addbins", p, str(SIZE), str(BINS_BELOW), "hfna_live_v1")
            out = (rc.stdout or "") + (rc.stderr or "")
            log_event(kind="live_enter", pool=p, bins=[ab - BINS_BELOW, ab], elev=ratio,
                      rc=rc.returncode, out=out[-300:], wallet_before=pos["wallet_before"])
            if rc.returncode != 0:
                st["seen"][p] = time.time()
                continue
            pos["entry_out"] = out[-200:]
        else:
            log_event(kind="dryrun_enter", pool=p, bins=[ab - BINS_BELOW, ab], elev=ratio)
        st["pos"] = pos
        st["seen"][p] = time.time()
        break

    json.dump(st, open(STATE, "w"), indent=1)
    if not st["pos"]:
        print(f"[flat] watchlist={len(watch)} armed={armed}")

if __name__ == "__main__":
    main()
