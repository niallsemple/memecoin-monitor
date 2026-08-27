#!/usr/bin/env python3
"""Paper trader v2: EARLY MOMENTUM rule (from 2026-08-26 entry-timing analysis).

Finding: on the filtered cohort (audit PASS + liq >= $20k), the 38-min kill-zone
wait added no protection — median outcome was identical at +5..+38 min — while
early momentum (mcap at +5min / detect mcap) separated winners (1.35) from
losers (0.59). So: audit instantly, enter at +5 min if momentum floor holds.

Bank: GBP 1000 (fresh book). Position size: 2% of CURRENT cash per trade.
Entry: Solana, verdict PASS, detected after window start, age >= +5 min,
       current mcap >= 100% of detection mcap (momentum floor), detect liq >= $20k.
Exit:  ladder 25% at 2x / 5x / 10x of entry; remaining trails: sell all if price
       falls >50% from position peak; open positions marked at last price.
Costs: 1.5% per side.
State: paper_v2.json. Log: trades_v2.md.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
BANK0 = 1000.0
POS_PCT = 0.02
FEE = 0.015
MIN_AGE = 5.0      # NEW: enter at +5 min instead of +38
FLOOR = 1.00       # NEW: momentum gate — current mcap >= 100% of detect mcap
MIN_LIQ = 20000
MIN_HIST = 3       # at ~2.2min gaps, +5min yields ~3 points

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
    paper = load("paper_v2.json", {
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
        if cur < FLOOR * p0:
            paper.setdefault("seen_done", {})[key] = "failed_momentum_floor"
            continue
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
            "size_gbp": round(size, 2), "peak_mcap": cur, "stage": 0,
            "remaining": 1.0, "realized": 0.0, "opened": now.isoformat(),
        }
        log.append(f"| {now.strftime('%H:%M')} | BUY | {v['addr'][:8]} | £{size:.2f} | entry mc ${cur:,.0f} | +{age:.0f}min |")

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
        for stage, mult in ((0, 2), (1, 5), (2, 10)):
            if pos["stage"] == stage and r >= mult:
                proceeds = size * 0.25 * mult * (1 - FEE)
                paper["cash"] += proceeds
                pos["realized"] += proceeds
                pos["remaining"] -= 0.25
                pos["stage"] += 1
                log.append(f"| {now.strftime('%H:%M')} | SELL {mult}x | {pos['addr']} | £{proceeds:.2f} | ladder stage {stage+1} |")
        if pos["remaining"] > 0 and cur < 0.5 * pos["peak_mcap"]:
            proceeds = size * pos["remaining"] * r * (1 - FEE)
            paper["cash"] += proceeds
            pos["realized"] += proceeds
            pos["remaining"] = 0
            log.append(f"| {now.strftime('%H:%M')} | STOP | {pos['addr']} | £{proceeds:.2f} | trail-stop at {r:.2f}x |")
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
    print(f"[v2 EARLY] bank=£{total:,.2f} (cash £{paper['cash']:,.2f} + open £{mtm:,.2f}) | "
          f"ROI={(total/BANK0-1)*100:+.2f}% | open={len(paper['positions'])} closed={n_closed} "
          f"realizedPnL=£{realized_pnl:+,.2f}")
    if log:
        tf = ROOT / "trades_v2.md"
        if not tf.exists():
            tf.write_text("# Paper Trade Log v2 — EARLY MOMENTUM (+5min, slope>=1.0) (£1000 bank, 2% sizing)\n\n| time(UTC) | action | token | amount | detail | note |\n|---|---|---|---|---|---|\n")
        with tf.open("a") as f:
            f.write("\n".join(log) + "\n")
    save("paper_v2.json", paper)

if __name__ == "__main__":
    main()
