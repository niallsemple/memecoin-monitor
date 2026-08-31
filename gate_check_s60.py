#!/usr/bin/env python3
"""Post-amendment go-live gate for the s60 manufactured-launch strategy.

Measurable gates are computed from mfg_paper_trades_s60.jsonl, counting only
entries at/after the amendment timestamp in amendment.json (the re-zero).
Manual gates are read from manual_signoff.json — created ONLY by the owner.

Usage: python3 gate_check_s60.py            # recompute + write gate_status_s60.json
       python3 gate_check_s60.py --quiet    # print one-line summary
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

MIN_COMMITTED = 30          # fresh committed closes required post-amendment
MIN_EXP = 0.0               # expectancy must be strictly positive
MAX_BLEEDERS = 1            # >=2 full-loss (<=-50%) trades in window kills
FLOOR = 0.125               # freerolled-open positions count at +12.5% floor


def load(name, default=None):
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        return default
    with open(p) as f:
        return json.load(f)


def main():
    amend = load("amendment.json", {}) or {}
    amend_ts = amend.get("amendment_ts")          # None until Sep 1 review sets it
    signoff = load("manual_signoff.json", {}) or {}

    rows = []
    p = os.path.join(HERE, amend.get("scorer_file",
                                     "mfg_paper_trades_s60.jsonl"))
    if amend_ts and os.path.exists(p):
        with open(p) as f:
            for line in f:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("entry_t", 0) >= amend_ts:
                    rows.append(r)

    committed = []
    for r in rows:
        if r.get("status") == "closed":
            committed.append(r.get("ret", 0.0))
        elif r.get("status") == "open" and r.get("freerolled"):
            committed.append(FLOOR)
    n = len(committed)
    exp = sum(committed) / n if n else None
    bleeders = sum(1 for v in committed if v <= -0.50)

    measurable = {
        "n_committed": n,
        "expectancy": round(exp, 4) if exp is not None else None,
        "bleeders": bleeders,
        "sample_ok": n >= MIN_COMMITTED,
        "exp_ok": exp is not None and exp > MIN_EXP,
        "bleeders_ok": bleeders <= MAX_BLEEDERS,
    }
    measurable_ok = all([measurable["sample_ok"], measurable["exp_ok"],
                         measurable["bleeders_ok"]])
    qualified = bool(amend_ts) and measurable_ok and bool(
        signoff.get("owner_approved"))

    status = {
        "computed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "amendment_ts": amend_ts,
        "strategy": "s60 breadth-entry + h108 exits (mfg universe)",
        "measurable": measurable,
        "measurable_ok": measurable_ok,
        "manual_signoff": bool(signoff.get("owner_approved")),
        "qualified": qualified,
    }
    with open(os.path.join(HERE, "gate_status_s60.json"), "w") as f:
        json.dump(status, f, indent=2)
    if "--quiet" in sys.argv:
        print(f"s60 gate: n={n} exp={measurable['expectancy']} "
              f"bleeders={bleeders} qualified={qualified}")
    else:
        print(json.dumps(status, indent=2))
    return 0 if qualified else 1


if __name__ == "__main__":
    sys.exit(main())
