#!/usr/bin/env python3
"""
base4_paper.py — paper scorer for Base V4 meme launches.

Reads base4_flow.jsonl (per-scan net quote inflow + sqrtPriceX96 per pool),
applies the proven BSC trigger: cumulative net quote inflow >= ENTRY_USD
within ENTRY_WIN_MIN of first observed activity, fill at the NEXT row's
price (next-poll realism), v2 exit stack:
  free-roll 75% @1.5x | abort <1.15x after 30m | trail 50% of peak |
  time-stop 120m. Price multiples come from (sqrt/entry_sqrt)^2 — exact,
  decimal-free. USD needed only for entry flow.

V4 LP is NFT-based (no ERC-20 LP token to pull) so the LP-pull rug class
is structurally absent; supply dumps surface as price collapse and are
caught by trail/abort.

Ungated control first — measures raw V4 EV. Gate variants (GoPlus crowd
check on chain 8453) layer on later.

Usage: python3 base4_paper.py
"""
import json, os, time

MON = os.path.dirname(os.path.abspath(__file__))
FLOW = os.path.join(MON, "base4_flow.jsonl")
TRADES = os.path.join(MON, "base4_paper_trades.jsonl")
STATE = os.path.join(MON, "base4_paper_state.json")

ENTRY_USD = 3000.0
ENTRY_WIN_MIN = 30
FREEROLL_MULT = 1.5
FREEROLL_PCT = 0.75
ABORT_MULT = 1.15
ABORT_MIN = 30
TRAIL_PCT = 0.50
TIMESTOP_MIN = 120
MAX_POOL_AGE_H = 26

_eth_px = {"t": 0, "px": None}


def eth_usd():
    if time.time() - _eth_px["t"] < 300 and _eth_px["px"]:
        return _eth_px["px"]
    px = None
    try:
        import evm_watcher
        evm_watcher.CFG = evm_watcher.CHAINS["base"]
        px = evm_watcher.native_usd()
    except Exception:
        pass
    if px:
        _eth_px.update(t=time.time(), px=px)
    return px


def quote_usd(quote_sym):
    if quote_sym in ("USDC",):
        return 1.0
    if quote_sym in ("ETH", "WETH"):
        return eth_usd()
    return None          # custom quote token: skip USD conversion


def qdec(quote_sym):
    return 6 if quote_sym == "USDC" else 18


def mult(sqrt, entry_sqrt):
    if not sqrt or not entry_sqrt:
        return 0.0
    return (sqrt / entry_sqrt) ** 2


def main():
    st = {"offset": 0, "watch": {}, "open": {}, "entered": []}
    if os.path.exists(STATE):
        try:
            st = json.load(open(STATE))
        except Exception:
            pass
    if not os.path.exists(FLOW):
        print("no base4 flow file yet")
        return
    size = os.path.getsize(FLOW)
    if size < st["offset"]:
        st["offset"] = 0
    rows = []
    with open(FLOW) as f:
        f.seek(st["offset"])
        for l in f:
            try:
                rows.append(json.loads(l))
            except Exception:
                pass
        st["offset"] = f.tell()
    now = time.time()

    trades_f = open(TRADES, "a")

    # ---- heartbeat close for quiet pools (no new rows): evaluate open
    # positions at last observed price against wall clock
    for pid, p in list(st["open"].items()):
        m = mult(p["last_sqrt"], p["entry_sqrt"])
        age_min = (now - p["entry_t"]) / 60
        reason = None
        if age_min >= ABORT_MIN and m < ABORT_MULT:
            reason = "abort"
        if age_min >= TIMESTOP_MIN:
            reason = "tstop"
        if reason:
            _close(st, trades_f, pid, p, m, reason, now)

    # ---- process new rows in time order
    for r in sorted(rows, key=lambda x: x["t"]):
        pid = r.get("pool_id")
        if not pid or pid in st["entered"]:
            continue
        qs = r.get("quote_sym")
        qu = quote_usd(qs)
        if qu is None:
            continue                       # unknown quote token
        flow_usd = r["net_quote_raw"] / 10 ** qdec(qs) * qu
        sqrt = r.get("sqrt_price_x96") or 0
        name = f"{r.get('base_sym') or pid[:8]} / {qs}"

        # manage open position first
        if pid in st["open"]:
            p = st["open"][pid]
            p["last_sqrt"] = sqrt or p["last_sqrt"]
            m = mult(p["last_sqrt"], p["entry_sqrt"])
            p["peak"] = max(p["peak"], m)
            age_min = (r["t"] - p["entry_t"]) / 60
            if not p["freerolled"] and m >= FREEROLL_MULT:
                p["freerolled"] = True
                p["banked"] = FREEROLL_PCT * FREEROLL_MULT
                print(f"FREEROLL {name} @{m:.2f}x")
            reason = None
            ret = None
            if p["freerolled"] and m <= p["peak"] * TRAIL_PCT:
                reason, ret = "trail", p["banked"] + (1 - FREEROLL_PCT) * m
            elif age_min >= ABORT_MIN and m < ABORT_MULT:
                reason, ret = "abort", m
            elif age_min >= TIMESTOP_MIN:
                reason, ret = "tstop", (p["banked"] + (1 - FREEROLL_PCT) * m
                                        if p["freerolled"] else m)
            if reason:
                _close(st, trades_f, pid, p, m, reason, r["t"], ret=ret)
            continue

        # watch / trigger logic
        w = st["watch"].get(pid)
        if w is None:
            if r.get("age_h", 0) > MAX_POOL_AGE_H:
                continue
            st["watch"][pid] = {"t0": r["t"], "cum": 0.0, "name": name}
            w = st["watch"][pid]
        if w.get("armed"):
            # fill at THIS row's price (next-poll fill)
            st["open"][pid] = {
                "entry_t": r["t"], "entry_sqrt": sqrt, "last_sqrt": sqrt,
                "peak": 1.0, "freerolled": False, "banked": 0.0,
                "name": name, "entry_flow_usd": round(w["cum"], 1),
            }
            st["entered"].append(pid)
            st["watch"].pop(pid, None)
            print(f'ENTRY {name} cum_flow=${w["cum"]:,.0f} (next-poll fill)')
            continue
        if r["t"] - w["t0"] > ENTRY_WIN_MIN * 60:
            st["watch"].pop(pid, None)
            continue
        w["cum"] += flow_usd
        if w["cum"] >= ENTRY_USD and sqrt:
            w["armed"] = True              # fill on next row

    # stale watches die
    for pid, w in list(st["watch"].items()):
        if not w.get("armed") and now - w["t0"] > ENTRY_WIN_MIN * 60:
            st["watch"].pop(pid, None)

    trades_f.close()
    json.dump(st, open(STATE, "w"))
    print(f'base4 paper: {len(st["entered"])} entered, {len(st["open"])} open, '
          f'{len(st["watch"])} watching, {len(rows)} rows consumed')


def _close(st, trades_f, pid, p, m, reason, t, ret=None):
    if ret is None:
        ret = m
    rec = {"name": p["name"], "pool_id": pid, "entry_t": p["entry_t"],
           "exit_t": t, "ret": round(ret, 4), "exit": reason,
           "entry_flow_usd": p.get("entry_flow_usd"),
           "hold_min": round((t - p["entry_t"]) / 60, 1)}
    trades_f.write(json.dumps(rec) + "\n")
    trades_f.flush()
    st["open"].pop(pid, None)
    print(f'EXIT  {p["name"]} ret={ret:.3f}x ({reason}, {rec["hold_min"]}m)')


if __name__ == "__main__":
    main()
