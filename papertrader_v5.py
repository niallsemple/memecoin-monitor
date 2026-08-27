#!/usr/bin/env python3
"""Paper trader v5: BEHAVIOURAL GATE (from countermeasures research, REPORT.md §12).

v5 = v4 (1.5x momentum floor crossing @5-30min, 100% TP @2x, 60% trail, 2h
time stop) PLUS the stage-3 behavioural audit as an entry gate:
tokens whose wallet-layer check says RISK (proxy mode: RugCheck danger risks;
helius mode: fresh-wallet supply >25%, deployer <24h old, top20 >80%) are
refused. v4 is the live control — same flow, no behavioural gate.

Bank: GBP 1000 (fresh book). Position size: 2% of CURRENT cash per trade.
State: paper_v5.json. Log: trades_v5.md.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
BANK0 = 1000.0
POS_PCT = 0.02
FEE = 0.015
MIN_AGE = 5.0      # earliest entry
MAX_AGE = 30.0     # latest entry (early-momentum semantics)
FLOOR = 1.5        # momentum floor: current mcap >= 150% of detect mcap
MIN_LIQ = 20000
MIN_HIST = 3
TP_MULT = 2.0      # take profit: sell 100% at 2x
TRAIL = 0.6        # trailing stop: 60% of position peak
TIME_STOP_MIN = 120.0
TIME_STOP_R = 1.5  # exit if older than TIME_STOP_MIN and below this multiple

def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

def load(p, default):
    f = ROOT / p
    return json.loads(f.read_text()) if f.exists() else default

def save(p, obj):
    (ROOT / p).write_text(json.dumps(obj, indent=1))

def main():
    mon = load("state.json", {"seen": {}})
    paper = load("paper_v5.json", {
        "bank_start": BANK0, "cash": BANK0, "positions": {}, "closed": [],
        "started": datetime.now(timezone.utc).isoformat(),
    })
    now = datetime.now(timezone.utc)
    log = []

    started = datetime.fromisoformat(paper["started"])
    for key, v in mon["seen"].items():
        if v.get("chain") != "solana" or v.get("verdict") != "PASS":
            continue
        # stage-3 behavioural gate: refuse RISK; SKIP (no data yet) waits
        beh = v.get("behaviour") or {}
        if beh.get("verdict") == "RISK":
            paper.setdefault("seen_done", {})[key] = "behaviour_risk"
            continue
        if beh.get("verdict") != "PASS":
            continue
        if key in paper["positions"] or key in paper.get("seen_done", {}):
            continue
        h = v.get("history") or []
        if len(h) < MIN_HIST:
            continue
        p0 = fnum(h[0].get("mcap"))
        if not p0 or p0 <= 0:
            continue
        t0 = datetime.fromisoformat(h[0]["t"])
        if t0 < started:
            paper.setdefault("seen_done", {})[key] = "pre_window"
            continue
        age = (now - t0).total_seconds() / 60
        if age < MIN_AGE:
            continue
        cur = fnum(h[-1].get("mcap"))
        if not cur:
            continue
        if cur >= FLOOR * p0:
            pass  # momentum confirmed -> proceed to liquidity check
        elif age > MAX_AGE:
            paper.setdefault("seen_done", {})[key] = "failed_momentum_floor"
            continue
        else:
            continue  # inside evaluation window, re-check next run
        liq = (v.get("detect") or {}).get("liq_usd") or 0
        if liq < MIN_LIQ:
            paper.setdefault("seen_done", {})[key] = "thin_liquidity"
            continue
        size = min(paper["cash"] * POS_PCT, paper["cash"])
        if size < 1:
            continue
        cost = size * (1 + FEE)
        paper["cash"] -= cost
        paper["positions"][key] = {
            "addr": v["addr"][:8], "entry_mcap": cur, "entry_min": round(age, 1),
            "size_gbp": round(size, 2), "peak_mcap": cur,
            "remaining": 1.0, "realized": 0.0, "opened": now.isoformat(),
        }
        log.append(f"| {now.strftime('%H:%M')} | BUY | {v['addr'][:8]} | £{size:.2f} | entry mc ${cur:,.0f} | +{age:.0f}min @ {cur/p0:.2f}x detect |")

    for key, pos in list(paper["positions"].items()):
        v = mon["seen"].get(key)
        if not v:
            continue
        h = v.get("history") or []
        cur = fnum(h[-1].get("mcap")) if h else None
        if not cur:
            continue
        pos["peak_mcap"] = max(pos["peak_mcap"], cur)
        entry_mc, size = pos["entry_mcap"], pos["size_gbp"]
        r = cur / entry_mc
        opened_min = (now - datetime.fromisoformat(pos["opened"])).total_seconds() / 60
        if r >= TP_MULT:
            proceeds = size * pos["remaining"] * TP_MULT * (1 - FEE)
            paper["cash"] += proceeds
            pos["realized"] += proceeds
            pos["remaining"] = 0
            log.append(f"| {now.strftime('%H:%M')} | SELL 2x | {pos['addr']} | £{proceeds:.2f} | take-profit 100% @2x |")
        elif cur < TRAIL * pos["peak_mcap"]:
            proceeds = size * pos["remaining"] * r * (1 - FEE)
            paper["cash"] += proceeds
            pos["realized"] += proceeds
            pos["remaining"] = 0
            log.append(f"| {now.strftime('%H:%M')} | STOP | {pos['addr']} | £{proceeds:.2f} | trail-stop at {r:.2f}x |")
        elif opened_min > TIME_STOP_MIN and r < TIME_STOP_R:
            proceeds = size * pos["remaining"] * r * (1 - FEE)
            paper["cash"] += proceeds
            pos["realized"] += proceeds
            pos["remaining"] = 0
            log.append(f"| {now.strftime('%H:%M')} | TIME | {pos['addr']} | £{proceeds:.2f} | time-stop at {r:.2f}x after {opened_min:.0f}min |")
        if pos["remaining"] <= 0.001:
            pnl = pos["realized"] - pos["size_gbp"] * (1 + FEE)
            paper["closed"].append({**pos, "closed_at": now.isoformat(),
                                    "exit_r": round(r, 3), "pnl_gbp": round(pnl, 2)})
            del paper["positions"][key]

    mtm = 0.0
    for key, pos in paper["positions"].items():
        v = mon["seen"].get(key)
        h = (v or {}).get("history") or []
        cur = fnum(h[-1].get("mcap")) if h else pos["entry_mcap"]
        mtm += pos["size_gbp"] * pos["remaining"] * (cur / pos["entry_mcap"])
    total = paper["cash"] + mtm
    n_closed = len(paper["closed"])
    realized_pnl = sum(c["pnl_gbp"] for c in paper["closed"])
    print(f"[v5 BEHAV] bank=£{total:,.2f} (cash £{paper['cash']:,.2f} + open £{mtm:,.2f}) | "
          f"ROI={(total/BANK0-1)*100:+.2f}% | open={len(paper['positions'])} closed={n_closed} "
          f"realizedPnL=£{realized_pnl:+,.2f}")
    if log:
        tf = ROOT / "trades_v5.md"
        if not tf.exists():
            tf.write_text("# Paper Trade Log v5 — BEHAVIOURAL GATE (v4 rules + wallet-layer audit) (£1000 bank, 2% sizing)\n\n| time(UTC) | action | token | amount | detail | note |\n|---|---|---|---|---|---|\n")
        with tf.open("a") as f:
            f.write("\n".join(log) + "\n")
    save("paper_v5.json", paper)

if __name__ == "__main__":
    main()
