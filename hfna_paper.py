#!/usr/bin/env python3
"""hfna_paper.py — paper trader for HFNA windows (memo #37, cost model v1).

Pass-based: each invocation processes new bin_snapshots.jsonl rows since the last
watermark and advances at most one open paper position.

Entry (all gates must pass on the same pool):
  1. vacuum:    liq_active <= 60% of value ~300s ago
  2. settle:    active bin drift <= 5 bins over adaptive window (~3x cadence)
  3. elevation: vol_accum / vol_ref >= 1.5
Position: paper Y-only 0.1 SOL spread over 3 bins [ab-2, ab].

Per-interval fee capture approximation:
  pool LP fees ~= d(prot_fee_y) x 20 (DLMM default 5% protocol share)
  capture    = lp_fees_interval x our_liq / (liq_active + our_liq)
               when active bin inside our range, else 0.

Exit: fee decayed (ratio < 1.2), liquidity refilled (liq_active > 1.5x trough),
      timeout 30min, or tripwire (active bin < low - 1 -> markout applied).
Net = fees - 0.001 fixed cost - markout.

Logs: hfna_paper.jsonl ; state: hfna_paper_state.json
"""
import json, os, statistics, time

MON = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(MON, "bin_snapshots.jsonl")
STATE = os.path.join(MON, "hfna_paper_state.json")
LOG = os.path.join(MON, "hfna_paper.jsonl")

SIZE = 0.1            # SOL deployed
FIXED_COST = 0.001    # tx fees round trip
# LP fee multiplier = (10000 - protocolShare) / protocolShare, per-pool.
# Measured on-chain 2026-09-11: all watchlist pools have protocolShare=1000
# (10% protocol cut) -> lpMult 9.0, not the 20 previously assumed.
WATCH_F = os.path.join(MON, "hfna_watchlist.json")

def lp_mult(pool):
    try:
        pp = json.load(open(WATCH_F)).get("pool_params", {})
        return float(pp.get(pool, {}).get("lpMult", 9.0))
    except Exception:
        return 9.0
VAC_DROP = 0.60
ELEV_MIN = 1.5
FLAT_TH = 5
TIMEOUT_S = 1800

def load_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {"watermark": 0, "pos": None, "bankroll": 1.0, "trades": 0,
                "wins": 0, "seen": {}}

def fee_rate(d):
    """total fee rate estimate: base + variable (capped 10%)."""
    bs = d.get("bin_step", 100)
    bf = d.get("base_factor", 0)
    va, vr = d.get("vol_accum", 0), d.get("vol_ref", 0)
    vfc = d.get("var_fee_ctl", 0)
    base = bf * bs / 1e6                       # %
    var = ((va * bs) ** 2) * vfc / 1e11 / 1e6  # % (approx DLMM formula)
    return min(base + var, 10.0) / 100         # fraction

def main():
    st = load_state()
    rows = []
    with open(SNAP) as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("liq_active") and d.get("prot_fee_y") is not None:
                rows.append(d)
    rows = [r for r in rows if r["t"] > st["watermark"]]
    if not rows:
        print("hfna_paper: no new rows")
        return
    st["watermark"] = max(r["t"] for r in rows)

    # per-pool history incl. some context before watermark
    hist = {}
    with open(SNAP) as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("liq_active") and d.get("prot_fee_y") is not None:
                hist.setdefault(d["pool"], []).append(d)
    for p in hist:
        hist[p].sort(key=lambda r: r["t"])

    pos = st["pos"]

    # ---- manage open position ----
    if pos:
        p = pos["pool"]
        cur = [r for r in hist.get(p, []) if r["t"] > pos["last_t"]]
        for r in cur:
            prev_t = pos["last_t"]
            dt = r["t"] - prev_t
            dpf = r["prot_fee_y"] - pos["last_pf"]
            pos["last_t"], pos["last_pf"] = r["t"], r["prot_fee_y"]
            ab = r["active_bin"]
            if dpf > 0 and pos["low"] <= ab <= pos["high"]:
                lp_fees = dpf / 1e9 * lp_mult(p)
                share = SIZE / (r["liq_active"] / 1e9 + SIZE) if r["liq_active"] > 0 else 0
                # liq_active is raw lamports-ish; normalize via pool scale factor
                pos["fees"] += lp_fees * share
            # tripwire: price fell below range
            if ab < pos["low"] - 1:
                bs = r.get("bin_step", 100)
                price_ratio = (1 + bs / 1e4) ** (ab - pos["low"])
                markout = SIZE * max(0, 1 - price_ratio)
                pos["markout"] = markout
                pos["exit_reason"] = f"tripwire ab={ab}<{pos['low']-1}"
                break
            # exits
            ratio = r["vol_accum"] / max(r["vol_ref"], 1)
            if ratio < 1.2:
                pos["exit_reason"] = f"fee decayed ({ratio:.2f}x)"
                break
            if r["liq_active"] > pos["trough"] * 1.5:
                pos["exit_reason"] = "liquidity refilled"
                break
            # stall exit: no fee progress for 300s -> flow is dead (covers
            # vol_ref=0 pools where the decay exit can never fire)
            if pos["fees"] == pos.get("fees_at_progress", -1):
                pos["stall_s"] = pos.get("stall_s", 0) + dt
            else:
                pos["fees_at_progress"] = pos["fees"]
                pos["stall_s"] = 0
            if pos.get("stall_s", 0) >= 300:
                pos["exit_reason"] = "flow stalled 300s"
                break
            if r["t"] - pos["t_entry"] > TIMEOUT_S:
                pos["exit_reason"] = "timeout"
                break
        # wall-clock backstop: if the pool stops being tracked, rows stop
        # arriving — close on wall time so positions can't get stuck
        if not pos.get("exit_reason") and time.time() - pos["t_entry"] > TIMEOUT_S:
            pos["exit_reason"] = "timeout (wall-clock, pool untracked)"
        if pos.get("exit_reason"):
            net = pos["fees"] - FIXED_COST - pos.get("markout", 0)
            st["bankroll"] += net
            st["trades"] += 1
            st["wins"] += 1 if net > 0 else 0
            with open(LOG, "a") as f:
                f.write(json.dumps({
                    "t": time.time(), "pool": p, "entry_t": pos["t_entry"],
                    "fees": pos["fees"], "markout": pos.get("markout", 0),
                    "net": net, "reason": pos["exit_reason"],
                    "elev": pos["elev"], "bankroll": st["bankroll"],
                    "mult": lp_mult(p),
                }) + "\n")
            print(f"[exit] {p[:8]} {pos['exit_reason']} fees={pos['fees']:.5f} "
                  f"markout={pos.get('markout',0):.5f} net={net:+.5f} bank={st['bankroll']:.4f}")
            st["pos"] = None
        else:
            print(f"[open] {p[:8]} fees={pos['fees']:.5f} t+{time.time()-pos['t_entry']:.0f}s")

    # ---- look for entry if flat ----
    if not st["pos"]:
        for r in rows:
            p = r["pool"]
            pts = [x for x in hist[p] if x["t"] <= r["t"]]
            if len(pts) < 5:
                continue
            iv = [pts[i+1]["t"] - pts[i]["t"] for i in range(len(pts)-1)]
            win = max(180.0, 3 * statistics.median(iv))
            # vacuum check
            prev = next((pts[j] for j in range(len(pts)-1, -1, -1)
                         if r["t"] - pts[j]["t"] >= 300), None)
            if not prev or prev["liq_active"] <= 0:
                continue
            if r["liq_active"] / prev["liq_active"] > VAC_DROP:
                continue
            # settle check: drift over last `win`
            recent = [x["active_bin"] for x in pts if x["t"] >= r["t"] - win]
            if len(recent) < 2 or max(recent) - min(recent) > FLAT_TH:
                continue
            # elevation check
            ratio = r["vol_accum"] / max(r["vol_ref"], 1)
            if ratio < ELEV_MIN:
                continue
            # actual-flow check: fee RATE is not fee FLOW — require real recent
            # protocol-fee delta (>= 0.0005 SOL over ~10min) so dead pools with
            # capped-but-idle fees (vol_ref=0 artifacts) can't enter
            pf_recent = [x for x in pts if x["t"] >= r["t"] - 600]
            if len(pf_recent) >= 2 and (pf_recent[-1]["prot_fee_y"] - pf_recent[0]["prot_fee_y"]) < 500_000:
                continue
            # edge-density gate (KNOTS/GBR recon, 2026-09-12): expected 30-min
            # capture must clear 2x round-trip costs, else the trade is
            # structurally sub-cost no matter the timing.
            #   capture_30 = dProtY_rate * lpMult * share * 1800
            #   share = per-bin dep / (per-bin dep + liq_active)
            if len(pf_recent) >= 2:
                dt = pf_recent[-1]["t"] - pf_recent[0]["t"]
                if dt > 0:
                    flow = (pf_recent[-1]["prot_fee_y"] - pf_recent[0]["prot_fee_y"]) / 1e9 / dt
                    dep_bin = SIZE / 3.0
                    share = dep_bin / (dep_bin + r["liq_active"] / 1e9)
                    capture30 = flow * lp_mult(p) * share * 1800
                    # 4x FIXED_COST ~= real all-in round trip (~0.004 SOL:
                    # entry + exit + claims + priority), per recon cost audit
                    if capture30 < 4 * FIXED_COST:
                        continue
            # cooldown: one trade per pool per hour
            last_done = st["seen"].get(p, 0)
            if time.time() - last_done < 3600:
                continue
            ab = r["active_bin"]
            st["pos"] = {
                "pool": p, "t_entry": r["t"], "low": ab - 2, "high": ab,
                "fees": 0.0, "markout": 0.0, "elev": ratio,
                "last_t": r["t"], "last_pf": r["prot_fee_y"],
                "trough": r["liq_active"],
            }
            st["seen"][p] = time.time()
            print(f"[enter] {p[:8]} HFNA paper Y-only {SIZE} SOL bins [{ab-2},{ab}] elev={ratio:.1f}x")
            break

    json.dump(st, open(STATE, "w"), indent=1)

if __name__ == "__main__":
    main()
