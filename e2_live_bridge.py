"""e2_live_bridge.py — §427: gated live-entry bridge for h16_early2.

When the forward test clears the gate (3-5 opens at backtest-like
profile), flipping LIVE_E2_ENABLED to True makes each h16e2_open event
place a REAL micro-size curve buy (SIZE_SOL) and register it with
live_trader.open_position(mode="e2_trial") — exits then run through the
existing exit_watch stack (bank12x at +20%, panic stop, timestop).

Until the flag flips, every event is logged as bridge_would_buy — a dry
run of the exact live path (same guard checks, same sizing) so the gate
decision is made on the bridge's OWN dry-run record, not just the shadow.

Guardrails: flag default False; one concurrent e2 position max; daily
loss cap; never touches the wallet when disabled.
"""
import json
import time
from pathlib import Path

MON = Path(__file__).resolve().parent
SHADOW_LOG = MON / "h16_early2.jsonl"
STATE = MON / "e2_bridge_state.json"
LOG = MON / "e2_bridge.jsonl"

LIVE_E2_ENABLED = True         # §439: OWNER FLIPPED 2026-09-06 ~21:16 BST
                               # ("go live"). Gate evidence: 3+ fresh
                               # would-buys at sub-20s lag, fresh-cadence
                               # +4.6%/trade gross at flip time.
SIZE_SOL = 0.02                # micro-size trial entries
SEED_FLOOR_SOL = 4.0           # §442: live fire only on seed >= 4 SOL
# §450: seed-fingerprint denylist. Farms rotate creator wallets but keep
# their fixed playbook seed amounts (create-tx solAmount on a fixed curve).
# 5.264197529: observed 5/5 losses across TWO creator wallets (7umWEB7b
# denylisted §445; CWeJoMKF §450) — every launch with this exact seed was
# a manufactured dump. Tolerance covers float fuzz only.
SEED_DENY = [5.264197529]
SEED_DENY_TOL = 0.0005
MAX_CONCURRENT = 1
DAILY_LOSS_CAP_SOL = 0.10      # stop for the day if realized losses exceed
STALE_OPEN_S = 150             # §433: never buy on backfilled opens — after
                               # any driver outage, batched catch-up scoring
                               # emits opens whose entry tick is long past;
                               # a real fill then would be at a different
                               # price than the shadow booked. Skip them.


def _load():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:
            pass
    return {"off": SHADOW_LOG.stat().st_size if SHADOW_LOG.exists() else 0,
            "open_mints": [], "day": "", "day_pnl": 0.0}


def _tail(path, off):
    size = path.stat().st_size
    if off > size:
        off = 0
    with path.open("rb") as f:
        f.seek(off)
        data = f.read()
    return data.decode("utf-8", "ignore").splitlines(), size


def run_pass():
    st = _load()
    now = time.time()
    today = time.strftime("%Y-%m-%d", time.gmtime(now))
    if st["day"] != today:
        st["day"], st["day_pnl"] = today, 0.0

    out = []
    if SHADOW_LOG.exists():
        lines, st["off"] = _tail(SHADOW_LOG, st["off"])
        for ln in lines:
            try:
                d = json.loads(ln)
            except Exception:
                continue
            act = d.get("action")
            if act == "h16e2_open":
                mint = d["mint"]
                open_age = now - (d.get("t") or now)
                blocked = None
                if open_age > STALE_OPEN_S:
                    blocked = "stale_open"
                elif len(st["open_mints"]) >= MAX_CONCURRENT:
                    blocked = "max_concurrent"
                elif st["day_pnl"] <= -DAILY_LOSS_CAP_SOL:
                    blocked = "daily_loss_cap"
                # §442: seed floor 4.0 SOL. Shadow (n=21) + live (n=4) both
                # split clean on seed: 2-4 SOL avg mult 0.958 (all 3 live
                # losers were seed<3), 4-7 -> 1.089, 7-10 -> 1.109. Bigger
                # seed = deeper curve + deployer commitment. Shadow recorder
                # still tracks the full 2-10 band so the sample keeps
                # building; only the LIVE fire is gated.
                elif (d.get("seed") or 0) < SEED_FLOOR_SOL:
                    blocked = "seed_floor"
                # §450: farm seed fingerprints (creator-rotation-proof)
                elif any(abs((d.get("seed") or 0) - s) < SEED_DENY_TOL
                         for s in SEED_DENY):
                    blocked = "seed_fingerprint"
                rec = {"t": now, "mint": mint, "mom": d.get("mom"),
                       "dd": d.get("dd"), "bf": d.get("bf"),
                       "entry_mcap": d.get("entry_mcap"), "seed": d.get("seed"),
                       "open_age_s": round(open_age, 1)}
                if blocked == "stale_open":
                    rec["action"] = "bridge_skip_stale"
                elif blocked:
                    rec["action"] = "bridge_blocked"
                    rec["reason"] = blocked
                elif not LIVE_E2_ENABLED:
                    rec["action"] = "bridge_would_buy"
                    rec["size_sol"] = SIZE_SOL
                else:
                    rec["action"] = "bridge_buy"
                    rec["size_sol"] = SIZE_SOL
                    try:
                        import importlib.util as ilu
                        spec = ilu.spec_from_file_location(
                            "live_trader", MON / "live_trader.py")
                        lt = ilu.module_from_spec(spec)
                        spec.loader.exec_module(lt)
                        # §444: serial-deployer gate. Seed-farm creators run
                        # identical seeds through every gate and dump on the
                        # momentum buyers. Any creator already seen on a
                        # qualifier in the last 6h is blocked (first coin
                        # allowed, repeats refused), and the creator-level
                        # denylist is enforced in curve_buy itself.
                        creator = None
                        try:
                            creator = lt.curve_creator(mint)
                        except Exception:
                            pass
                        hist = st.setdefault("creator_hist", [])
                        hist[:] = [h for h in hist
                                   if now - h[0] < 6 * 3600][-200:]
                        prior = sum(1 for h in hist if h[1] == creator)
                        if creator and prior >= 1:
                            rec["action"] = "bridge_blocked"
                            rec["reason"] = "serial_deployer"
                            rec["creator"] = creator[:12]
                            out.append(rec)
                            continue
                        if creator:
                            hist.append([now, creator])
                        sig = lt.curve_buy(mint, SIZE_SOL, reason="e2_trial")
                        rec["sig"] = sig
                        # §440: only register a position on a REAL fill —
                        # sig=None means the slippage guard rejected the
                        # preflight (error 6062 on F2VJAXjj); opening anyway
                        # created a phantom position the exit stack would
                        # try to sell. No sig -> no position -> no slot held.
                        if isinstance(sig, dict) and sig.get("sig"):
                            lt.open_position(mint, SIZE_SOL, "e2_trial")
                            st["open_mints"].append(mint)
                        else:
                            rec["action"] = "bridge_buy_refused"
                            rec["refused"] = (sig or {}).get("result", "?")[:160]
                    except Exception as e:
                        rec["action"] = "bridge_error"
                        rec["err"] = str(e)[:200]
                out.append(rec)
            elif act == "h16e2_close":
                mint = d["mint"]
                if mint in st["open_mints"]:
                    st["open_mints"].remove(mint)
                out.append({"t": now, "mint": mint, "action": "bridge_note_close",
                            "outcome": d.get("outcome"), "mult": d.get("mult")})

    if out:
        with LOG.open("a") as f:
            for r in out:
                f.write(json.dumps(r) + "\n")
    STATE.write_text(json.dumps(st))
    return {"events": len(out), "open": len(st["open_mints"])}


if __name__ == "__main__":
    print(run_pass())
