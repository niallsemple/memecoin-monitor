#!/usr/bin/env python3
"""Paper trader: simulates the kill-zone rule on the live monitor state.

Bank: GBP 1000. Position size: 2% of CURRENT bank per trade.
Entry: Solana token, verdict PASS (post-backfill), first history point >= +38 min,
       value >= 80% of detection value, liquidity at entry >= $20k (exit feasibility).
Exit: ladder 25% at 2x / 5x / 10x of entry; remaining trails: sell all if price
      falls >50% from position peak; open positions marked at last price.
Costs: 1.5% per side (terminal fee + slippage on thin pairs).
State: paper.json. Log: trades.md.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
BANK0 = 1000.0
POS_PCT = 0.02
FEE = 0.015
MIN_AGE = 38.0
FLOOR = 0.80
MIN_LIQ = 20000

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
    paper = load("paper.json", {
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
        if len(h) < 5:
            continue
        p0 = fnum(h[0].get("mcap"))
        if not p0 or p0 <= 0:
            continue
        t0 = datetime.fromisoformat(h[0]["t"])
        if t0 < started:
            paper.setdefault("seen_done", {})[key] = "pre_window"
            continue  # only tokens detected after the paper run started
        age = (now - t0).total_seconds() / 60
        if age < MIN_AGE:
            continue  # too young, check again next cycle
        cur = fnum(h[-1].get("mcap"))
        if not cur:
            continue
        if cur < FLOOR * p0:
            paper.setdefault("seen_done", {})[key] = "failed_floor"
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

    # manage open positions
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
        # trailing stop on remainder
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

    # mark-to-market
    mtm = 0.0
    for key, pos in paper["positions"].items():
        v = mon["seen"].get(key)
        h = (v or {}).get("history") or []
        cur = fnum(h[-1].get("mcap")) if h else pos["entry_mcap"]
        mtm += pos["size_gbp"] * pos["remaining"] * (cur / pos["entry_mcap"])
    total = paper["cash"] + mtm
    n_closed = len(paper["closed"])
    realized_pnl = sum(c["pnl_gbp"] for c in paper["closed"])
    print(f"bank=£{total:,.2f} (cash £{paper['cash']:,.2f} + open £{mtm:,.2f}) | "
          f"ROI={(total/BANK0-1)*100:+.2f}% | open={len(paper['positions'])} closed={n_closed} "
          f"realizedPnL=£{realized_pnl:+,.2f}")
    if log:
        tf = ROOT / "trades.md"
        if not tf.exists():
            tf.write_text("# Paper Trade Log (£1000 bank, 2% sizing)\n\n| time(UTC) | action | token | amount | detail | note |\n|---|---|---|---|---|---|\n")
        with tf.open("a") as f:
            f.write("\n".join(log) + "\n")
    save("paper.json", paper)

if __name__ == "__main__":
    main()
