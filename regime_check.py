#!/usr/bin/env python3
"""Regime-shift check: has a non-farm launch passed the seed gate recently?

Reads fast_entry_debug.jsonl, compares spawned vs seed_blocked mints over the
last 40 minutes. A spawned mint with NO seed_blocked event passed the birth
gate = potential real launch = regime break. Prints ONE summary line and, on a
blocked->passed transition, appends to regime_break.jsonl (dedup: max one
marker per mint, and one transition line per 12h).

Exit 0 always; output is for the watchdog automation's reply.
"""
import json, time
from pathlib import Path

MON = Path(__file__).resolve().parent
DBG = MON / "fast_entry_debug.jsonl"
MARK = MON / "regime_break.jsonl"
WINDOW_S = 40 * 60
DEDUP_S = 12 * 3600


def main():
    now = time.time()
    spawned, blocked = {}, set()
    try:
        with open(DBG) as f:
            for l in f:
                try:
                    e = json.loads(l)
                except Exception:
                    continue
                t = e.get("t", 0)
                if now - t > WINDOW_S:
                    continue
                if e.get("phase") == "spawned":
                    spawned[e.get("mint")] = t
                elif e.get("phase") == "seed_blocked":
                    blocked.add(e.get("mint"))
    except FileNotFoundError:
        print("regime: no debug log"); return

    passed = {m: t for m, t in spawned.items() if m not in blocked and m}
    n_sp, n_bl = len(spawned), len(blocked & set(spawned))

    # 24h block rate for context
    day_sp = day_bl = 0
    try:
        with open(DBG) as f:
            for l in f:
                try:
                    e = json.loads(l)
                except Exception:
                    continue
                t = e.get("t", 0)
                if now - t > 86400:
                    continue
                if e.get("phase") == "spawned":
                    day_sp += 1
                elif e.get("phase") == "seed_blocked":
                    day_bl += 1
    except FileNotFoundError:
        pass

    if not passed:
        print(f"regime: FARM 100% — {n_sp} spawned/{n_bl} blocked last 40min; "
              f"24h block rate {day_bl}/{day_sp}")
        return

    # transition dedup: skip if a marker was written in the last 12h
    last_mark = 0
    if MARK.exists():
        try:
            last_mark = max(json.loads(l).get("t", 0)
                            for l in MARK.read_text().strip().split("\n") if l.strip())
        except Exception:
            pass
    fresh = {m: t for m, t in passed.items()}
    if now - last_mark > DEDUP_S:
        with open(MARK, "a") as f:
            f.write(json.dumps({"t": now, "mints": list(fresh)[:10],
                                "note": "non-farm launch passed seed gate"}) + "\n")
        print(f"*** REGIME BREAK *** {len(fresh)} non-farm launch(es) passed the "
              f"seed gate in the last 40min: {[m[:12] for m in fresh]} "
              f"(24h block rate {day_bl}/{day_sp}) — live trading may resume")
    else:
        print(f"regime: {len(fresh)} passed gate last 40min (marker already "
              f"sent {(now-last_mark)/3600:.1f}h ago); 24h block rate {day_bl}/{day_sp}")


if __name__ == "__main__":
    main()
