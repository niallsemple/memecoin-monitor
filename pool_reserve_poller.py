#!/usr/bin/env python3
"""
pool_reserve_poller.py — on-chain liquidity drain detector for hot PumpSwap
pairs. The rug study (REPORT.md 2026-09-08) showed price feeds stay green
until the pool is empty: ONLY reserve-based exits work, and 20-min batch
cadence is blind. This polls the real chain state at <=15s cadence.

Method: getTokenLargestAccounts(mint) via Helius. For newborn memecoins the
pool vault dominates the holder list, so account #1 is the pool's token
vault. A rug pull = vault token balance collapses (deployer yanks LP / dumps
the vault). We track the vault amount against its running peak and flag
drains at >30% (RUG_LIQ_PCT parity with the trade sim) and >50% (hard).

Selection mirrors pumpswap_fastpoll: pumpswap pairs, age < MAX_AGE_H,
latest DexScreener liq >= MIN_LIQ, top MAX_PAIRS by liq.

Output: pool_reserve_snapshots.jsonl rows:
  {t, mint, name, vault, amount, peak, dd (drawdown from peak, 0..1),
   drain30, drain50}

Budget: 15 pairs x 4 polls/min = ~86k calls/day, well inside the 10M/mo
Helius allowance (~333k/day).

Usage:
  python3 pool_reserve_poller.py --once          # one poll, print, exit
  python3 pool_reserve_poller.py [--minutes 8]   # bounded run for watcher
"""
import json, os, sys, time, urllib.request, collections

MON = os.path.dirname(os.path.abspath(__file__))
PAIRS = os.path.join(MON, "pumpswap_pairs.json")
SNAP = os.path.join(MON, "pumpswap_snapshots.jsonl")
OUT = os.path.join(MON, "pool_reserve_snapshots.jsonl")
KEYF = os.path.join(MON, "helius_key.txt")

CADENCE_S = 15
MAX_AGE_H = 6.0
MIN_LIQ = 25000.0
MAX_PAIRS = 15
DRAIN30, DRAIN50 = 0.30, 0.50
RPC_TIMEOUT = 10


def rpc(key, mint):
    url = f"https://mainnet.helius-rpc.com/?api-key={key}"
    body = json.dumps({"jsonrpc": "2.0", "id": 1,
                       "method": "getTokenLargestAccounts",
                       "params": [mint]}).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=RPC_TIMEOUT) as r:
        d = json.loads(r.read())
    vals = (d.get("result") or {}).get("value") or []
    if not vals:
        return None, None
    top = vals[0]
    return top.get("address"), top.get("uiAmount")


def hot_mints(now):
    """Mint -> name for pairs worth watching, same gate as fastpoll."""
    try:
        pairs = json.load(open(PAIRS))
    except Exception:
        return {}
    latest = {}
    if os.path.exists(SNAP):
        for l in open(SNAP):
            try:
                r = json.loads(l)
            except Exception:
                continue
            if r.get("mint"):
                latest[r["mint"]] = r
    out = {}
    for mint, p in pairs.items():
        if p.get("dex") != "pumpswap":
            continue
        age_h = (now - p.get("born_t", now)) / 3600
        if age_h > MAX_AGE_H:
            continue
        s = latest.get(mint)
        if not s or (s.get("liq") or 0) < MIN_LIQ:
            continue
        out[mint] = {"name": p.get("name"), "liq": s.get("liq") or 0}
    top = sorted(out.items(), key=lambda kv: -kv[1]["liq"])[:MAX_PAIRS]
    return dict(top)


def poll_once(key, watch, peaks, vaults, fout):
    now = time.time()
    n_ok = 0
    for mint, meta in watch.items():
        try:
            vault, amt = rpc(key, mint)
        except Exception as e:
            print(f"  rpc fail {(meta['name'] or '?')[:16]}: {e}", file=sys.stderr)
            continue
        if vault is None or amt is None:
            continue
        vaults.setdefault(mint, vault)
        peak = max(peaks.get(mint, 0.0), amt)
        peaks[mint] = peak
        dd = 1 - (amt / peak) if peak > 0 else 0.0
        row = {"t": now, "mint": mint, "name": meta["name"], "vault": vault,
               "amount": amt, "peak": peak, "dd": round(dd, 4),
               "drain30": dd >= DRAIN30, "drain50": dd >= DRAIN50}
        fout.write(json.dumps(row) + "\n")
        n_ok += 1
        flag = " <== DRAIN" if row["drain30"] else ""
        print(f"  {(meta['name'] or '?')[:16]:<18} vault={amt:>18,.2f} "
              f"dd={dd * 100:5.1f}%{flag}")
    fout.flush()
    return n_ok


def main():
    once = "--once" in sys.argv
    minutes = 8
    if "--minutes" in sys.argv:
        minutes = int(sys.argv[sys.argv.index("--minutes") + 1])
    key = open(KEYF).read().strip()
    watch = hot_mints(time.time())
    print(f"watching {len(watch)} hot mints")
    if not watch:
        return
    peaks, vaults = {}, {}
    # seed peaks from today's file so dd survives restarts
    if os.path.exists(OUT):
        for l in open(OUT):
            try:
                r = json.loads(l)
            except Exception:
                continue
            if r.get("mint") in watch:
                peaks[r["mint"]] = max(peaks.get(r["mint"], 0.0),
                                       r.get("peak") or 0)
    with open(OUT, "a") as fout:
        if once:
            poll_once(key, watch, peaks, vaults, fout)
            return
        deadline = time.time() + minutes * 60
        while time.time() < deadline:
            t0 = time.time()
            poll_once(key, watch, peaks, vaults, fout)
            dt = time.time() - t0
            time.sleep(max(1, CADENCE_S - dt))


if __name__ == "__main__":
    main()
