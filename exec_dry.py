#!/usr/bin/env python3
"""
exec_dry.py — execution-first DRY paper book for early PumpSwap momentum.

FINDINGS 2026-09-13: paper edges died on fills, not detection.
This loop quotes Jupiter for every fill, models failed txs + reserve-drain
rugs, and refuses to run unless STOP_LIVE_TRADING is present.

Lane (GO_NOGO 2026-09-08):
  enter: pumpswap, age<=0.5h, liq>=$25k, vol_5m>=1x liq, buys>sells
  exit:  +25% | -40% | 35% trail | 30m max | reserve_drain
  size:  0.10 SOL paper, max 3 open

Usage:
  python3 exec_dry.py --once | --minutes N | --status
"""
from __future__ import annotations

import json
import os
import random
import ssl
import sys
import time
import urllib.request
from pathlib import Path

import certifi

MON = Path(__file__).resolve().parent
KILL = MON / "STOP_LIVE_TRADING"
PAIRS = MON / "pumpswap_pairs.json"
SNAP = MON / "pumpswap_snapshots.jsonl"
RESERVE = MON / "pool_reserve_snapshots.jsonl"
POS_F = MON / "exec_dry_positions.json"
BOOK = MON / "exec_dry_trades.jsonl"
STATE = MON / "exec_dry_state.json"
EDGE_CAND = MON / "edge_candidates.jsonl"
CAND_FRESH_S = 2 * 3600  # convergence candidates stay priority for 2h
UNIVERSE_LATEST = MON / "data" / "universe_latest.json"
# Optional override (box feed synced onto Mac)
UNIVERSE_ENV = os.environ.get("MEMECOINS_UNIVERSE")

SIZE_SOL = 0.10
MAX_AGE_H = 0.5
MIN_LIQ = 25_000.0
TURNOVER = 1.0
TARGET = 1.25
STOP = 0.60
TRAIL = 0.65
MAX_HOLD_S = 30 * 60
MAX_OPEN = 3
FAIL_TX_RATE = 0.08
MAX_IMPACT = 0.05  # reject quotes with >5% price impact
# Kimi edge_screen: hard-block AVOID only. Age<40m is WATCH there, so early
# PumpSwap lane (age<=30m) can still fill. PASS/WATCH proceed to Jupiter.
EDGE_SCREEN = os.environ.get("EDGE_SCREEN", "1") != "0"
PRIORITY_FEE_SOL = 0.0002
RUG_RECOVERY = 0.10
SLIPPAGE_BPS = 200
DEX = "https://api.dexscreener.com/latest/dex/tokens/"
JUP_Q = "https://lite-api.jup.ag/swap/v1/quote"
GT_NEW = "https://api.geckoterminal.com/api/v2/networks/solana/new_pools?page=1"
SOL = "So11111111111111111111111111111111111111112"

CTX = ssl.create_default_context(cafile=certifi.where())
UA = {"User-Agent": "darwin-labs-exec-dry/1.0", "Accept": "application/json"}


def _die_if_live_possible():
    if not KILL.exists():
        print("REFUSING: STOP_LIVE_TRADING missing. This loop is dry-only.")
        sys.exit(2)


def _load(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _save(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2))


def _log(row: dict):
    row = dict(row)
    row.setdefault("ts", time.time())
    with BOOK.open("a") as f:
        f.write(json.dumps(row) + "\n")


def _http_json(url: str, timeout: float = 20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return json.loads(r.read())


def jupiter_buy_quote(mint: str, size_sol: float):
    params = (
        f"inputMint={SOL}&outputMint={mint}"
        f"&amount={int(size_sol * 1e9)}&slippageBps={SLIPPAGE_BPS}"
    )
    try:
        return _http_json(f"{JUP_Q}?{params}")
    except Exception as e:
        return {"error": str(e)[:160]}


def jupiter_sell_quote(mint: str, token_raw: int):
    if token_raw <= 0:
        return {"error": "no tokens"}
    params = (
        f"inputMint={mint}&outputMint={SOL}"
        f"&amount={int(token_raw)}&slippageBps={SLIPPAGE_BPS}"
    )
    try:
        return _http_json(f"{JUP_Q}?{params}")
    except Exception as e:
        return {"error": str(e)[:160]}


def dex_token(mint: str):
    try:
        d = _http_json(DEX + mint)
        pairs = [p for p in (d.get("pairs") or []) if p.get("chainId") == "solana"]
        if not pairs:
            return None, []
        best = max(pairs, key=lambda x: (x.get("liquidity") or {}).get("usd") or 0)
        return best, pairs
    except Exception:
        return None, []


def snapshot_from_pair(now: float, mint: str, name: str, pair: dict, born_t: float | None):
    pc = pair.get("pairCreatedAt")
    age_h = round((now - pc / 1000) / 3600, 2) if pc else None
    vol = pair.get("volume") or {}
    tx = (pair.get("txns") or {}).get("m5") or {}
    pcg = pair.get("priceChange") or {}
    row = {
        "t": now,
        "mint": mint,
        "name": name,
        "pair": pair.get("pairAddress"),
        "dex": pair.get("dexId"),
        "age_h": age_h,
        "price": float(pair["priceUsd"]) if pair.get("priceUsd") else None,
        "liq": (pair.get("liquidity") or {}).get("usd"),
        "vol_5m": vol.get("m5"),
        "vol_h1": vol.get("h1"),
        "txns_m5_b": tx.get("buys"),
        "txns_m5_s": tx.get("sells"),
        "pc_5m": pcg.get("m5"),
        "pc_h1": pcg.get("h1"),
        "fdv": pair.get("fdv"),
        "mc": pair.get("marketCap"),
        "src": "exec_dry",
    }
    with SNAP.open("a") as f:
        f.write(json.dumps(row) + "\n")
    return row


def refresh_universe(now: float) -> int:
    """Prefer Slice 1 universe_latest.json; fall back to GeckoTerminal."""
    feed = Path(UNIVERSE_ENV) if UNIVERSE_ENV else UNIVERSE_LATEST
    if feed.exists():
        try:
            snap = json.loads(feed.read_text())
        except Exception as e:
            print(f"  universe read fail: {e}")
            snap = None
        if isinstance(snap, dict) and snap.get("items") is not None:
            return _ingest_slice1(now, snap)
        print("  universe feed empty/invalid — falling back to GT")
    return _refresh_geckoterminal(now)


def _ingest_slice1(now: float, snap: dict) -> int:
    """Merge Slice1 universe rows into pairs + snapshots. Return pumpswap snaps written."""
    pairs = _load(PAIRS, {})
    n_snap = 0
    for it in snap.get("items") or []:
        mint = it.get("mint")
        if not mint:
            continue
        dex = (it.get("dex_id") or "") or ""
        born_t = None
        if it.get("pair_created_at_ms"):
            born_t = it["pair_created_at_ms"] / 1000.0
        elif it.get("first_seen"):
            try:
                import datetime
                born_t = datetime.datetime.fromisoformat(
                    it["first_seen"].replace("Z", "+00:00")
                ).timestamp()
            except Exception:
                born_t = now
        pairs[mint] = {
            "pair": it.get("pair_address"),
            "dex": dex,
            "name": it.get("name") or it.get("symbol"),
            "symbol": it.get("symbol"),
            "born_t": born_t or now,
            "pair_created": it.get("pair_created_at_ms"),
            "src": "slice1",
            "graduated": it.get("graduated"),
            "pass_filters": it.get("pass_filters"),
        }
        # snapshot pumpswap / graduated rows so entry gates can see them
        if "pumpswap" in dex.lower() or it.get("graduated"):
            price = it.get("price_usd")
            try:
                price_f = float(price) if price is not None else None
            except Exception:
                price_f = None
            row = {
                "t": now,
                "mint": mint,
                "name": it.get("name") or it.get("symbol"),
                "pair": it.get("pair_address"),
                "dex": dex,
                "age_h": round(it["age_min"] / 60.0, 3) if it.get("age_min") is not None else None,
                "price": price_f,
                "liq": it.get("liq_usd"),
                "vol_5m": it.get("vol_5m"),
                "vol_h1": it.get("vol_1h"),
                "txns_m5_b": it.get("buys_5m"),
                "txns_m5_s": it.get("sells_5m"),
                "src": "slice1",
            }
            with SNAP.open("a") as f:
                f.write(json.dumps(row) + "\n")
            n_snap += 1
    _save(PAIRS, pairs)
    updated = snap.get("updated_at")
    print(f"  universe slice1 updated_at={updated} items={snap.get('count')} snaps+={n_snap}")
    return n_snap


def _refresh_geckoterminal(now: float) -> int:
    """Pull GeckoTerminal newborns, resolve via DexScreener, snapshot PumpSwap."""
    pairs = _load(PAIRS, {})
    try:
        gt = _http_json(GT_NEW)
    except Exception as e:
        print(f"  universe gt fail: {e}")
        return 0
    n_snap = 0
    for item in gt.get("data") or []:
        rel = item.get("relationships") or {}
        base = ((rel.get("base_token") or {}).get("data") or {}).get("id") or ""
        if not base.startswith("solana_"):
            continue
        mint = base.split("_", 1)[1]
        dex = ((rel.get("dex") or {}).get("data") or {}).get("id") or ""
        attrs = item.get("attributes") or {}
        name = attrs.get("name")
        created = attrs.get("pool_created_at")
        born_t = None
        if created:
            try:
                import datetime
                born_t = datetime.datetime.fromisoformat(
                    created.replace("Z", "+00:00")
                ).timestamp()
            except Exception:
                born_t = now
        best, _ = dex_token(mint)
        if not best:
            continue
        dex_id = (best.get("dexId") or dex or "").lower()
        liq = (best.get("liquidity") or {}).get("usd") or 0
        # track pumpswap graduates; also keep pump-fun for migration watch
        if "pump" not in dex_id and "meteora" not in dex_id and "raydium" not in dex_id:
            continue
        rec = pairs.get(mint) or {}
        pc = best.get("pairCreatedAt")
        pairs[mint] = {
            "pair": best.get("pairAddress") or rec.get("pair"),
            "dex": best.get("dexId") or dex,
            "name": name or rec.get("name"),
            "born_t": born_t or rec.get("born_t") or (pc / 1000 if pc else now),
            "pair_created": pc or rec.get("pair_created"),
            "gt_dex": dex,
        }
        if "pumpswap" in dex_id:
            snapshot_from_pair(now, mint, name, best, born_t)
            n_snap += 1
    _save(PAIRS, pairs)
    return n_snap



def latest_snaps() -> dict:
    latest = {}
    if SNAP.exists():
        for l in SNAP.open():
            try:
                r = json.loads(l)
            except Exception:
                continue
            if r.get("mint"):
                latest[r["mint"]] = r
    return latest


def drained_mints(now: float) -> set:
    out = set()
    if not RESERVE.exists():
        return out
    for l in RESERVE.open():
        try:
            r = json.loads(l)
        except Exception:
            continue
        if r.get("drain30") and now - r.get("t", 0) < 900:
            out.add(r["mint"])
    return out


def closed_mints() -> set:
    out = set()
    if not BOOK.exists():
        return out
    for l in BOOK.open():
        try:
            r = json.loads(l)
        except Exception:
            continue
        if r.get("action") == "exit" and r.get("mint"):
            out.add(r["mint"])
    return out


def simulate_fail() -> bool:
    # Do NOT use time_ns()%1000 — on this Mac the clock resolution makes
    # that residue almost always < 80, so an 8% fail model became 100%.
    return random.random() < FAIL_TX_RATE



def _edge_candidates() -> set:
    """Mints with fresh convergence alerts — preferred over liquidity rank."""
    out = set()
    if not EDGE_CAND.exists():
        return out
    cut = time.time() - CAND_FRESH_S
    try:
        with EDGE_CAND.open() as f:
            for line in f:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("t", 0) >= cut and r.get("mint"):
                    out.add(r["mint"])
    except Exception:
        pass
    return out


def edge_screen_verdict(mint: str, age_min: float | None = None) -> dict:
    """Run Kimi edge_screen. Returns {verdict, checks, error?}. Never raises."""
    try:
        from edge_screen import screen
        # exec_dry's lane IS the sub-30m PumpSwap lane — use the named
        # profile so the age floor is waived instead of always WATCH.
        return screen(mint, deployer=None, mcap_sol=None, age_min=age_min,
                      profile="early_pumpswap")
    except Exception as e:
        return {"verdict": "WATCH", "checks": [], "error": str(e)[:120],
                "elapsed_s": None}

def scan_entries(now: float, positions: dict, closed: set, latest: dict):
    if len(positions) >= MAX_OPEN:
        return
    pairs = _load(PAIRS, {})
    cands = []
    for mint, p in pairs.items():
        if "pumpswap" not in (p.get("dex") or "").lower():
            continue
        if mint in positions or mint in closed:
            continue
        age_h = (now - p.get("born_t", now)) / 3600
        if age_h > MAX_AGE_H:
            continue
        s = latest.get(mint)
        if not s:
            best, _ = dex_token(mint)
            if not best:
                continue
            s = snapshot_from_pair(now, mint, p.get("name"), best, p.get("born_t"))
        liq = s.get("liq") or 0
        if liq < MIN_LIQ or (s.get("vol_5m") or 0) < TURNOVER * liq:
            continue
        if (s.get("txns_m5_b") or 0) <= (s.get("txns_m5_s") or 0):
            continue
        cands.append((liq, mint, p, s, age_h))
    if not cands:
        return
    # convergence candidates outrank raw liquidity; rest sort by liq
    priority = _edge_candidates()
    cands.sort(key=lambda x: (x[1] not in priority, -x[0]))
    liq, mint, p, s, age_h = cands[0]
    if mint in priority:
        print(f"  ENTRY prefer convergence candidate {p.get('name')} "
              f"({mint[:10]}…)")
    mid = s.get("price") or 0
    best, _ = dex_token(mint)
    if best and best.get("priceUsd"):
        mid = float(best["priceUsd"])
        liq = (best.get("liquidity") or {}).get("usd") or liq
    # live liq can be far below the snapshot that qualified us
    if liq < MIN_LIQ:
        print(f"  ENTRY skip (live liq ${liq:,.0f} < min) {p.get('name')}")
        return

    # Kimi EDGE CAPTURE gate — AVOID blocks dry entry; PASS/WATCH continue.
    if EDGE_SCREEN:
        age_min = round(age_h * 60, 1)
        scr = edge_screen_verdict(mint, age_min=age_min)
        verdict = scr.get("verdict") or "WATCH"
        row_scr = {
            "action": "entry_eval",
            "mint": mint,
            "name": p.get("name"),
            "age_h": round(age_h, 3),
            "liq": liq,
            "mid_px": mid,
            "result": f"edge_{verdict.lower()}",
            "edge_verdict": verdict,
            "edge_checks": [
                {"check": c.get("check"), "verdict": c.get("verdict"),
                 "value": c.get("value")}
                for c in (scr.get("checks") or [])
            ],
            "edge_elapsed_s": scr.get("elapsed_s"),
            "edge_error": scr.get("error"),
        }
        if verdict == "AVOID":
            _log(row_scr)
            reasons = [
                f"{c.get('check')}={c.get('value')}"
                for c in (scr.get("checks") or [])
                if c.get("verdict") == "AVOID"
            ]
            print(f"  ENTRY skip (edge AVOID) {p.get('name')} "
                  f"{', '.join(reasons) or scr.get('error') or ''}")
            return
        # PASS / WATCH: keep going; attach verdict onto the eventual fill row
        p["_edge_verdict"] = verdict
        p["_edge_checks"] = row_scr["edge_checks"]

    q = jupiter_buy_quote(mint, SIZE_SOL)
    row = {
        "action": "entry_eval",
        "mint": mint,
        "name": p.get("name"),
        "age_h": round(age_h, 3),
        "liq": liq,
        "mid_px": mid,
    }
    if not q or q.get("error") or not q.get("outAmount"):
        row["result"] = "quote_fail"
        row["error"] = (q or {}).get("error")
        _log(row)
        print(f"  ENTRY skip (quote fail) {p.get('name')}: {row.get('error')}")
        return
    try:
        impact = float(q.get("priceImpactPct") or 0)
    except Exception:
        impact = 0.0
    if impact > MAX_IMPACT:
        row["result"] = "impact_reject"
        row["quote_impact"] = impact
        _log(row)
        print(f"  ENTRY skip (impact {impact:.1%} > {MAX_IMPACT:.0%}) {p.get('name')}")
        return
    if simulate_fail():
        row["result"] = "failed_tx"
        _log(row)
        print(f"  ENTRY failed_tx {p.get('name')} (modeled)")
        return

    out_raw = int(q["outAmount"])
    positions[mint] = {
        "name": p.get("name"),
        "entry_t": now,
        "entry_sol": SIZE_SOL,
        "tokens_raw": out_raw,
        "mid_px_entry": mid,
        "quote_out_entry": out_raw,
        "peak_mid": mid,
        "age_h_entry": round(age_h, 3),
        "liq_entry": liq,
        "quote_impact_entry": q.get("priceImpactPct"),
    }
    _save(POS_F, positions)
    row.update({
        "action": "entry",
        "result": "filled",
        "quote_out": out_raw,
        "quote_impact": q.get("priceImpactPct"),
        "priority_fee_sol": PRIORITY_FEE_SOL,
        "mode": "dry-exec",
        "edge_verdict": p.get("_edge_verdict"),
        "edge_checks": p.get("_edge_checks"),
    })
    _log(row)
    print(
        f"  ENTRY filled {p.get('name')} liq=${liq:,.0f} age={age_h:.3f}h "
        f"out={out_raw} impact={q.get('priceImpactPct')}"
    )


def manage_exits(now: float, positions: dict, drained: set):
    for mint in list(positions):
        pos = positions[mint]
        best, _ = dex_token(mint)
        if not best or not best.get("priceUsd"):
            continue
        px = float(best["priceUsd"])
        pos["peak_mid"] = max(pos.get("peak_mid") or 0, px)
        held = now - pos["entry_t"]
        mid_ret = px / pos["mid_px_entry"] if pos.get("mid_px_entry") else None
        reason = None
        if mint in drained:
            reason = "reserve_drain"
        elif mid_ret is not None and mid_ret >= TARGET:
            reason = "target"
        elif mid_ret is not None and mid_ret <= STOP:
            reason = "stop"
        elif pos.get("peak_mid") and px <= pos["peak_mid"] * TRAIL:
            reason = "trail"
        elif held >= MAX_HOLD_S:
            reason = "max_hold"
        if not reason:
            continue

        row = {
            "action": "exit_eval",
            "mint": mint,
            "name": pos.get("name"),
            "reason": reason,
            "mid_ret": round(mid_ret, 4) if mid_ret is not None else None,
            "held_min": round(held / 60, 1),
            "liq": (best.get("liquidity") or {}).get("usd"),
        }
        if reason == "reserve_drain":
            net_sol = pos["entry_sol"] * RUG_RECOVERY - PRIORITY_FEE_SOL
            row.update({
                "action": "exit",
                "result": "rug_salvage",
                "net_sol": round(net_sol, 6),
                "pnl_sol": round(net_sol - pos["entry_sol"], 6),
                "mode": "dry-exec",
            })
            _log(row)
            print(f"  EXIT rug {pos.get('name')} salvage={net_sol:.4f} SOL")
            del positions[mint]
            _save(POS_F, positions)
            continue
        if simulate_fail():
            row["result"] = "failed_tx"
            _log(row)
            print(f"  EXIT failed_tx {pos.get('name')} {reason} (modeled, retry)")
            continue
        q = jupiter_sell_quote(mint, int(pos.get("tokens_raw") or 0))
        if not q or q.get("error") or not q.get("outAmount"):
            row["result"] = "quote_fail"
            row["error"] = (q or {}).get("error")
            _log(row)
            print(f"  EXIT quote_fail {pos.get('name')} {reason}: {row.get('error')}")
            continue
        out_sol = int(q["outAmount"]) / 1e9
        net_sol = out_sol - PRIORITY_FEE_SOL
        quote_ret = net_sol / pos["entry_sol"] if pos["entry_sol"] else None
        row.update({
            "action": "exit",
            "result": "filled",
            "exit_reason": reason,
            "quote_out_sol": round(out_sol, 6),
            "net_sol": round(net_sol, 6),
            "pnl_sol": round(net_sol - pos["entry_sol"], 6),
            "quote_ret": round(quote_ret, 4) if quote_ret is not None else None,
            "mid_vs_quote_gap": (
                round(quote_ret - mid_ret, 4)
                if quote_ret is not None and mid_ret is not None else None
            ),
            "quote_impact": q.get("priceImpactPct"),
            "mode": "dry-exec",
        })
        _log(row)
        print(
            f"  EXIT {pos.get('name')} {reason} mid_ret={mid_ret:.3f} "
            f"quote_ret={quote_ret:.3f} pnl={net_sol - pos['entry_sol']:+.4f} SOL"
        )
        del positions[mint]
        _save(POS_F, positions)


def one_pass():
    _die_if_live_possible()
    now = time.time()
    n = refresh_universe(now)
    positions = _load(POS_F, {})
    manage_exits(now, positions, drained_mints(now))
    scan_entries(now, positions, closed_mints(), latest_snaps())
    _save(STATE, {
        "t": now,
        "open": len(positions),
        "open_mints": list(positions),
        "universe_pumpswap_snaps": n,
        "kill_switch": True,
        "mode": "dry-exec",
    })
    print(f"pass ok universe_pumpswap_snaps={n} open={len(positions)}")


def status():
    st = _load(STATE, {})
    pos = _load(POS_F, {})
    closes = []
    if BOOK.exists():
        for l in BOOK.open():
            try:
                r = json.loads(l)
            except Exception:
                continue
            if r.get("action") == "exit":
                closes.append(r)
    n = len(closes)
    pnl = sum(r.get("pnl_sol") or 0 for r in closes)
    print(json.dumps({
        "open": len(pos),
        "closed": n,
        "pnl_sol": round(pnl, 6),
        "mean_pnl": round(pnl / n, 6) if n else None,
        "last_pass_age_s": round(time.time() - st["t"], 1) if st.get("t") else None,
        "kill_switch": KILL.exists(),
        "mode": "dry-exec",
    }, indent=2))


def main():
    _die_if_live_possible()
    if "--status" in sys.argv:
        status()
        return
    if "--once" in sys.argv:
        one_pass()
        return
    minutes = 60
    if "--minutes" in sys.argv:
        minutes = int(sys.argv[sys.argv.index("--minutes") + 1])
    deadline = time.time() + minutes * 60
    print(f"exec_dry starting minutes={minutes} kill_switch={KILL.exists()}")
    while time.time() < deadline:
        t0 = time.time()
        try:
            one_pass()
        except Exception as e:
            print(f"pass error: {e}")
        time.sleep(max(5, 20 - (time.time() - t0)))


if __name__ == "__main__":
    main()
