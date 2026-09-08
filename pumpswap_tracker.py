#!/usr/bin/env python3
"""
pumpswap_tracker.py — resolve each detected token birth to its REAL pool
and snapshot the tradable curve.

Why (venue-truth finding 2026-09-08 10:45 UTC): met-dbc births create DAMM
v2 skeleton pools that stay ~$0 TVL forever; the liquidity and volume live
on the token's PumpSwap pair (LEGO-SOL: $1 DAMM v2 vs $94k liq / $9M vol on
PumpSwap at 40min old). The birth listeners tell us WHICH tokens exist at
age ~5min; this tracker follows the money.

Per run:
  1. Read births (damm_v2_births.jsonl + dlmm_births.jsonl, last 24h).
  2. For unseen mints: DexScreener /latest/dex/tokens/{mint}, pick the
     highest-liquidity Solana pair, store in pumpswap_pairs.json
     {mint: {pair, dex, name, born_t}}.
  3. For every tracked pair younger than TRACK_H: snapshot via
     /latest/dex/pairs/solana/{pair} -> pumpswap_snapshots.jsonl
     {t, mint, name, pair, dex, age_h, price, liq, vol_5m, vol_h1,
      txns_m5_b, txns_m5_s, pc_5m, pc_h1, fdv, mc}
     Most-liquid-first, capped per run to stay inside DexScreener limits.

Runs as a step in the Meteora birth + fee pipeline automation (~20min).
"""
import json, os, time, urllib.request

MON = os.path.dirname(os.path.abspath(__file__))
BIRTH_FILES = [os.path.join(MON, "damm_v2_births.jsonl"),
               os.path.join(MON, "dlmm_births.jsonl")]
PAIRS = os.path.join(MON, "pumpswap_pairs.json")
OUT = os.path.join(MON, "pumpswap_snapshots.jsonl")
UA = {"User-Agent": "darwin-labs/1.0"}
DS = "https://api.dexscreener.com/latest/dex"
BIRTH_WINDOW_H = 24
TRACK_H = 12          # snapshot pairs until 12h old
SNAP_CAP = 400        # per-run pair snapshots, most-liquid-first
MIN_LIQ_KEEP = 0      # keep dust pairs too (dump tail is the data)


def get(url, tries=3):
    err = None
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except Exception as e:
            err = e
            time.sleep(1 + 2 ** a)
    print(f"dexscreener fail: {str(err)[:70]}")
    return None


def load_births(now):
    """mint -> {t, name, src} for births in the window."""
    out = {}
    for bf in BIRTH_FILES:
        if not os.path.exists(bf):
            continue
        src = os.path.basename(bf).split("_births")[0]
        with open(bf) as f:
            for l in f:
                try:
                    r = json.loads(l)
                except Exception:
                    continue
                mint = r.get("x_addr")
                if mint and r.get("t", 0) > now - BIRTH_WINDOW_H * 3600:
                    out.setdefault(mint, {"t": r["t"], "name": r.get("name"),
                                          "src": src})
    return out


def resolve_mint(mint):
    """Return best-liquidity Solana pair dict or None."""
    d = get(f"{DS}/tokens/{mint}", tries=2)
    pairs = [p for p in ((d or {}).get("pairs") or [])
             if p.get("chainId") == "solana" and p.get("pairAddress")]
    if not pairs:
        return None
    pairs.sort(key=lambda p: (p.get("liquidity") or {}).get("usd") or 0,
               reverse=True)
    return pairs[0]


def main():
    now = time.time()
    pairs = {}
    if os.path.exists(PAIRS):
        try:
            pairs = json.load(open(PAIRS))
        except Exception:
            pass

    births = load_births(now)

    # last-known liquidity per mint (for re-resolve decisions + ordering)
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

    new_res = 0
    for mint, b in births.items():
        rec = pairs.get(mint)
        if rec and rec.get("pair"):
            # re-resolve while young and dust: the skeleton pair may be
            # tracked while the real (PumpSwap) pair fills later
            pc = rec.get("pair_created")
            ref_t = (pc / 1000) if pc else rec.get("born_t", now)
            if now - ref_t > 3 * 3600 or liq_last.get(mint, 0) >= 1000:
                continue
        p = resolve_mint(mint)
        if p:
            if not pairs.get(mint, {}).get("pair") or (
                    (p.get("liquidity") or {}).get("usd") or 0) > 1000:
                pairs[mint] = {"pair": p["pairAddress"],
                               "dex": p.get("dexId"),
                               "name": b.get("name"),
                               "born_t": b["t"],
                               "pair_created": p.get("pairCreatedAt")}
                new_res += 1
        elif not pairs.get(mint):
            # mark unresolved so we retry next run (pairs appear with lag)
            pairs[mint] = {"pair": None, "name": b.get("name"),
                           "born_t": b["t"]}
    json.dump(pairs, open(PAIRS, "w"))

    # candidates: resolved, born within TRACK_H (use pair_created if known)
    cands = []
    for mint, rec in pairs.items():
        if not rec.get("pair"):
            continue
        pc = rec.get("pair_created")
        ref_t = (pc / 1000) if pc else rec.get("born_t", now)
        if now - ref_t < TRACK_H * 3600:
            cands.append((mint, rec))
    cands.sort(key=lambda mr: liq_last.get(mr[0], 0), reverse=True)
    cands = cands[:SNAP_CAP]

    n = 0
    with open(OUT, "a") as f:
        for mint, rec in cands:
            d = get(f"{DS}/pairs/solana/{rec['pair']}", tries=2)
            p = None
            if isinstance(d, dict):
                rows = d.get("pairs") or []
                p = rows[0] if rows else d.get("pair")
            if not p or not p.get("pairAddress"):
                continue
            pc = p.get("pairCreatedAt") or rec.get("pair_created")
            age_h = round((now - pc / 1000) / 3600, 2) if pc else None
            vol = p.get("volume") or {}
            tx = (p.get("txns") or {}).get("m5") or {}
            pcg = p.get("priceChange") or {}
            f.write(json.dumps({
                "t": now, "mint": mint, "name": rec.get("name"),
                "pair": p["pairAddress"], "dex": p.get("dexId"),
                "age_h": age_h,
                "price": float(p["priceUsd"]) if p.get("priceUsd") else None,
                "liq": (p.get("liquidity") or {}).get("usd"),
                "vol_5m": vol.get("m5"), "vol_h1": vol.get("h1"),
                "txns_m5_b": tx.get("buys"), "txns_m5_s": tx.get("sells"),
                "pc_5m": pcg.get("m5"), "pc_h1": pcg.get("h1"),
                "fdv": p.get("fdv"),
                "mc": p.get("marketCap"),
            }) + "\n")
            n += 1
    unresolved = sum(1 for r in pairs.values() if not r.get("pair"))
    print(f"pumpswap track: {len(births)} births 24h, {new_res} newly resolved, "
          f"{n} snapshotted, {unresolved} unresolved")


if __name__ == "__main__":
    main()
