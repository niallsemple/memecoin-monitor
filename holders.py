#!/usr/bin/env python3
"""Holder-overlap analyzer: find wallets that appear in multiple winning tokens.

A token 'did well' if its peak mcap reached >= +50% of detection mcap.
Fetches RugCheck full-report topHolders for qualifying tokens (rate-limited,
a few per run), then counts cross-token wallet overlap. Output: holders.json
+ printed leaderboard of wallets in >= 2 winners ('smart money' candidates).
"""
import json, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
RUGCHECK_FULL = "https://api.rugcheck.xyz/v1/tokens/{}/report"
UA = {"User-Agent": "memecoin-monitor/1.0 (research)"}
MAX_FETCH = 4

def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

def get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"_error": str(e)}

def load(p, default):
    f = ROOT / p
    return json.loads(f.read_text()) if f.exists() else default

def main():
    mon = load("state.json", {"seen": {}})
    hold = load("holders.json", {"tokens": {}, "wallets": {}})
    fetched = 0
    for key, v in mon["seen"].items():
        if v.get("chain") != "solana" or key in hold["tokens"]:
            continue
        h = v.get("history") or []
        if len(h) < 3:
            continue
        p0 = fnum(h[0].get("mcap"))
        if not p0 or p0 <= 0:
            continue
        peak = max(fnum(x.get("mcap")) or 0 for x in h)
        if peak < 1.5 * p0:
            continue  # didn't do well
        if fetched >= MAX_FETCH:
            continue
        rep = get(RUGCHECK_FULL.format(v["addr"]))
        time.sleep(2)
        if "_error" in rep or not isinstance(rep, dict):
            continue
        holders = rep.get("topHolders") or []
        wallets = []
        for hh in holders[:20]:
            if hh.get("isLocker") or hh.get("isBurned"):
                continue
            w = hh.get("address")
            if w:
                wallets.append({"w": w, "pct": round(float(hh.get("pct") or 0), 2)})
        hold["tokens"][key] = {
            "addr": v["addr"][:8], "peak_mult": round(peak / p0, 2),
            "wallets": wallets,
        }
        fetched += 1
    # rebuild wallet -> tokens index
    idx = {}
    for key, t in hold["tokens"].items():
        for e in t["wallets"]:
            idx.setdefault(e["w"], []).append({"token": t["addr"], "pct": e["pct"],
                                               "peak_mult": t["peak_mult"]})
    hold["wallets"] = idx
    (ROOT / "holders.json").write_text(json.dumps(hold, indent=1))
    multi = {w: ts for w, ts in idx.items() if len(ts) >= 2}
    print(f"winning tokens profiled: {len(hold['tokens'])}, unique wallets: {len(idx)}, "
          f"wallets in >=2 winners: {len(multi)}")
    for w, ts in sorted(multi.items(), key=lambda x: -len(x[1]))[:15]:
        desc = ", ".join(f"{t['token']}({t['pct']}%, {t['peak_mult']}x)" for t in ts)
        print(f"  {w[:12]}…  in {len(ts)} winners: {desc}")

if __name__ == "__main__":
    main()
