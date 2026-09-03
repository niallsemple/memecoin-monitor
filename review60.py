#!/usr/bin/env python3
"""review60.py — 60-close review generator (DARWIN_TRAINING_LAB charter).

Loads every close from live_positions.json, joins shadow-gate scores from
mfg_live_trades.jsonl, retro-computes bundle_share for era mints that lack it
(cached in bundle_cache.json), then prints:
  1. overall + fresh-infra era tally
  2. per-trade outcome labels (MFE = peak_mult; MAE not recorded — flagged)
  3. hypothesis ledger counterfactuals: era PnL if gates had been BLOCKING
     (a) bundle_share >= BUNDLE_GATE skip
     (b) deployer prior_rugs >= 1 skip
     (c) both
Era boundary: GBPV3tgX onward (REPORT.md §233: "Post-verdict closes so far:
GBPV ..." — the fresh-infra era start).
"""
import json, sys, time
from pathlib import Path

MON = Path(__file__).parent
sys.path.insert(0, str(MON))

ERA_START = "4hMy3vXP"   # fresh-infra era first mint (REPORT §233/§244)
BUNDLE_GATE = 40.0       # §253 proposed skip threshold (outsider_pct)
SUPPLY = 1_000_000_000

# §253 retro-computed values — seed the cache, avoid re-paying RPC cost
RETRO_SEED = {
    "GFhwZDQk": 55.2, "BESHQjLG": 53.6, "v4iV886R": 46.1, "5ogCegLu": 0.0,
    "4hMy3vXP": 14.7, "Vpp3Vuvv": 0.0, "8nk9kDEQ": 0.0, "4Pu3iy2J": 0.01,
}


def load_closes():
    d = json.load(open(MON / "live_positions.json"))
    out = []
    for m, p in d.items():
        if p.get("open"):
            continue
        reason = p.get("exit_reason") or p.get("closed_reason")
        if not reason or p.get("pnl_sol") is None:
            continue
        out.append({"mint": m, "reason": reason, "pnl": p["pnl_sol"],
                    "size": p.get("size_sol"), "peak": p.get("peak_mult"),
                    "entry_t": p.get("entry_t"), "exit_t": p.get("exit_t")})
    out.sort(key=lambda r: r.get("exit_t") or 0)
    return out


def load_buy_events():
    ev = {}
    for line in open(MON / "mfg_live_trades.jsonl"):
        if '"action": "buy"' not in line:
            continue
        b = json.loads(line)
        ev[b["mint"]] = {"deployer_score": b.get("deployer_score"),
                         "bundle_share": b.get("bundle_share"),
                         "size_sol": b.get("size_sol")}
    return ev


def birth_deployer(mint):
    """Deployer (traderPublicKey) from our own birth feed, curves.jsonl."""
    import subprocess
    r = subprocess.run(["grep", "-m", "1", mint, str(MON / "curves.jsonl")],
                       capture_output=True, text=True)
    if not r.stdout:
        return None
    try:
        rec = json.loads(r.stdout.strip().split("\n")[0])
    except Exception:
        return None
    for k in ("traderPublicKey", "creator", "deployer"):
        if rec.get(k):
            return rec[k]
    return None


def retro_bundle(mint, deployer):
    """bundle_share with backward pagination so birth txs aren't missed."""
    from deployer_score import rpc
    cache_p = MON / "bundle_cache.json"
    cache = json.load(open(cache_p)) if cache_p.exists() else {}
    if mint in cache:
        return cache[mint]
    if mint[:8] in RETRO_SEED:
        cache[mint] = {"outsider_pct": RETRO_SEED[mint[:8]], "retro_seed": True}
        json.dump(cache, open(cache_p, "w"), indent=1)
        return cache[mint]
    sigs, before = [], None
    for _ in range(10):  # up to 1000 sigs, newest-first
        params = [mint, {"limit": 100}]
        if before:
            params[1]["before"] = before
        page = rpc("getSignaturesForAddress", params) or []
        if not page:
            break
        sigs += page
        before = page[-1]["signature"]
        if len(page) < 100:
            break
    if not sigs:
        return None
    birth = min(s["blockTime"] for s in sigs if s.get("blockTime"))
    early = [s for s in sigs if s.get("blockTime")
             and s["blockTime"] - birth <= 30]
    from concurrent.futures import ThreadPoolExecutor

    def amt(b):
        ta = b["uiTokenAmount"]
        return float(ta.get("amount", "0")) / (10 ** ta.get("decimals", 6))

    def fetch(s):
        return rpc("getTransaction", [s["signature"], {
                   "encoding": "jsonParsed",
                   "maxSupportedTransactionVersion": 0}])
    with ThreadPoolExecutor(max_workers=8) as ex:
        txs = list(ex.map(fetch, early))
    acquired = {}
    for tx in txs:
        if not tx or not tx.get("meta"):
            continue
        pre = {b["owner"]: amt(b) for b in tx["meta"].get("preTokenBalances", [])
               if b.get("mint") == mint and b.get("owner")}
        post = {b["owner"]: amt(b) for b in tx["meta"].get("postTokenBalances", [])
                if b.get("mint") == mint and b.get("owner")}
        for owner, a in post.items():
            d = a - pre.get(owner, 0)
            if d > 0:
                acquired[owner] = acquired.get(owner, 0) + d
    outsider = sum(v for k, v in acquired.items() if k != deployer)
    res = {"birth": birth, "txs_in_window": len(early),
           "outsider_pct": round(100 * outsider / SUPPLY, 2),
           "n_buyers": len(acquired)}
    cache[mint] = res
    json.dump(cache, open(cache_p, "w"), indent=1)
    return res


def tally(rows, label):
    n = len(rows)
    green = [r for r in rows if r["pnl"] > 0.0005]
    rugs = [r for r in rows if r["pnl"] < -0.05]
    net = sum(r["pnl"] for r in rows)
    staked = sum(r["size"] or 0 for r in rows)
    print(f"\n== {label}: {n} closes, net {net:+.4f} SOL, "
          f"staked {staked:.3f}, ROI {100*net/staked if staked else 0:+.1f}%")
    print(f"   green {len(green)} ({100*len(green)/n:.0f}%), "
          f"rugs {len(rugs)} ({100*len(rugs)/n:.0f}%), "
          f"avg green {sum(r['pnl'] for r in green)/len(green):+.4f}" if green else "")
    return net


def main():
    closes = load_closes()
    buys = load_buy_events()
    era_i = next(i for i, r in enumerate(closes)
                 if r["mint"].startswith(ERA_START))
    era = closes[era_i:]
    print(f"total closes: {len(closes)} | era closes: {len(era)} "
          f"(from {era[0]['mint'][:8]})")

    # enrich era rows with shadow scores
    for r in era:
        b = buys.get(r["mint"], {})
        ds = b.get("deployer_score") or {}
        r["deployer"] = ds.get("deployer") or birth_deployer(r["mint"])
        r["prior"] = ds.get("prior")
        r["prior_rugs"] = ds.get("prior_rugs")
        bs = b.get("bundle_share")
        if bs is None:
            rb = retro_bundle(r["mint"], r["deployer"])
            bs = rb.get("outsider_pct") if rb else None
        elif isinstance(bs, dict):
            bs = bs.get("outsider_pct")
        r["bundle"] = bs

    print("\n== per-trade labels (era) ==")
    print(f"{'mint':10} {'reason':15} {'pnl':>9} {'MFE':>6} "
          f"{'prior_rugs':>10} {'bundle%':>8}")
    for r in era:
        print(f"{r['mint'][:8]:10} {r['reason']:15} {r['pnl']:>+9.5f} "
              f"{(r['peak'] or 0):>6.3f} {str(r['prior_rugs']):>10} "
              f"{str(r['bundle']):>8}")
    print("   (MAE not recorded in position schema — gap flagged for review)")

    tally(closes, "ALL 57+")
    tally(era, "FRESH-INFRA ERA")

    # counterfactuals
    for name, fn in [
        ("gate: bundle>=40 skip", lambda r: (r["bundle"] or 0) >= BUNDLE_GATE),
        ("gate: prior_rugs>=1 skip", lambda r: (r["prior_rugs"] or 0) >= 1),
        ("gate: both", lambda r: (r["bundle"] or 0) >= BUNDLE_GATE
         or (r["prior_rugs"] or 0) >= 1),
    ]:
        kept = [r for r in era if not fn(r)]
        blocked = [r for r in era if fn(r)]
        net = sum(r["pnl"] for r in kept)
        print(f"\n== COUNTERFACTUAL {name}: keep {len(kept)}, "
              f"block {len(blocked)} -> era net {net:+.4f} SOL")
        for r in blocked:
            print(f"   blocked {r['mint'][:8]} {r['reason']} "
                  f"{r['pnl']:+.5f} (bundle={r['bundle']}, "
                  f"prior_rugs={r['prior_rugs']})")


if __name__ == "__main__":
    main()
