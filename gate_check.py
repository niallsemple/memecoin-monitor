#!/usr/bin/env python3
"""Score v3 STRICT and v6 CLUSTER against memecoin-monitor/go-live-gates.md.

Measurable gates are computed from paper_v*.json / mfg_report.json.
Manual gates (exit-rule code upgrade, slippage proof, ops config) are read
from manual_signoff.json — v3 is only fully "qualified" when both pass.

Usage: python3 gate_check.py            # recompute + write gate_status.json
       python3 gate_check.py --quiet    # print one-line summary only
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))

BANK_START = 1000.0
MAX_ENTRY_AGE_MIN = 360  # 6h — re-entries older than this violate the entry window rule


def load(name, default=None):
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        return default
    with open(p) as f:
        return json.load(f)


def iso(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def score_v3():
    book = load("paper_v3.json", {})
    closed = book.get("closed") or []
    open_pos = book.get("positions") or {}
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    n_closed = len(closed)
    pnl_7d = sum(t.get("pnl_gbp", 0.0) for t in closed
                 if t.get("closed_at") and iso(t["closed_at"]) >= week_ago)
    gains = sum(t.get("pnl_gbp", 0.0) for t in closed if t.get("pnl_gbp", 0.0) > 0)
    losses = abs(sum(t.get("pnl_gbp", 0.0) for t in closed if t.get("pnl_gbp", 0.0) < 0))
    profit_factor = round(gains / losses, 2) if losses > 0 else (None if gains == 0 else 99.0)
    # conservative drawdown: cash-only (open positions assumed worthless)
    cash = book.get("cash", BANK_START)
    drawdown_pct = round((BANK_START - cash) / BANK_START * 100, 1)
    recent = closed[-50:] + list(open_pos.values())
    reentry_violations = sum(1 for t in recent if t.get("entry_min", 0) > MAX_ENTRY_AGE_MIN)

    gates = {
        "sample_size_100": {"pass": n_closed >= 100, "value": n_closed, "need": ">=100 closed"},
        "pnl_7d_nonneg": {"pass": pnl_7d >= 0, "value": round(pnl_7d, 2), "need": ">= £0 trailing 7d"},
        "drawdown_le_10pct": {"pass": drawdown_pct <= 10.0, "value": drawdown_pct, "need": "<=10% cash drawdown"},
        "profit_factor_1_3": {"pass": (profit_factor or 0) >= 1.3, "value": profit_factor, "need": ">=1.3"},
        "no_late_reentries": {"pass": reentry_violations == 0, "value": reentry_violations,
                              "need": "0 entries with age>6h in last 50 trades + open"},
    }
    signoff = load("manual_signoff.json", {}) or {}
    manual = {
        "exit_rule_upgraded": bool(signoff.get("exit_rule_upgraded")),
        "slippage_proof_20": bool(signoff.get("slippage_proof_20")),
        "ops_configured": bool(signoff.get("ops_configured")),
    }
    data_pass = all(g["pass"] for g in gates.values())
    return {
        "gates": gates,
        "manual_gates": manual,
        "data_pass": data_pass,
        "qualified": data_pass and all(manual.values()),
        "open_positions": len(open_pos),
        "closed_trades": n_closed,
    }


def score_v6():
    book = load("paper_v6.json", {})
    rep = load("mfg_report.json", {}) or {}
    runners = rep.get("runners", 0)
    husks = rep.get("husks", 0)
    fired = len(book.get("closed") or []) + len(book.get("positions") or {})
    closed = book.get("closed") or []
    gains = sum(t.get("pnl_gbp", 0.0) for t in closed if t.get("pnl_gbp", 0.0) > 0)
    losses = abs(sum(t.get("pnl_gbp", 0.0) for t in closed if t.get("pnl_gbp", 0.0) < 0))
    pf = round(gains / losses, 2) if losses > 0 else None
    gates = {
        "labelled_20v20": {"pass": runners >= 20 and husks >= 20, "value": f"{runners} runners / {husks} husks",
                           "need": ">=20 each"},
        "has_fired": {"pass": fired > 0, "value": fired, "need": ">=1 paper trade"},
        "fired_30_pf_1_5": {"pass": fired >= 30 and (pf or 0) >= 1.5, "value": f"{fired} trades, PF={pf}",
                            "need": ">=30 fired, PF>=1.5"},
    }
    return {"gates": gates, "qualified": all(g["pass"] for g in gates.values())}


def main():
    status = {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "v3": score_v3(),
        "v6": score_v6(),
    }
    out = os.path.join(HERE, "gate_status.json")
    with open(out, "w") as f:
        json.dump(status, f, indent=1)
    v3, v6 = status["v3"], status["v6"]
    line = (f"v3: qualified={v3['qualified']} data_pass={v3['data_pass']} "
            f"closed={v3['closed_trades']} manual={v3['manual_gates']} | "
            f"v6: qualified={v6['qualified']}")
    print(line)
    if "--quiet" not in sys.argv:
        print(json.dumps(status, indent=1))
    return status


if __name__ == "__main__":
    main()
