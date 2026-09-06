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

LIVE_E2_ENABLED = False        # THE GATE. Flip only on owner sign-off.
SIZE_SOL = 0.02                # micro-size trial entries
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
                        sig = lt.curve_buy(mint, SIZE_SOL, reason="e2_trial")
                        lt.open_position(mint, SIZE_SOL, "e2_trial")
                        rec["sig"] = sig
                        st["open_mints"].append(mint)
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
