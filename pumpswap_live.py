#!/usr/bin/env python3
"""
pumpswap_live.py — live executor for the measured-winning PumpSwap momentum
cell (GO_NOGO.md 2026-09-08):

  ENTRY (all gates must pass, one shot per scan):
    dex=pumpswap, age <= 0.5h, liq >= $25k, vol_5m >= 1x liq, buys > sells
  EXIT (checked every poll):
    +25% target | -40% stop | 35% trail from peak | 30 min max hold |
    reserve drain30 flag -> emergency sell attempt
  SIZE: fixed 0.10 SOL (owner directive). Max 3 concurrent positions.
  SOL-ONLY EXITS (owner directive): after every sell, close the token
    account so the wallet returns to pure SOL.

Execution mechanics come from the battle-tested live_trader (Jupiter pool
path, local signing, dynamic priority fees, farm/deployer/bundle blocking
gates, one-trade-per-mint). This file is strategy + bookkeeping only.

SAFETY: default is DRY-RUN (quotes + logs, nothing signed). Live only when
live_trader.live_enabled() passes (owner signoff + no kill switch) AND
--dry is NOT passed. --dry forces dry-run even when the gate is live.

Modes:
  python3 pumpswap_live.py --once [--dry]      # one scan+manage pass
  python3 pumpswap_live.py --minutes 8 [--dry] # loop at 20s cadence (watcher)
"""
import json, os, sys, time, urllib.request

import live_trader as lt

MON = os.path.dirname(os.path.abspath(__file__))
PAIRS = os.path.join(MON, "pumpswap_pairs.json")
SNAP = os.path.join(MON, "pumpswap_snapshots.jsonl")
RESERVE = os.path.join(MON, "pool_reserve_snapshots.jsonl")
POS_F = os.path.join(MON, "pumpswap_live_positions.json")
BOOK = os.path.join(MON, "pumpswap_live_trades.jsonl")

SIZE_SOL = 0.10            # owner directive
MAX_AGE_H = 0.5
MIN_LIQ = 25_000.0
TURNOVER = 1.0
TARGET = 1.25
STOP = 0.60
TRAIL = 0.65               # exit if px <= 65% of peak
MAX_HOLD_S = 30 * 60
MAX_OPEN = 3
DEX_URL = "https://api.dexscreener.com/latest/dex/tokens/"

FORCE_DRY = "--dry" in sys.argv


def _load(f, default):
    try:
        return json.load(open(f))
    except Exception:
        return default


def _save(f, obj):
    json.dump(obj, open(f, "w"))


def _log(row):
    with open(BOOK, "a") as f:
        f.write(json.dumps(row) + "\n")


def _latest_snaps():
    latest = {}
    if os.path.exists(SNAP):
        for l in open(SNAP):
            try:
                r = json.loads(l)
            except Exception:
                continue
            if r.get("mint"):
                latest[r["mint"]] = r
    return latest


def _drained_mints():
    out = set()
    if os.path.exists(RESERVE):
        for l in open(RESERVE):
            try:
                r = json.loads(l)
            except Exception:
                continue
            if r.get("drain30") and time.time() - r.get("t", 0) < 900:
                out.add(r["mint"])
    return out


def _fresh_px(mint):
    """Live DexScreener price/liq for exit decisions (not the 20-min batch)."""
    try:
        with urllib.request.urlopen(DEX_URL + mint, timeout=15) as r:
            d = json.loads(r.read())
        pairs = [p for p in (d.get("pairs") or []) if p.get("chainId") == "solana"]
        if not pairs:
            return None
        p = max(pairs, key=lambda x: (x.get("liquidity") or {}).get("usd") or 0)
        return {"price": float(p.get("priceUsd") or 0),
                "liq": (p.get("liquidity") or {}).get("usd") or 0}
    except Exception:
        return None


def scan_entries(now, positions, closed_mints, latest, dry):
    if len(positions) >= MAX_OPEN:
        return
    pairs = _load(PAIRS, {})
    cands = []
    for mint, p in pairs.items():
        if p.get("dex") != "pumpswap" or mint in positions or mint in closed_mints:
            continue
        age_h = (now - p.get("born_t", now)) / 3600
        if age_h > MAX_AGE_H:
            continue
        s = latest.get(mint)
        if not s:
            continue
        liq = s.get("liq") or 0
        if liq < MIN_LIQ or (s.get("vol_5m") or 0) < TURNOVER * liq:
            continue
        if (s.get("txns_m5_b") or 0) <= (s.get("txns_m5_s") or 0):
            continue
        cands.append((liq, mint, p, s))
    if not cands:
        return
    cands.sort(key=lambda x: -x[0])
    liq, mint, p, s = cands[0]
    row = {"action": "entry_signal", "mint": mint, "name": p.get("name"),
           "age_h": round((now - p.get("born_t", now)) / 3600, 3),
           "liq": liq, "entry_px": s.get("price")}
    if dry:
        row["result"] = "dry-run: would buy 0.10 SOL"
        _log(row)
        print(f"  ENTRY-SIGNAL (dry) {p.get('name')} liq=${liq:,.0f} "
              f"age={row['age_h']}h px={s.get('price')}")
        return
    res = lt.buy(mint, reason="pumpswap_momentum_cell", size_sol=SIZE_SOL)
    row["buy_result"] = res.get("result")
    row["mode"] = res.get("mode")
    _log(row)
    print(f"  ENTRY {p.get('name')}: {res.get('result')} [{res.get('mode')}]")
    if res.get("result") == "submitted" and res.get("mode") == "live":
        positions[mint] = {
            "name": p.get("name"), "entry_t": now,
            "entry_px": s.get("price"), "peak_px": s.get("price"),
            "size_sol": SIZE_SOL, "tokens_raw": res.get("tokens_raw"),
            "sig": res.get("sig")}
        _save(POS_F, positions)


def manage_exits(now, positions, drained, dry):
    for mint in list(positions):
        pos = positions[mint]
        cur = _fresh_px(mint)
        if not cur or not cur["price"]:
            continue
        px = cur["price"]
        pos["peak_px"] = max(pos.get("peak_px") or 0, px)
        entry_px = pos.get("entry_px") or 0
        if not entry_px:
            continue
        ret = px / entry_px
        held = now - pos["entry_t"]
        reason = None
        if mint in drained:
            reason = "reserve_drain"
        elif ret >= TARGET:
            reason = "target"
        elif ret <= STOP:
            reason = "stop"
        elif px <= pos["peak_px"] * TRAIL:
            reason = "trail"
        elif held >= MAX_HOLD_S:
            reason = "max_hold"
        if not reason:
            continue
        row = {"action": "exit_signal", "mint": mint, "name": pos.get("name"),
               "reason": reason, "ret": round(ret, 3),
               "held_min": round(held / 60, 1)}
        if dry:
            row["result"] = "dry-run: would sell all + close ATA"
            _log(row)
            print(f"  EXIT-SIGNAL (dry) {pos.get('name')} {reason} ret={ret:.2f}")
            continue
        sell = lt.pool_sell(mint, pos.get("tokens_raw") or 0,
                            reason=f"pslive_{reason}")
        row["sell_result"] = sell.get("result")
        # SOL-only: close the ATA after the sell regardless of dust
        close = lt.close_token_accounts(mints=[mint], reason="post_exit")
        row["close_result"] = close.get("result")
        _log(row)
        print(f"  EXIT {pos.get('name')} {reason}: sell={sell.get('result')} "
              f"close={close.get('result')}")
        del positions[mint]
        _save(POS_F, positions)


def one_pass(dry):
    now = time.time()
    positions = _load(POS_F, {})
    closed = set()
    if os.path.exists(BOOK):
        for l in open(BOOK):
            try:
                r = json.loads(l)
            except Exception:
                continue
            if r.get("action") == "exit_signal":
                closed.add(r.get("mint"))
    manage_exits(now, positions, _drained_mints(), dry)
    scan_entries(now, positions, closed, _latest_snaps(), dry)


def main():
    dry = FORCE_DRY
    if not dry:
        ok, why = lt.live_enabled()
        if not ok:
            dry = True
            print(f"gate closed ({why}) -> dry-run")
    if "--once" in sys.argv:
        one_pass(dry)
        return
    minutes = 8
    if "--minutes" in sys.argv:
        minutes = int(sys.argv[sys.argv.index("--minutes") + 1])
    deadline = time.time() + minutes * 60
    while time.time() < deadline:
        t0 = time.time()
        one_pass(dry)
        time.sleep(max(1, 20 - (time.time() - t0)))


if __name__ == "__main__":
    main()
