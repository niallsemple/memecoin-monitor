#!/usr/bin/env python3
"""pool_discovery.py — find other deep/high-yield DLMM pools worth tracking.

Pulls Meteora's public pool API sorted by 24h fees and by fee/TVL ratio,
filters to healthy pools (TVL floor, not blacklisted, fee/TVL above bar),
and merges new addresses into capacity_pools.json so bin_collector and
capacity_watch start tracking them next poll cycle.

Run manually or weekly; discovery pools get tag "discovered".
"""
import json, os, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
POOLS = os.path.join(BASE, "capacity_pools.json")
API = "https://dlmm.datapi.meteora.ag/pools?limit=100&sort_key={key}&order_by=desc"
TVL_FLOOR = 100_000        # USD
FEE_TVL_BAR = 0.5          # 24h fees >= 50% of TVL => exceptional yield
FEES24H_BAR = 5_000        # or absolute 24h fees >= $5k
MAX_TRACKED = 12           # keep snapshot load bounded

def fetch(key):
    req = urllib.request.Request(API.format(key=key),
                                 headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)["data"]

def bin_step(p):
    cfg = p.get("pool_config") or {}
    return cfg.get("bin_step") or cfg.get("binStep")

def main():
    seen, cands = set(), {}
    for key in ("fees24h", "fee_tvl_ratio"):
        try:
            for p in fetch(key):
                a = p["address"]
                if a in seen or p.get("is_blacklisted"):
                    continue
                seen.add(a)
                tvl = p.get("tvl") or 0
                f24 = (p.get("fees") or {}).get("24h", 0)
                ftr = (p.get("fee_tvl_ratio") or {}).get("24h", 0)
                if tvl >= TVL_FLOOR and (ftr >= FEE_TVL_BAR or f24 >= FEES24H_BAR):
                    cands[a] = p
        except Exception as e:
            print(f"fetch {key} failed: {e}")
    cfg = json.load(open(POOLS))
    have = {p["addr"] for p in cfg["pools"]}
    ranked = sorted(cands.values(),
                    key=lambda p: (p.get("fee_tvl_ratio") or {}).get("24h", 0),
                    reverse=True)
    added = 0
    print(f"{'pool':<28} {'TVL$':>12} {'fees24h$':>10} {'fee/tvl':>8}  status")
    for p in ranked[:30]:
        a = p["address"]
        tvl, f24 = p["tvl"], p["fees"]["24h"]
        ftr = p["fee_tvl_ratio"]["24h"]
        if a in have:
            status = "tracked"
        elif len(cfg["pools"]) < MAX_TRACKED:
            tx, ty = p.get("token_x") or {}, p.get("token_y") or {}
            cfg["pools"].append({
                "addr": a, "name": p["name"], "tvl_usd": round(tvl),
                "bin_step": bin_step(p),
                "fee_pct": round(f24 / (p["volume"]["24h"] or 1) * 100, 4),
                "x_sym": tx.get("symbol"), "y_sym": ty.get("symbol"),
                "x_dec": tx.get("decimals", 9), "y_dec": ty.get("decimals", 9),
                "tag": "discovered"})
            have.add(a)
            added += 1
            status = "ADDED"
        else:
            status = "skipped(full)"
        print(f"{p['name']:<28} {tvl:>12,.0f} {f24:>10,.0f} {ftr:>8.2f}  {status}")
    json.dump(cfg, open(POOLS, "w"), indent=2)
    print(f"\n{added} pools added; {len(cfg['pools'])} total tracked")

if __name__ == "__main__":
    main()
