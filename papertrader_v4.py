#!/usr/bin/env python3
"""Paper trader v4: MOMENTUM-1.5 (from research deep-dive 2026-08-27, REPORT.md §11).

Data basis (566 audited tokens, 54 PASS): r5 >= 1.5x bucket -> 88% reached 2x,
0% fast-rug, median peak 3.94x. Floors of 1.0/1.25 lose in simulation;
>=1.5 is the only profitable entry cohort. Exit sweep: selling 100% at 2x beat
all ladders (+3.2% vs +0.9%); trailing stop 0.6 of peak beat 0.5 (+4.1% best).

Bank: GBP 1000 (fresh book). Position size: 2% of CURRENT cash per trade.
Entry: Solana, verdict PASS, detected after window start, detect liq >= $20k,
       first crossing of 1.5x detection mcap while age is 5-30 min
       (approximates the r5>=1.5 else r15>=1.5 two-checkpoint rule).
Exit:  sell 100% at 2x of entry; trailing stop at 60% of position peak;
       time stop: exit if open > 120 min and below 1.5x entry.
Costs: 1.5% per side.
State: paper_v4.json. Log: trades_v4.md.
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
    paper = load("paper_v4.json", {
        "bank_start": BANK0, "cash": BANK0, "positions": {}, "closed": [],
        "started": datetime.now(timezone.utc).isoformat(),
    })
    now = datetime.now(timezone.utc)
    log = []

    started = datetime.fromisoformat(paper["started"])
    for key, v in mon["seen"].items():
        if v.get("chain") != "solana" or v.get("verdict") != "PASS":
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
    print(f"[v4 MOM1.5] bank=£{total:,.2f} (cash £{paper['cash']:,.2f} + open £{mtm:,.2f}) | "
          f"ROI={(total/BANK0-1)*100:+.2f}% | open={len(paper['positions'])} closed={n_closed} "
          f"realizedPnL=£{realized_pnl:+,.2f}")
    if log:
        tf = ROOT / "trades_v4.md"
        if not tf.exists():
            tf.write_text("# Paper Trade Log v4 — MOMENTUM-1.5 (1.5x floor @5-30min, 100% TP @2x, 60% trail) (£1000 bank, 2% sizing)\n\n| time(UTC) | action | token | amount | detail | note |\n|---|---|---|---|---|---|\n")
        with tf.open("a") as f:
            f.write("\n".join(log) + "\n")
    save("paper_v4.json", paper)

if __name__ == "__main__":
    main()
