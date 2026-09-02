#!/usr/bin/env python3
"""overhang_obs.py — §211: forward observational sampling of the
insider-overhang screen on mints we do NOT enter live.

Purpose: the overhang screen's evidence base is two historical drains
(retrospective). Before the 40-close verdict makes it BLOCKING, we need
its forward false-positive rate on live tape. This sampler screens
recent paper-book mints (signals we didn't trade live) and logs
overhang vs the paper outcome as it lands.

Source:  mfg_paper_trades_s60nm5fr.jsonl (the live gate's paper twin)
         + mfg_paper_trades.jsonl (broad book) for coverage.
Log:     overhang_obs.jsonl {mint, screen_t, age_min, overhang_pct,
         insider_n, feeders, paper_status, paper_ret, paper_peak}
State:   overhang_obs_state.json {mint: screen_t} — screened once,
         ~2-6 min after paper entry (close to live entry timing).

Usage: python3 overhang_obs.py [max_screens_per_run]
"""
import json, sys, time
from pathlib import Path

MON = Path(__file__).resolve().parent
LOG = MON / "overhang_obs.jsonl"
STATE = MON / "overhang_obs_state.json"
SOURCES = ["mfg_paper_trades_s60nm5fr.jsonl", "mfg_paper_trades.jsonl"]
MAX_AGE_MIN = 25           # tracker cadence ~20min: screen fresh mints
                           # only — overhang decays as insiders sell,
                           # stale reads bias LOW vs entry-time truth
SCREEN_AFTER_S = 120       # ~2min after entry ≈ live entry timing


def main():
    max_n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    seen = set(state)
    # newest-first candidates
    cands = {}
    for src in SOURCES:
        p = MON / src
        if not p.exists():
            continue
        for line in p.open():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            m = r.get("mint")
            if m:
                cands[m] = r          # last row wins (latest state)
    now = time.time()
    todo = []
    for m, r in sorted(cands.items(),
                       key=lambda kv: -kv[1].get("entry_t", 0)):
        if m in seen:
            continue
        age = now - r.get("entry_t", 0)
        if age < SCREEN_AFTER_S or age > MAX_AGE_MIN * 60:
            continue
        todo.append((m, r))
        if len(todo) >= max_n:
            break
    done = 0
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "lt", str(MON / "live_trader.py"))
    lt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lt)
    import insider_screen, wallet_ledger
    for m, r in todo:
        row = {"mint": m, "screen_t": now,
               "age_min": round((now - r.get("entry_t", 0)) / 60, 1),
               "paper_status": r.get("status"), "paper_ret": r.get("ret"),
               "paper_peak": r.get("peak"),
               "paper_exit": r.get("exit_reason")}
        try:
            pool = insider_screen.POOLS.get(m) or lt._discover_pool(m)
            if not pool:
                row["error"] = "no pool"
            else:
                wallet_ledger.update(m, pool)
                insider_screen.POOLS.setdefault(m, pool)
                s = insider_screen.screen(m)
                row["overhang_pct"] = s.get("overhang_pct")
                row["insider_n"] = len(s.get("insiders", []))
                f_n, _ = lt._feeder_count(m)
                row["feeders"] = f_n
        except Exception as e:
            row["error"] = str(e)[:120]
        with LOG.open("a") as f:
            f.write(json.dumps(row) + "\n")
        state[m] = now
        done += 1
    STATE.write_text(json.dumps(state))
    print(json.dumps({"screened": done, "candidates": len(todo),
                      "total_seen": len(state)}))


if __name__ == "__main__":
    main()
