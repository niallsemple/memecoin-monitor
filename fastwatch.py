#!/usr/bin/env python3
"""Fast watcher — attacks the reconstruction wedge (REPORT.md §22).

The 10-min automation cadence means live entries/exits fill up to 10 min
after the triggering print; reconstruction fills AT the print. That wedge
cost v4 ~75pp of ROI vs its own backtest. This script refreshes prices for
the HOT SET only — open paper positions (v2-v6) + cluster-tagged tokens in
their entry window + audit-PASS tokens in the 5-30 min evaluation window —
and appends fresh history points, so paper traders evaluate on ~1-min data.

Called in a loop by memecoin_loop.py between full monitor cycles.
"""
import json, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
STATE = ROOT / "state.json"
DEX_TOKENS = "https://api.dexscreener.com/latest/dex/tokens/{}"
UA = {"User-Agent": "memecoin-monitor/1.0 (research)"}
BOOKS = ["paper_v2.json", "paper_v3.json", "paper_v4.json", "paper_v5.json", "paper_v6.json"]


def get(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return {}


def hot_set(state, now):
    hot = set()
    for b in BOOKS:
        f = ROOT / b
        if f.exists():
            try:
                hot |= set(json.loads(f.read_text()).get("positions", {}))
            except Exception:
                pass
    for key, v in state["seen"].items():
        if v.get("chain") != "solana" or not v.get("history"):
            continue
        try:
            age_min = (now - datetime.fromisoformat(v["history"][0]["t"])).total_seconds() / 60
        except Exception:
            continue
        cl = v.get("cluster") or {}
        if cl.get("hit") and age_min < 120:
            hot.add(key)  # cluster token in/around entry window
        elif v.get("verdict") == "PASS" and 3 <= age_min <= 60:
            hot.add(key)  # momentum evaluation window
    return hot


def main():
    state = json.loads(STATE.read_text())
    now = datetime.now(timezone.utc)
    hot = hot_set(state, now)
    if not hot:
        print("fastwatch: hot set empty")
        return
    addr_to_key = {state["seen"][k]["addr"]: k for k in hot if state["seen"][k].get("addr")}
    addrs = list(addr_to_key)
    updated = 0
    for i in range(0, len(addrs), 30):
        d = get(DEX_TOKENS.format(",".join(addrs[i:i+30])))
        time.sleep(1.0)
        pairs = {}
        for p in (d.get("pairs") or []):
            ta = (p.get("baseToken") or {}).get("address")
            cur = pairs.get(ta)
            if not cur or ((p.get("liquidity") or {}).get("usd") or 0) > ((cur.get("liquidity") or {}).get("usd") or 0):
                pairs[ta] = p
        for ta, p in pairs.items():
            k = addr_to_key.get(ta)
            if k:
                state["seen"][k].setdefault("history", []).append({
                    "t": now.isoformat(), "price": p.get("priceUsd"),
                    "mcap": p.get("marketCap") or p.get("fdv")})
                updated += 1
    STATE.write_text(json.dumps(state, indent=1))
    print(f"fastwatch: {updated}/{len(addrs)} hot tokens refreshed")


if __name__ == "__main__":
    main()
