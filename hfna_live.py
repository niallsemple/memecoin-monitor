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
DEPTH_F = os.path.join(MON, "pool_depth_cache.json")
TXFLOW = os.path.join(MON, "txflow.jsonl")
DENY_F = os.path.join(MON, "paper_denylist.json")
WASH_F = os.path.join(MON, "pool_wash_cache.json")
WASH_MAX_AGE = 86400.0  # organic verdicts stale after 24h
# reflow rebuild (09-13, owner directive "rebuild engine then go live"):
# port the three gates that made hfna_paper_reflow the only positive paper arm
# (19 trades, +0.0048 net, ZERO strikes as of 09-13 morning):
#   1. tx5 tape gate — entry only on confirmed hot tape (>=75 swaps/5min,
#      fresh <150s). Tape strength predicts payoff WITHIN a pool (BN7C
#      tx5=952 paid 3x; every sub-75 window was sub-cost).
#   2. wash denylist — never enter wash-scan-denied pools.
#   3. capped follow — MAX_REPOS immediate re-entries after a tripwire
#      (paper reflow re-centers in-place; live pays real tx cost per re-add,
#      so we exit + re-enter only if ALL gates still pass, max 2 follows).
MIN_SWAPS_5M = 75
TXFLOW_MAX_AGE = 150.0
MAX_REPOS = 2
# LIVE-ONLY blocklist (09-13): "mixed" forensics verdict — dust churn and real
# bursts coexist, so wash_scan does NOT denylist them and paper arms keep
# trading them to learn. Paper-tradeable, NEVER live: capture there is
# dominated by the wash component and unverifiable. (zxTp: 57.8 SOL active
# depth yet capture30 0.0022 < 0.004 floor — uncapturable at 0.1 SOL.)
LIVE_NEVER = {
    "zxTpi4BtaWX3mgdAPoezkMD1hxx8CdeCfrqXMWvSCLX",
    "6WwtGMXueNTv5YrD3nbfXxxS3ANiDEGyXJkTBcnmXLvc",
}

SIZE = 0.1
BINS_BELOW = 2
VAC_DROP = 0.60
FLAT_TH = 5
ELEV_MIN = 1.5
# DEPTH GATE (09-12, 16 live trades): pools with <1000 SOL Y-reserve bled
# -0.0123 over 7 trades; >=1000 SOL pools net +0.0064 and every win came
# from 7k-deep GBR. Raised to 1500 after FpP5 (884 SOL) crossed 1005
# mid-burst and slipped through: marginal pools oscillate around any line
# they hover near. Fail-CLOSED on unknown depth — depth is the primary
# safety filter, a missed trade is cheaper than a shallow pool.
MIN_SOL_RESERVE = 1500.0
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

def latest_swaps5():
    """pool -> (t, swaps_5m) from the newest txflow row (verbatim from reflow)."""
    out = {}
    try:
        with open(TXFLOW) as f:
            for line in f:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                out[r["pool"]] = (r["t"], r.get("swaps_5m", 0))
    except Exception:
        pass
    return out

def main():
    if os.path.exists(KILL):
        print("STOP_LIVE_TRADING present — halting"); return
    armed = os.path.exists(ARMED)
    watch = json.load(open(WATCH_F))["pools"] if os.path.exists(WATCH_F) else []
    st = json.load(open(STATE)) if os.path.exists(STATE) else {
        "pos": None, "seen": {}, "consec_loss": 0, "start_bank": None, "halted": False}
    if st.get("halted"):
        print("pilot HALTED (circuit breaker) — needs manual review"); return
    # revised mandate 09-13 13:39 (owner + external review): extend 24h at
    # 0.1 SOL. Objective changed: not "+1 SOL" but PAIRED live/shadow capture
    # data, cost decomposition, hold-time curves. Profit guard kept as a
    # backstop; real success = 30-50 clean paired windows.
    now0 = time.time()
    if now0 > 1789387890:
        st["halted"] = True
        json.dump(st, open(STATE, "w"), indent=1)
        print("pilot STOPPED: 24h window elapsed"); return
    tgt = st.get("sample3_start", 7.347707709) + 1.0
    last_bank = st.get("last_bank", st.get("sample3_start", 7.347707709))
    if last_bank >= tgt:
        st["halted"] = True
        json.dump(st, open(STATE, "w"), indent=1)
        print(f"pilot STOPPED: profit target reached bank={last_bank:.4f}"); return

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
        exit_reason = None
        # --- fast on-chain tripwire loop (09-12): the -5.6% JBG loss came
        # from snapshot-cadence detection — price fell 7+ bins between poll
        # turns. While armed with an open position, poll the chain directly
        # every ~15s for up to 4 min and fire the tripwire immediately.
        # statusjson gives activeBin + unclaimed feeY for OUR position.
        if armed:
            t0 = time.time()
            missing = 0
            while time.time() - t0 < 150:
                try:
                    rc = run_bundle("statusjson", timeout=60)
                    line = [l for l in (rc.stdout or "").splitlines() if l.strip().startswith("[")][-1]
                    mine = [x for x in json.loads(line) if x.get("pool") == p and not x.get("error")]
                    if not mine:
                        # crash-safe reconcile (09-12): a timeout kill once left
                        # us out on-chain but "open" in state. Two consecutive
                        # misses = the position is gone; reconcile via wallet.
                        missing += 1
                        if missing >= 2:
                            exit_reason = "position gone (reconcile)"
                            break
                        time.sleep(5)
                        continue
                    missing = 0
                    if mine[0].get("activeBin") is not None:
                        ab = mine[0]["activeBin"]
                        pos["feeY_onchain"] = int(mine[0].get("feeY_lamports") or 0) / 1e9
                        # hold-time curve data (revised mandate 09-13): 15s
                        # accrual series lets us reconstruct NetEdge(t) offline
                        pos.setdefault("curve", []).append(
                            [round(time.time() - pos["t_entry"], 1), ab, round(pos["feeY_onchain"], 6)])
                        if ab < pos["low"] - 1:
                            exit_reason = f"fast tripwire ab={ab}<{pos['low']-1}"
                            break
                except Exception:
                    pass
                time.sleep(15)
        cur = [r for r in hist.get(p, []) if r["t"] > pos["last_t"]]
        for r in cur:
            dpf = r["prot_fee_y"] - pos["last_pf"]
            pos["last_t"], pos["last_pf"] = r["t"], r["prot_fee_y"]
            ab = r["active_bin"]
            if dpf > 0 and pos["low"] <= ab <= pos["high"]:
                pos["fees_est"] += min(dpf / 1e9 * lp_mult(p) * (SIZE / (r["liq_active"] / 1e9 + SIZE) if r["liq_active"] > 0 else 0), 0.05 * SIZE)
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
                rc = run_bundle("exit", p, timeout=90)
                log_event(kind="live_exit", pool=p, reason=exit_reason, rc=rc.returncode,
                          out=(rc.stdout or rc.stderr or "")[-300:])
                if rc.returncode != 0:
                    # failed exit (09-12 GBR: tx expired, engine read wallet
                    # mid-flight and booked a false -0.142). Retry once, then
                    # verify on-chain. If the position still exists, keep it
                    # open in state — the next cycle's fast loop re-enters
                    # this path / reconciles. NEVER account on a failed exit.
                    time.sleep(8)
                    rc2 = run_bundle("exit", p, timeout=90)
                    log_event(kind="live_exit_retry", pool=p, rc=rc2.returncode,
                              out=(rc2.stdout or rc2.stderr or "")[-300:])
                    gone = False
                    try:
                        rcs = run_bundle("statusjson", timeout=60)
                        line = [l for l in (rcs.stdout or "").splitlines() if l.strip().startswith("[")][-1]
                        gone = not [x for x in json.loads(line) if x.get("pool") == p and not x.get("error")]
                    except Exception:
                        gone = rc2.returncode == 0
                    if not gone:
                        json.dump(st, open(STATE, "w"), indent=1)
                        print(f"[exit-fail] {p[:8]} position still on-chain — keeping open, retry next cycle")
                        return
                time.sleep(12)  # RPC finality: exit-state visible before sweep
                for _try in range(2):
                    rcs = subprocess.run([sys.executable, os.path.join(MON, "sweep_to_sol.py")],
                                         capture_output=True, text=True, timeout=90)
                    if rcs.returncode == 0:
                        break
                    time.sleep(5)
                # stable wallet read (09-12): sweep proceeds land late; two
                # reads 15s apart, take the settled one, else a third read.
                wa = wallet_sol()
                for _stab in range(3):
                    time.sleep(15)
                    wa2 = wallet_sol()
                    if wa is not None and wa2 is not None and abs(wa2 - wa) < 0.0005:
                        wa = wa2; break
                    wa = wa2 if wa2 is not None else wa
                if wa is not None and pos.get("wallet_before") is not None:
                    real_pnl = wa - pos["wallet_before"]
                    st["last_bank"] = wa
                    # paired live/shadow capture (revised mandate 09-13):
                    # fees_est is the reflow-model shadow on identical bins/
                    # window. capture_ratio = on-chain claimed feeY vs shadow.
                    fee_real = pos.get("feeY_onchain")
                    ratio = (fee_real / pos["fees_est"]) if fee_real is not None and pos["fees_est"] > 0 else None
                    log_event(kind="real_pnl", pool=p, real_pnl=real_pnl,
                              wallet_before=pos["wallet_before"], wallet_after=wa,
                              shadow_fees=round(pos["fees_est"], 6),
                              feeY_onchain=fee_real, capture_ratio=ratio,
                              hold_s=round(time.time() - pos["t_entry"], 1),
                              exit_reason=exit_reason)
                    if pos.get("curve"):
                        log_event(kind="fee_curve", pool=p, curve=pos["curve"][-40:])
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
            # reflow gate 3: capped follow. A tripwire means price drifted out
            # of range — reflow re-centers in place (paper, free); live pays a
            # real tx cost per re-add, so we EXIT (already done above) then
            # clear the cooldown for an immediate re-entry ONLY if every gate
            # still passes on the next scan, max MAX_REPOS follows per window.
            # Uncapped follow is what churned 55Ev for -0.005 on 09-13.
            if "tripwire" in exit_reason:
                fl = st.setdefault("follow", {})
                rec = fl.get(p) or {"n": 0, "t": 0}
                rec["n"] = rec["n"] + 1 if time.time() - rec["t"] < 1200 else 1
                rec["t"] = time.time()
                fl[p] = rec
                if rec["n"] <= MAX_REPOS:
                    st["seen"][p] = 0
                    log_event(kind="follow_arm", pool=p, follow_n=rec["n"])
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
    deny = set()
    try:
        deny = set(json.load(open(DENY_F))["pools"])
    except Exception:
        pass
    # forensics gate (09-13, qhJ7 incident): denylist-only is REACTIVE — qhJ7
    # entered live unclassified and forensicked wash WHILE WE HELD IT
    # (-0.00023 scratch). Live now requires a POSITIVE organic verdict,
    # fresh <24h. Fail-closed on unknown — same philosophy as the depth gate.
    washc = {}
    try:
        washc = json.load(open(WASH_F))
    except Exception:
        pass
    sw5 = latest_swaps5()
    for p in watch:
        r = latest.get(p)
        if not r:
            continue
        # reflow gate 2: wash denylist — never enter denied pools
        if p in deny or p in LIVE_NEVER:
            continue
        wv = washc.get(p)
        if not wv or wv.get("verdict") != "organic" or time.time() - wv.get("t", 0) > WASH_MAX_AGE:
            continue
        # reflow gate 1: confirmed hot tape, fresh (<150s), >=75 swaps/5min.
        # Stale or missing tape = no entry (fail closed, same as depth).
        tf = sw5.get(p)
        if not tf or time.time() - tf[0] > TXFLOW_MAX_AGE or tf[1] < MIN_SWAPS_5M:
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
        if tax_bps > 50:
            continue
        tax_drag = 0.0
        # depth gate: cached 1h, fetched on-chain via bundle depthjson.
        dc = json.load(open(DEPTH_F)) if os.path.exists(DEPTH_F) else {}
        ent = dc.get(p)
        if not ent or time.time() - ent.get("t", 0) > 3600:
            rc = run_bundle("depthjson", p)
            try:
                line = [l for l in (rc.stdout or "").splitlines() if l.strip().startswith('{"pool"')][-1]
                ent = {"t": time.time(), "sol": json.loads(line).get("solReserveY", 0)}
                dc[p] = ent
                json.dump(dc, open(DEPTH_F, "w"), indent=1)
            except Exception:
                ent = None
        if ent is None or ent["sol"] < MIN_SOL_RESERVE:
            continue  # fail closed: unknown or shallow depth = no trade
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
