#!/usr/bin/env python3
"""pattern_markout.py — dry observation logger for near-grad → PumpSwap joins + markouts.

Observation only. Never submits swaps. Requires STOP_LIVE_TRADING kill switch.
"""
from __future__ import annotations

import argparse
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import certifi
except ImportError:  # pragma: no cover
    certifi = None  # type: ignore

ROOT = Path(__file__).resolve().parent
STOP = ROOT / "STOP_LIVE_TRADING"
UNIVERSE = ROOT / "data" / "universe_latest.json"
STATE_PATH = ROOT / "pattern_state.json"
EVENTS_PATH = ROOT / "pattern_events.jsonl"

WSOL = "So11111111111111111111111111111111111111112"
JUP_QUOTE = "https://lite-api.jup.ag/swap/v1/quote"
DEX_TOKEN = "https://api.dexscreener.com/latest/dex/tokens/{mint}"
QUOTE_SOL = 0.1
LIQ_QUOTE_MIN = 10_000.0
MARKOUT_LADDER = (
    (300, "markout_5m"),
    (900, "markout_15m"),
    (1800, "markout_30m"),
)
UA = "memecoin-monitor-pattern-markout/0.1 (+dry observation; no live)"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_ts() -> float:
    return time.time()


def _ssl_context() -> ssl.SSLContext:
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def _http_json(url: str, timeout: float = 20.0) -> Any:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _save_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def _append_event(ev: dict) -> None:
    with EVENTS_PATH.open("a") as f:
        f.write(json.dumps(ev, separators=(",", ":")) + "\n")


def _f(x: Any) -> float | None:
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _mint_state(state: dict, mint: str) -> dict:
    mints = state.setdefault("mints", {})
    st = mints.get(mint)
    if st is None:
        st = {
            "emitted": [],
            "near_grad": None,
            "pump_complete": None,
            "first_pumpswap": None,
            "first_pumpfun_bonding": None,
        }
        mints[mint] = st
    st.setdefault("emitted", [])
    return st


def _already(st: dict, event_type: str) -> bool:
    return event_type in (st.get("emitted") or [])


def _mark_emitted(st: dict, event_type: str) -> None:
    em = st.setdefault("emitted", [])
    if event_type not in em:
        em.append(event_type)


def _snapshot_near_grad(row: dict) -> dict:
    return {
        "t": _now_ts(),
        "t_iso": _now_iso(),
        "bonding_progress_pct": _f(row.get("bonding_progress_pct")),
        "bonding_remaining_sol": _f(row.get("bonding_remaining_sol")),
        "real_sol": _f(row.get("real_sol")),
        "dex_id": row.get("dex_id"),
        "symbol": row.get("symbol"),
        "price_usd": _f(row.get("price_usd")),
        "liq_usd": _f(row.get("liq_usd")),
        "vol_5m": _f(row.get("vol_5m")),
        "age_min": _f(row.get("age_min")),
    }


def _snapshot_complete(row: dict) -> dict:
    return _snapshot_near_grad(row) | {
        "pump_complete": bool(row.get("pump_complete")),
        "graduated": bool(row.get("graduated")),
    }


def _snapshot_pumpswap(row: dict) -> dict:
    return {
        "t": _now_ts(),
        "t_iso": _now_iso(),
        "dex_id": row.get("dex_id"),
        "symbol": row.get("symbol"),
        "pair_address": row.get("pair_address"),
        "price_usd": _f(row.get("price_usd")),
        "liq_usd": _f(row.get("liq_usd")),
        "vol_5m": _f(row.get("vol_5m")),
        "age_min": _f(row.get("age_min")),
        "buys_5m": row.get("buys_5m"),
        "sells_5m": row.get("sells_5m"),
    }


def _snapshot_pumpfun_bonding(row: dict) -> dict:
    return {
        "t": _now_ts(),
        "t_iso": _now_iso(),
        "dex_id": row.get("dex_id"),
        "bonding_progress_pct": _f(row.get("bonding_progress_pct")),
        "bonding_remaining_sol": _f(row.get("bonding_remaining_sol")),
        "bonding_token_progress_pct": _f(row.get("bonding_token_progress_pct")),
        "real_sol": _f(row.get("real_sol")),
        "virtual_sol": _f(row.get("virtual_sol")),
        "bonding_source": row.get("bonding_source"),
        "pump_complete": row.get("pump_complete"),
        "symbol": row.get("symbol"),
    }


def jupiter_quote_buy(mint: str, sol: float = QUOTE_SOL) -> dict:
    """Quote only — NEVER submit a swap. Returns fields for event logging."""
    amount = int(sol * 1e9)
    url = (
        f"{JUP_QUOTE}?inputMint={WSOL}&outputMint={mint}"
        f"&amount={amount}&slippageBps=1500"
    )
    try:
        q = _http_json(url, timeout=20.0)
        out_amount = q.get("outAmount")
        impact = q.get("priceImpactPct")
        try:
            impact_f = float(impact) if impact is not None else None
        except (TypeError, ValueError):
            impact_f = None
        return {
            "ok": True,
            "quote_impact": impact_f,
            "out_amount": out_amount,
            "in_amount_lamports": amount,
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def dexscreener_token(mint: str) -> dict | None:
    try:
        data = _http_json(DEX_TOKEN.format(mint=mint), timeout=20.0)
    except Exception:
        return None
    pairs = data.get("pairs") if isinstance(data, dict) else None
    if not isinstance(pairs, list) or not pairs:
        return None
    # Prefer solana + highest liquidity
    sol = [p for p in pairs if str(p.get("chainId", "")).lower() == "solana"]
    pool = sol or pairs

    def liq_key(p: dict) -> float:
        return float((p.get("liquidity") or {}).get("usd") or 0)

    best = max(pool, key=liq_key)
    price = _f(best.get("priceUsd"))
    liq = liq_key(best)
    return {
        "price_usd": price,
        "liq_usd": liq if liq > 0 else None,
        "dex_id": best.get("dexId"),
        "pair_address": best.get("pairAddress"),
    }


def _maybe_attach_quote(ev: dict, mint: str, liq_usd: float | None) -> None:
    if not mint or liq_usd is None or liq_usd < LIQ_QUOTE_MIN:
        return
    q = jupiter_quote_buy(mint)
    if q.get("ok"):
        ev["quote_impact"] = q.get("quote_impact")
        ev["out_amount"] = q.get("out_amount")
        ev["quote_sol"] = QUOTE_SOL
    else:
        ev["quote_error"] = q.get("error")


def process_transitions(items: list[dict], state: dict) -> list[dict]:
    new_events: list[dict] = []
    now = _now_ts()
    now_iso = _now_iso()

    for row in items:
        mint = row.get("mint")
        if not mint or not isinstance(mint, str):
            continue
        st = _mint_state(state, mint)
        dex = (row.get("dex_id") or "").lower()

        # First pumpfun row with bonding fields
        has_bonding = (
            dex == "pumpfun"
            and (
                row.get("bonding_progress_pct") is not None
                or row.get("bonding_remaining_sol") is not None
                or row.get("real_sol") is not None
            )
        )
        if has_bonding and st.get("first_pumpfun_bonding") is None:
            st["first_pumpfun_bonding"] = _snapshot_pumpfun_bonding(row)

        # near_grad_first
        if row.get("near_grad") and not _already(st, "near_grad_first"):
            snap = _snapshot_near_grad(row)
            st["near_grad"] = snap
            ev = {
                "event": "near_grad_first",
                "t": now,
                "t_iso": now_iso,
                "mint": mint,
                "symbol": row.get("symbol"),
                **{k: snap[k] for k in (
                    "bonding_progress_pct",
                    "bonding_remaining_sol",
                    "dex_id",
                    "price_usd",
                    "liq_usd",
                    "vol_5m",
                    "age_min",
                )},
            }
            _append_event(ev)
            _mark_emitted(st, "near_grad_first")
            new_events.append(ev)

        # pump_complete_first
        if row.get("pump_complete") is True and not _already(st, "pump_complete_first"):
            snap = _snapshot_complete(row)
            st["pump_complete"] = snap
            ev = {
                "event": "pump_complete_first",
                "t": now,
                "t_iso": now_iso,
                "mint": mint,
                "symbol": row.get("symbol"),
                **{k: snap.get(k) for k in (
                    "bonding_progress_pct",
                    "bonding_remaining_sol",
                    "dex_id",
                    "price_usd",
                    "liq_usd",
                    "vol_5m",
                    "age_min",
                    "graduated",
                )},
            }
            _append_event(ev)
            _mark_emitted(st, "pump_complete_first")
            new_events.append(ev)

        # first_pumpswap (strict dex_id == pumpswap)
        if dex == "pumpswap" and not _already(st, "first_pumpswap"):
            snap = _snapshot_pumpswap(row)
            st["first_pumpswap"] = snap
            # entry marks for soft markouts
            st["entry_price_usd"] = snap.get("price_usd")
            st["entry_liq_usd"] = snap.get("liq_usd")

            ev = {
                "event": "first_pumpswap",
                "t": now,
                "t_iso": now_iso,
                "mint": mint,
                "symbol": row.get("symbol"),
                "liq_usd": snap.get("liq_usd"),
                "vol_5m": snap.get("vol_5m"),
                "age_min": snap.get("age_min"),
                "price_usd": snap.get("price_usd"),
                "pair_address": snap.get("pair_address"),
            }
            _maybe_attach_quote(ev, mint, snap.get("liq_usd"))
            _append_event(ev)
            _mark_emitted(st, "first_pumpswap")
            new_events.append(ev)

            # near_grad_to_pumpswap
            ng = st.get("near_grad")
            if ng is not None and not _already(st, "near_grad_to_pumpswap"):
                dt_s = now - float(ng.get("t") or now)
                ev2 = {
                    "event": "near_grad_to_pumpswap",
                    "t": now,
                    "t_iso": now_iso,
                    "mint": mint,
                    "symbol": row.get("symbol"),
                    "dt_s": round(dt_s, 3),
                    "bond_pct_at_near_grad": ng.get("bonding_progress_pct"),
                    "liq_usd": snap.get("liq_usd"),
                    "vol_5m": snap.get("vol_5m"),
                    "age_min": snap.get("age_min"),
                    "price_usd": snap.get("price_usd"),
                }
                _maybe_attach_quote(ev2, mint, snap.get("liq_usd"))
                _append_event(ev2)
                _mark_emitted(st, "near_grad_to_pumpswap")
                new_events.append(ev2)

            # complete_to_pumpswap
            pc = st.get("pump_complete")
            if pc is not None and not _already(st, "complete_to_pumpswap"):
                dt_s = now - float(pc.get("t") or now)
                ev3 = {
                    "event": "complete_to_pumpswap",
                    "t": now,
                    "t_iso": now_iso,
                    "mint": mint,
                    "symbol": row.get("symbol"),
                    "dt_s": round(dt_s, 3),
                    "bond_pct_at_complete": pc.get("bonding_progress_pct"),
                    "liq_usd": snap.get("liq_usd"),
                    "vol_5m": snap.get("vol_5m"),
                    "age_min": snap.get("age_min"),
                    "price_usd": snap.get("price_usd"),
                }
                _append_event(ev3)
                _mark_emitted(st, "complete_to_pumpswap")
                new_events.append(ev3)

    return new_events


def process_markouts(state: dict) -> list[dict]:
    """Soft markouts for open watches (first_pumpswap set, markout_30m not yet)."""
    new_events: list[dict] = []
    now = _now_ts()
    now_iso = _now_iso()
    mints = state.get("mints") or {}

    for mint, st in list(mints.items()):
        ps = st.get("first_pumpswap")
        if not ps or ps.get("t") is None:
            continue
        if _already(st, "markout_30m"):
            continue  # fully closed watch

        first_ps_t = float(ps["t"])
        age = now - first_ps_t
        entry_px = _f(st.get("entry_price_usd") if st.get("entry_price_usd") is not None else ps.get("price_usd"))
        entry_liq = _f(st.get("entry_liq_usd") if st.get("entry_liq_usd") is not None else ps.get("liq_usd"))

        due = [name for secs, name in MARKOUT_LADDER if age >= secs and not _already(st, name)]
        if not due:
            continue

        lookup = dexscreener_token(mint)
        if lookup is None:
            # still don't emit; retry next pass (do not mark emitted)
            continue

        cur_px = lookup.get("price_usd")
        cur_liq = lookup.get("liq_usd")
        price_mult = None
        if entry_px and entry_px > 0 and cur_px is not None:
            price_mult = cur_px / entry_px
        liq_mult = None
        if entry_liq and entry_liq > 0 and cur_liq is not None:
            liq_mult = cur_liq / entry_liq
        rug_flag = bool(
            entry_liq is not None
            and entry_liq > 0
            and cur_liq is not None
            and cur_liq < 0.30 * entry_liq
        )

        for name in due:
            ev = {
                "event": name,
                "t": now,
                "t_iso": now_iso,
                "mint": mint,
                "dt_s": round(age, 3),
                "price_usd": cur_px,
                "liq_usd": cur_liq,
                "entry_price_usd": entry_px,
                "entry_liq_usd": entry_liq,
                "price_mult": round(price_mult, 6) if price_mult is not None else None,
                "liq_mult": round(liq_mult, 6) if liq_mult is not None else None,
                "rug_flag": rug_flag,
                "dex_id": lookup.get("dex_id"),
            }
            _append_event(ev)
            _mark_emitted(st, name)
            new_events.append(ev)

    return new_events


def count_open_watches(state: dict) -> int:
    n = 0
    for st in (state.get("mints") or {}).values():
        if st.get("first_pumpswap") and not _already(st, "markout_30m"):
            n += 1
    return n


def run_once() -> int:
    if not STOP.exists():
        print("STOP_LIVE_TRADING missing — refusing to run (exit 2)", file=sys.stderr)
        return 2

    if not UNIVERSE.exists():
        print(f"universe missing: {UNIVERSE}", file=sys.stderr)
        # still create empty events file for success contract
        EVENTS_PATH.touch(exist_ok=True)
        print("watches=0 new_events=0 (no universe)")
        return 1

    uni = _load_json(UNIVERSE, {})
    items = uni.get("items") if isinstance(uni, dict) else None
    if not isinstance(items, list):
        print("universe_latest.json has no items[]", file=sys.stderr)
        EVENTS_PATH.touch(exist_ok=True)
        print("watches=0 new_events=0 (bad universe)")
        return 1

    state = _load_json(STATE_PATH, {"schema": "pattern_state.v1", "mints": {}})
    if "mints" not in state:
        state = {"schema": "pattern_state.v1", "mints": state if isinstance(state, dict) else {}}

    EVENTS_PATH.touch(exist_ok=True)

    new1 = process_transitions(items, state)
    new2 = process_markouts(state)
    new_events = new1 + new2

    state["updated_at"] = _now_iso()
    _save_json(STATE_PATH, state)

    watches = count_open_watches(state)
    print(f"watches={watches} new_events={len(new_events)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Dry near-grad→PumpSwap observation logger")
    ap.add_argument("--once", action="store_true", help="Single observation pass")
    args = ap.parse_args()
    if not args.once:
        ap.error("only --once is supported (observation loop is driven externally)")
    return run_once()


if __name__ == "__main__":
    sys.exit(main())
