#!/usr/bin/env python3
"""LP guardian + compounder for the Meteora DLMM experiment.

Every run:
  1. On-chain state per open position (via lp_exec/meteora_lp.bundle.cjs statusjson)
  2. Pool state from Meteora datapi (tvl, vol24, blacklisted)
  3. DANGER -> emergency exit (remove 100% + claim + close), then sweep to SOL:
       - active bin fell BELOW position range (position = 100% token X; price
         crashed through; realize and swap out per SOL-only rule)
       - pool TVL collapsed >55% vs baseline
       - pool blacklisted flag flipped on
  4. COMPOUND -> claim fees when claimable SOL-side > 0.003 SOL (~60x tx cost);
     claimed fees land in wallet; SOL side re-deposits on next 'add' cycle.
     (Token-X fee side is left for the sweeper to convert.)
  5. Baselines (entry tvl/vol24) recorded on first sight.

Logs to lp_guardian.log and lp_guardian_actions.jsonl.
"""
import json, os, subprocess, sys, time, urllib.request

MON = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.join(MON, "lp_exec", "meteora_lp.bundle.cjs")
STATE_F = os.path.join(MON, "lp_positions.json")
LOG_F = os.path.join(MON, "lp_guardian.log")
ACT_F = os.path.join(MON, "lp_guardian_actions.jsonl")
API = "https://dlmm.datapi.meteora.ag"
CLAIM_MIN_SOL = 0.003
TVL_COLLAPSE = 0.55


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line)
    with open(LOG_F, "a") as f:
        f.write(line + "\n")


def action(kind, **kw):
    with open(ACT_F, "a") as f:
        f.write(json.dumps({"t": time.time(), "kind": kind, **kw}) + "\n")


def run_lp(*args):
    r = subprocess.run(["node", BUNDLE, *args], capture_output=True, text=True, timeout=240)
    out = (r.stdout or "") + (r.stderr or "")
    # strip noisy warnings
    lines = [l for l in out.splitlines() if l.strip() and "bigint" not in l
             and "punycode" not in l and "Deprecation" not in l and "trace-deprecation" not in l]
    return r.returncode, "\n".join(lines)


def datapi_pool(addr):
    try:
        req = urllib.request.Request(f"{API}/pools/{addr}", headers={"User-Agent": "curl/8.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except Exception:
        return None


def main():
    st = json.load(open(STATE_F))
    open_pos = [p for p in st["positions"] if p["status"] == "open"]
    if not open_pos:
        log("no open positions"); return

    rc, out = run_lp("statusjson")
    fake = os.environ.get("GUARDIAN_FAKE_STATUS")  # test hook: path to JSON file
    if fake:
        rc, out = 0, open(fake).read()
    try:
        chain = json.loads(out[out.index("["):])
    except Exception:
        log(f"statusjson parse failed rc={rc}: {out[:200]}"); return
    by_pos = {c["position"]: c for c in chain}

    for p in open_pos:
        c = by_pos.get(p["position"])
        name = p.get("name") or p["pool"][:8]
        if not c or c.get("error"):
            log(f"{name}: on-chain read failed: {(c or {}).get('error')}"); continue

        # baseline on first sight
        d = datapi_pool(p["pool"])
        tvl = (d or {}).get("tvl") or 0
        vol24 = (((d or {}).get("volume") or {}).get("24h")) or 0
        black = (d or {}).get("is_blacklisted")
        if "base_tvl" not in p and tvl:
            p["base_tvl"] = tvl; p["base_vol24"] = vol24
        json.dump(st, open(STATE_F, "w"), indent=1)

        fee_y = int(c.get("feeY_lamports") or 0)
        fee_x = int(c.get("feeX_lamports") or 0)
        active, lo, hi = c["activeBin"], c["lowerBinId"], c["upperBinId"]
        log(f"{name}: active={active} range=[{lo},{hi}] tvl=${tvl:,.0f} vol24=${vol24:,.0f} "
            f"feeY={fee_y/1e9:.6f}SOL feeX={fee_x}")

        danger = None
        if active < lo:
            danger = f"price fell through range (active {active} < {lo}) — position is all token-X"
        elif black:
            danger = "pool blacklisted"
        elif p.get("base_tvl") and tvl < p["base_tvl"] * (1 - TVL_COLLAPSE):
            danger = f"TVL collapsed {tvl/p['base_tvl']:.0%} of baseline"
        if danger:
            log(f"{name}: EMERGENCY EXIT — {danger}")
            rc2, out2 = run_lp("exit", p["pool"])
            action("emergency_exit", name=name, pool=p["pool"], reason=danger, out=out2[:400])
            if "EXITED" in out2:
                p["status"] = "exited"; p["exit_reason"] = danger
                json.dump(st, open(STATE_F, "w"), indent=1)
                log(f"{name}: exited ok")
            else:
                log(f"{name}: EXIT FAILED rc={rc2}: {out2[:300]}")
            continue

        # back-in-range / drifted-out transition alerts
        in_rng = bool(c["inRange"])
        was = p.get("was_in_range")
        if was is not None and in_rng != was:
            if in_rng:
                log(f"{name}: BACK IN RANGE — fee accrual resumed")
                action("back_in_range", name=name, pool=p["pool"], active=active,
                       range=[lo, hi], feeY=fee_y)
            else:
                log(f"{name}: drifted out of range — fee accrual paused")
                action("out_of_range", name=name, pool=p["pool"], active=active,
                       range=[lo, hi], side="above" if active > hi else "below")
        p["was_in_range"] = in_rng
        json.dump(st, open(STATE_F, "w"), indent=1)

        if not in_rng and active > hi:
            log(f"{name}: idle above range (pure SOL, no fees) — watching")
            # wide-arm re-center: price ran up through the range; position is pure
            # SOL earning nothing. After 2 consecutive passes above range, exit
            # (claim+close refunds rent) and attempt a gated re-deploy at the new
            # price. Re-deploy refuses unless the watchlist still qualifies.
            if p.get("strategy_tag") == "wide_arm_v2":
                p["above_range_passes"] = p.get("above_range_passes", 0) + 1
                json.dump(st, open(STATE_F, "w"), indent=1)
                if p["above_range_passes"] >= 2:
                    log(f"{name}: RE-CENTER — above range {p['above_range_passes']} passes; exit + gated redeploy")
                    rc2, out2 = run_lp("exit", p["pool"])
                    action("recenter_exit", name=name, pool=p["pool"], out=out2[:400])
                    if "EXITED" in out2:
                        p["status"] = "exited"; p["exit_reason"] = "recenter_above_range"
                        json.dump(st, open(STATE_F, "w"), indent=1)
                        rc5 = subprocess.run([sys.executable, os.path.join(MON, "sweep_to_sol.py")],
                                             capture_output=True, text=True, timeout=280)
                        action("recenter_sweep", name=name, rc=rc5.returncode)
                        rc6 = subprocess.run([sys.executable, os.path.join(MON, "lp_deploy_watchlist.py"), name],
                                             capture_output=True, text=True, timeout=280)
                        action("recenter_redeploy", name=name, rc=rc6.returncode,
                               out=(rc6.stdout or "")[-400:])
                        log(f"{name}: redeploy rc={rc6.returncode} (refusal = data no longer qualifies)")
                    else:
                        log(f"{name}: RE-CENTER EXIT FAILED rc={rc2}: {out2[:300]}")
        else:
            if p.get("above_range_passes"):
                p["above_range_passes"] = 0
                json.dump(st, open(STATE_F, "w"), indent=1)

        if fee_y >= CLAIM_MIN_SOL * 1e9:
            log(f"{name}: claiming fees ({fee_y/1e9:.6f} SOL side)")
            rc3, out3 = run_lp("claim", p["pool"])
            action("claim", name=name, feeY=fee_y, feeX=fee_x, out=out3[:300])
            log(f"{name}: claim rc={rc3}")
            if rc3 == 0:
                # SOL-only rule: convert any token-side fees the claim dropped in wallet
                rc4 = subprocess.run([sys.executable, os.path.join(MON, "sweep_to_sol.py")],
                                     capture_output=True, text=True, timeout=280)
                action("post_claim_sweep", name=name, rc=rc4.returncode,
                       out=(rc4.stdout or "")[-400:])
                log(f"{name}: post-claim sweep rc={rc4.returncode}")

    log("guardian pass complete")


if __name__ == "__main__":
    main()
