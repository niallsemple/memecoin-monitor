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

Usage: python3 base4_paper.py [variant]     # variant: '' (control) | 'gp'
"""
import json, os, sys, time

MON = os.path.dirname(os.path.abspath(__file__))
VARIANT = sys.argv[1] if len(sys.argv) > 1 else ''
_SUF = f'_{VARIANT}' if VARIANT else ''
FLOW = os.path.join(MON, "base4_flow.jsonl")
TRADES = os.path.join(MON, f"base4_paper_trades{_SUF}.jsonl")
STATE = os.path.join(MON, f"base4_paper_state{_SUF}.json")
GP_CACHE = os.path.join(MON, "base4_goplus_cache.json")
GATE_LOG = os.path.join(MON, "base4_gate_log.jsonl")

GP_MIN_HOLDERS = 200      # 'gp' variant: GoPlus crowd gate (chain 8453)
CROWD_MIN_HOLDERS = 50    # 'crowd' variant: self-hosted Transfer-recipient gate

_birth_blocks = {}

def _birth_block(pid):
    if not _birth_blocks:
        try:
            for l in open(os.path.join(MON, "base4_pools.jsonl")):
                d = json.loads(l)
                if d.get("pool_id") and d.get("block"):
                    _birth_blocks[d["pool_id"]] = d["block"]
        except Exception:
            pass
    return _birth_blocks.get(pid, 0)


def goplus_check(token):
    """GoPlus token_security snapshot on Base (8453). Free, no key."""
    import urllib.request
    if not token:
        return {}
    url = ('https://api.gopluslabs.io/api/v1/token_security/8453'
           f'?contract_addresses={token}')
    req = urllib.request.Request(url, headers={'User-Agent': 'darwin-labs/1.0'})
    with urllib.request.urlopen(req, timeout=20) as r:
        q = json.load(r)
    res = (q.get('result') or {}).get(token.lower()) or {}
    if not res:
        return {}
    return {'gp_holders': res.get('holder_count'),
            'gp_honeypot': res.get('is_honeypot'),
            'gp_open_source': res.get('is_open_source')}


def goplus_cached(token, row_t=None):
    """Cache-first snapshot keyed by base TOKEN. Historical rows (>6h old)
    never fetch — cache miss = {} = conservative reject."""
    try:
        cache = json.load(open(GP_CACHE))
    except Exception:
        cache = {}
    if token in cache:
        return cache[token]
    if row_t is not None and (time.time() - row_t) > 6 * 3600:
        return {}
    try:
        gp = goplus_check(token)
    except Exception:
        gp = {}
    if gp:
        gp = dict(gp); gp['t'] = row_t or time.time(); gp['src'] = 'live'
        try:
            cache[token] = gp
            json.dump(cache, open(GP_CACHE, 'w'), indent=1)
        except Exception:
            pass
    return gp

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
        if p.get("updated") is False and age_min >= ABORT_MIN:
            # never saw a post-entry swap: no observable exit liquidity.
            # Book at last price but tag 'illiquid' so stats can split
            # genuine resolution from optimistic flat closes.
            reason = "illiquid"
        elif age_min >= ABORT_MIN and m < ABORT_MULT:
            reason = "abort"
        if age_min >= TIMESTOP_MIN and reason is None:
            reason = "tstop"
        if reason:
            _close(st, trades_f, pid, p, m, reason, now)

    # ---- process new rows in time order
    for r in sorted(rows, key=lambda x: x["t"]):
        pid = r.get("pool_id")
        if not pid:
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
            if sqrt and sqrt != p["last_sqrt"]:
                p["updated"] = True
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

        if pid in st["entered"]:
            continue                 # closed trade: ignore late rows

        # watch / trigger logic
        base = (r.get("base") or "").lower()
        if base in ("", "0x" + "0" * 40):
            continue                 # native-ETH base = not a meme launch
        w = st["watch"].get(pid)
        if w is None:
            if r.get("age_h", 0) > MAX_POOL_AGE_H:
                continue
            st["watch"][pid] = {"t0": r["t"], "cum": 0.0, "name": name,
                                "base": base}
            w = st["watch"][pid]
        if w.get("armed"):
            # fill at THIS row's price (next-poll fill)
            st["open"][pid] = {
                "entry_t": r["t"], "entry_sqrt": sqrt, "last_sqrt": sqrt,
                "peak": 1.0, "freerolled": False, "banked": 0.0,
                "updated": False,
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
            if VARIANT == 'gp':
                # GoPlus crowd gate (chain 8453): the BSC-decisive split —
                # winners had 1000+ holders, supply dumps had 28/30.
                gp = goplus_cached(r.get("base"), r["t"])
                nh = int(gp.get('gp_holders') or 0)
                hp = str(gp.get('gp_honeypot') or '').lower()
                if nh < GP_MIN_HOLDERS or hp in ('1', 'true'):
                    with open(GATE_LOG, 'a') as gf:
                        gf.write(json.dumps({
                            't': r['t'], 'pool_id': pid,
                            'base': r.get('base'), 'name': name,
                            'cum_usd': round(w['cum'], 1),
                            'gp_holders': nh, 'gp_honeypot': hp,
                            'gp_src': gp.get('src', 'miss'),
                            'variant': VARIANT, 'gate_reject': True}) + '\n')
                    print(f'GP_REJECT {name} holders={nh} hp={hp}')
                    st["entered"].append(pid)      # one shot per pool
                    st["watch"].pop(pid, None)
                    continue
            if VARIANT == 'crowd':
                # Self-hosted crowd gate: unique Transfer recipients of the
                # base token, birth -> now. Live-only (forward) variant:
                # historical rows reject conservatively; the offline
                # base4_crowd.jsonl study covers the backfill comparison.
                # Backfill read: holders<50 = farm spam (35/65, mean 0.999x,
                # 3% green) — kill them; winners sat at 99-319.
                nh = -1
                if time.time() - r["t"] <= 6 * 3600:
                    try:
                        import base4_crowd
                        birth = _birth_block(pid)
                        tip = int(base4_crowd.rpc("eth_blockNumber", []), 16)
                        nh = base4_crowd.holders_of(base, birth, tip)
                    except Exception:
                        nh = -1
                if nh < CROWD_MIN_HOLDERS:
                    with open(GATE_LOG, 'a') as gf:
                        gf.write(json.dumps({
                            't': r['t'], 'pool_id': pid, 'base': base,
                            'name': name, 'cum_usd': round(w['cum'], 1),
                            'crowd_holders': nh, 'variant': VARIANT,
                            'gate_reject': True}) + '\n')
                    print(f'CROWD_REJECT {name} holders={nh}')
                    st["entered"].append(pid)
                    st["watch"].pop(pid, None)
                    continue
            w["armed"] = True              # fill on next row

    # stale watches die
    for pid, w in list(st["watch"].items()):
        if not w.get("armed") and now - w["t0"] > ENTRY_WIN_MIN * 60:
            st["watch"].pop(pid, None)

    trades_f.close()
    json.dump(st, open(STATE, "w"))
    print(f'base4 paper [{VARIANT or "control"}]: {len(st["entered"])} entered, '
          f'{len(st["open"])} open, '
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
