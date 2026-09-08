#!/usr/bin/env python3
"""
pumpswap_fastpoll.py — fine-grained snapshots for HOT tracked pairs.

Why: the 20-min watcher cadence is fine for discovery, but mania exits
(trailing stops, dumps, rugs) resolve in MINUTES. With one snapshot per
20min the trade sim's exit prices are coarse and the dump tail is blurry.
This pass polls the hot subset (liquidity >= MIN_LIQ, age < MAX_AGE_H,
cap MAX_PAIRS by liquidity) every POLL_S seconds for DURATION_S, appending
to the same pumpswap_snapshots.jsonl the trade sim already reads — finer
batches, same schema, no sim changes needed.

Designed to run INSIDE the combined watcher turn (like bsc_watch_loop):
~8 minutes of polling per 20-min cycle gives hot pairs ~12-16 snapshots
per hour instead of 3.
"""
import json, os, time, urllib.request

MON = os.path.dirname(os.path.abspath(__file__))
PAIRS = os.path.join(MON, "pumpswap_pairs.json")
OUT = os.path.join(MON, "pumpswap_snapshots.jsonl")
UA = {"User-Agent": "darwin-labs/1.0"}
DS = "https://api.dexscreener.com/latest/dex"
MIN_LIQ = 25000.0
MAX_AGE_H = 6.0
MAX_PAIRS = 15
POLL_S = 45
DURATION_S = 480      # ~8 minutes inside the watcher turn


def get(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def snap_pair(mint, rec, now):
    d = get(f"{DS}/pairs/solana/{rec['pair']}")
    rows = (d or {}).get("pairs") or []
    p = rows[0] if rows else (d or {}).get("pair")
    if not p or not p.get("pairAddress"):
        return None
    pc = p.get("pairCreatedAt") or rec.get("pair_created")
    age_h = round((now - pc / 1000) / 3600, 3) if pc else None
    vol = p.get("volume") or {}
    tx = (p.get("txns") or {}).get("m5") or {}
    pcg = p.get("priceChange") or {}
    return {
        "t": now, "mint": mint, "name": rec.get("name"),
        "pair": p["pairAddress"], "dex": p.get("dexId"), "age_h": age_h,
        "price": float(p["priceUsd"]) if p.get("priceUsd") else None,
        "liq": (p.get("liquidity") or {}).get("usd"),
        "vol_5m": vol.get("m5"), "vol_h1": vol.get("h1"),
        "txns_m5_b": tx.get("buys"), "txns_m5_s": tx.get("sells"),
        "pc_5m": pcg.get("m5"), "pc_h1": pcg.get("h1"),
        "fdv": p.get("fdv"), "mc": p.get("marketCap"),
        "fast": 1,
    }


def main():
    now = time.time()
    if not os.path.exists(PAIRS):
        print("fastpoll: no pairs file")
        return
    pairs = json.load(open(PAIRS))

    # last-known liquidity per mint
    liq_last = {}
    if os.path.exists(OUT):
        cutoff = now - 3 * 3600
        with open(OUT) as f:
            for l in f:
                try:
                    r = json.loads(l)
                except Exception:
                    continue
                if r.get("t", 0) > cutoff:
                    liq_last[r["mint"]] = r.get("liq") or 0

    cands = []
    for mint, rec in pairs.items():
        if not rec.get("pair"):
            continue
        pc = rec.get("pair_created")
        ref_t = (pc / 1000) if pc else rec.get("born_t", now)
        if now - ref_t >= MAX_AGE_H * 3600:
            continue
        if liq_last.get(mint, 0) >= MIN_LIQ:
            cands.append((mint, rec))
    cands.sort(key=lambda mr: liq_last.get(mr[0], 0), reverse=True)
    cands = cands[:MAX_PAIRS]
    if not cands:
        print("fastpoll: no hot pairs right now")
        return

    end = time.time() + DURATION_S
    n = 0
    with open(OUT, "a") as f:
        while time.time() < end:
            loop_t = time.time()
            for mint, rec in cands:
                try:
                    row = snap_pair(mint, rec, time.time())
                    if row:
                        f.write(json.dumps(row) + "\n")
                        n += 1
                except Exception:
                    pass
            f.flush()
            dt = POLL_S - (time.time() - loop_t)
            if dt > 0:
                time.sleep(dt)
    names = ", ".join((r.get("name") or "?")[:14] for _, r in cands[:6])
    print(f"fastpoll: {n} fine snapshots across {len(cands)} hot pairs ({names})")


if __name__ == "__main__":
    main()
