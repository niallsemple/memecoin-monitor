"""MFG tracker (§56+§56b): capture manufactured launches birth → graduation
→ post-graduation runner/husk.

Runs as the curve-collector automation (~19-min window, every 20 min).

Data path (all verified live 2026-08-29):
- ws1 PumpPortal: subscribeNewToken + subscribeMigration (births/graduations,
  logged raw to curves.jsonl).
- ws2 Helius accountSubscribe. PumpPortal subscribeTokenTrade is PAYWALLED —
  do not use. Two account kinds per token:
  1. PRE-GRAD: bonding-curve account (from create event's bondingCurveKey).
     151 bytes: virtualTokenReserves u64 @8, virtualSolReserves u64 @16,
     complete bool @48, creator 32B @49. vSol delta = buy/sell flow;
     mcap = vSol_lamports * 1e6 / vTok_raw.
  2. POST-GRAD: PumpSwap pool token accounts. Pool discovered via
     getProgramAccounts on AMM pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA
     with memcmp offset 43 = mint (layout: bump@8, index@9, creator@11,
     baseMint@43, quoteMint@75, lpMint@107, poolBaseTA@139, poolQuoteTA@171,
     lpSupply u64 @203). Both token accounts subscribed; SPL amount u64 @64.
     Quote (WSOL) delta = buy(+)/sell(-) flow; pool mcap = q_lamports*1e6/b_raw.
     (The curve account FREEZES at graduation — post-grad runner/husk is only
     measurable on the pool. That was the §56b blind spot.)

LOST vs the paywalled trade feed (honest limits): trader identity (no unique
buyers, no dev-sell flags) — flow is aggregate only. Slot batching can merge
several trades into one notification (accepted approximation).

Snapshots to mfg_tokens.jsonl at +5m/+15m/+60m (all tokens) and +4h/+12h/+24h
(graduated tokens, pool fields); derived trades to mfg_trades.jsonl;
state in mfg_state.json (survives the 1-min inter-run gap).
"""
import base64
import json
import struct
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

MON = Path("/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor")
CURVES = MON / "curves.jsonl"
TRADES = MON / "mfg_trades.jsonl"
SNAPS = MON / "mfg_tokens.jsonl"
STATE = MON / "mfg_state.json"
KEYFILE = MON / "helius_key.txt"
PUMP_WSS = "wss://pumpportal.fun/data-api/real-time"
WINDOW_S = 19 * 60
SEED_MIN = 5.0
MAX_TRACK = 60                          # concurrent curve subscriptions
MAX_POOL_TRACK = 30                     # graduated tokens pool-tracked (2 subs each)
POOL_QUIET_S = 2 * 3600                 # §56g: recycle pool slots after 2h silence
SNAP_AGES = (300, 900, 3600)            # +5m, +15m, +60m
GRAD_SNAP_AGES = (14400, 43200, 86400)  # +4h, +12h, +24h (graduated only)
TRACK_MAX_AGE = 3600                    # unsubscribe curve after 1h
AMM_PROG = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
WSOL = "So11111111111111111111111111111111111111112"
ALERTS = MON / "mfg_alerts.jsonl"
ALERT_LIQ_MIN = 100.0     # SOL of quote liquidity = deep-pool campaign
ALERT_FLOW_MIN = 3.0      # pool buy/sell SOL ratio
ALERT_BUY_MIN = 20.0      # SOL of pool buy volume (activity floor)
ALERT_BUYS_MIN = 30       # trade-count floor (kicks dust noise out)
ALERT_MAX_AGE = 4 * 3600  # only fresh campaigns ping

# §56e free-roll paper-trader (paper only — no real orders)
PAPER = MON / "mfg_paper_trades.jsonl"
P_TARGET, P_SELL = 1.5, 0.75    # free-roll: sell 75% at 1.5x entry
P_TRAIL = 0.5                   # trailing stop: exit below 50% of post-entry peak
P_TS_MIN = 120                  # time-stop: dump unpumped campaign after 120 min
P_NET_MIN, P_NB_MIN, P_FLOW_MIN = 25.0, 10, 2.0   # E25 early entry trigger


def paper_score():
    """Replay pool trades with the §56e exit stack; write mfg_paper_trades.jsonl.
    Fully self-contained and fail-safe: returns {} on any error."""
    import collections
    tr = collections.defaultdict(list)
    try:
        with TRADES.open() as f:
            for line in f:
                try:
                    x = json.loads(line)
                except Exception:
                    continue
                if (x.get("venue") != "pool" or not x.get("t")
                        or not x.get("mcap_sol")):
                    continue
                tr[x["mint"]].append(x)
    except Exception:
        return {}
    positions = []
    for m, xs in tr.items():
        if len(xs) < 50:
            continue
        xs.sort(key=lambda x: x["t"])
        nb = ns = 0
        bs = ss = 0.0
        ti = None
        for i, x in enumerate(xs):
            if x.get("side") == "buy":
                nb += 1
                bs += x.get("sol") or 0
            else:
                ns += 1
                ss += x.get("sol") or 0
            if ((bs - ss) >= P_NET_MIN and nb >= P_NB_MIN
                    and nb / max(ns, 1) >= P_FLOW_MIN):
                ti = i
                break
        if ti is None:
            continue
        emc = xs[ti]["mcap_sol"]
        t0 = xs[ti]["t"]
        if emc <= 0:
            continue
        proceeds = 0.0
        pos = 1.0
        peak = 1.0
        fr = False
        reason = None
        for x in xs[ti + 1:]:
            r = x["mcap_sol"] / emc
            peak = max(peak, r)
            if not fr and r >= P_TARGET:
                proceeds += P_SELL * P_TARGET
                pos -= P_SELL
                fr = True
            if r <= P_TRAIL * peak and pos > 0:
                proceeds += pos * r
                pos = 0
                reason = "trail"
                break
            if not fr and (x["t"] - t0) / 60 >= P_TS_MIN:
                proceeds += pos * r
                pos = 0
                reason = "timestop"
                break
        if pos > 0:
            total = proceeds + pos * (xs[-1]["mcap_sol"] / emc)
            status = "open"
        else:
            total = proceeds
            status = "closed"
        positions.append({"mint": m, "entry_t": t0, "entry_mcap": emc,
                          "freerolled": fr, "peak": round(peak, 3),
                          "status": status, "exit_reason": reason,
                          "ret": round(total - 1, 4),
                          "last_t": xs[-1]["t"], "n_trades": len(xs)})
    try:
        with PAPER.open("w") as f:
            for r in positions:
                f.write(json.dumps(r) + "\n")
    except Exception:
        pass
    closed = [r["ret"] for r in positions if r["status"] == "closed"]
    return {"paper_positions": len(positions),
            "paper_closed": len(closed),
            "paper_open": len(positions) - len(closed),
            "paper_exp": round(sum(closed) / len(closed), 4) if closed else None,
            "paper_wins": sum(1 for v in closed if v > 0)}


def _load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:
            pass
    return {}


def _save_state(tokens):
    now = time.time()
    keep = {}
    for m, t in tokens.items():
        done = len(set(t["snapped"]) & set(SNAP_AGES)) >= len(SNAP_AGES) and (
            not t.get("grad_ts")
            or len(set(t["snapped"]) & set(GRAD_SNAP_AGES)) >= len(GRAD_SNAP_AGES))
        if now - t["birth_ts"] < 26 * 3600 or not done:
            keep[m] = t
    STATE.write_text(json.dumps(keep))
    return keep


def _decode_curve(b64):
    """Return (vTok_raw, vSol_lamports, complete) or None."""
    try:
        raw = base64.b64decode(b64)
        if len(raw) < 49:
            return None
        vtok, vsol = struct.unpack("<QQ", raw[8:24])
        return vtok, vsol, raw[48] != 0
    except Exception:
        return None


def _decode_spl_amount(b64):
    """SPL token account: amount u64 @64. Return raw amount or None."""
    try:
        raw = base64.b64decode(b64)
        if len(raw) < 72:
            return None
        return struct.unpack("<Q", raw[64:72])[0]
    except Exception:
        return None


def _b58e(b):
    al = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = int.from_bytes(b, "big")
    s = ""
    while n:
        n, m = divmod(n, 58)
        s = al[m] + s
    return "1" * (len(b) - len(b.lstrip(b"\x00"))) + s


def run(ctx):
    import websocket
    helius_key = KEYFILE.read_text().strip()
    helius_wss = f"wss://mainnet.helius-rpc.com/?api-key={helius_key}"
    helius_rpc = f"https://mainnet.helius-rpc.com/?api-key={helius_key}"

    def rpc(method, params):
        req = urllib.request.Request(
            helius_rpc,
            data=json.dumps({"jsonrpc": "2.0", "id": 1,
                             "method": method, "params": params}).encode(),
            headers={"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=20).read())

    def discover_pool(mint):
        """Return {'pool','pbt','pqt'} for the mint's WSOL pool, else None."""
        try:
            r = rpc("getProgramAccounts", [AMM_PROG, {
                "encoding": "base64",
                "filters": [{"memcmp": {"offset": 43, "bytes": mint}}]}])
            for a in r.get("result") or []:
                raw = base64.b64decode(a["account"]["data"][0])
                if len(raw) < 203 or _b58e(raw[75:107]) != WSOL:
                    continue
                return {"pool": a["pubkey"],
                        "pbt": _b58e(raw[139:171]),
                        "pqt": _b58e(raw[171:203])}
        except Exception:
            pass
        return None

    def _liq_update(t):
        if t.get("pool_last_q") is None:
            return
        liq = round(t["pool_last_q"] / 1e9, 4)
        t["pool_liq_sol"] = liq
        t["pool_liq_min"] = liq if t.get("pool_liq_min") is None else min(t["pool_liq_min"], liq)
        t["pool_liq_max"] = liq if t.get("pool_liq_max") is None else max(t["pool_liq_max"], liq)

    now0 = time.time()
    deadline = now0 + WINDOW_S
    tokens = _load_state()
    # migrate legacy state entries forward
    for t in tokens.values():
        t.setdefault("curve", None)
        t.setdefault("notifs", 0)
        t.setdefault("last_vsol", None)
        t.setdefault("last_mcap_sol", None)
        t.setdefault("snapped", [])
        t.setdefault("pool", None)          # {'pool','pbt','pqt'} once found
        t.setdefault("pool_try_ts", 0)      # last discovery attempt
        t.setdefault("pool_buys", 0)
        t.setdefault("pool_sells", 0)
        t.setdefault("pool_buy_sol", 0.0)
        t.setdefault("pool_sell_sol", 0.0)
        t.setdefault("pool_notifs", 0)
        t.setdefault("pool_last_q", None)   # quote (WSOL) lamports
        t.setdefault("pool_last_b", None)   # base raw units
        t.setdefault("pool_mcap", None)
        t.setdefault("pool_liq_sol", None)  # quote balance in SOL (pool depth)
        t.setdefault("pool_liq_min", None)  # drain detection: min/max since grad
        t.setdefault("pool_liq_max", None)
    stats = {"births": 0, "big_seeds": 0, "new_tracks": 0, "trades": 0,
             "migrations": 0, "complete_flags": 0, "snaps": 0,
             "curve_subs": 0, "helius_err": 0, "unsubs": 0,
             "pools_found": 0, "pool_subs": 0, "pool_trades": 0, "alerts": 0}
    alerted = set()
    if ALERTS.exists():
        for line in ALERTS.read_text().splitlines():
            try:
                alerted.add(json.loads(line)["mint"])
            except Exception:
                pass
    LK = threading.Lock()
    stop = threading.Event()

    # ---- Helius subscription bookkeeping ----
    hws_ref = {"ws": None, "open": False}
    req_seq = {"n": 0}
    pending = {}          # req_id -> (mint, kind, address)
    subs = {}             # sub_id -> (mint, kind)
    mint_sub = {}         # mint -> {kind: sub_id}
    sub_queue = []        # (mint, kind, address, rid) waiting for ws open

    def helius_send(obj):
        ws = hws_ref["ws"]
        if ws and hws_ref["open"]:
            try:
                ws.send(json.dumps(obj))
                return True
            except Exception:
                return False
        return False

    def subscribe_account(mint, kind, address):
        if not address:
            return
        with LK:
            if kind in mint_sub.get(mint, {}):
                return
            req_seq["n"] += 1
            rid = req_seq["n"]
            pending[rid] = (mint, kind, address)
        req = {"jsonrpc": "2.0", "id": rid, "method": "accountSubscribe",
               "params": [address, {"encoding": "base64",
                                    "commitment": "processed"}]}
        if not helius_send(req):
            with LK:
                sub_queue.append((mint, kind, address, rid))

    def unsubscribe_mint(mint, kinds=("curve", "pool_q", "pool_b")):
        with LK:
            entry = mint_sub.get(mint, {})
            sids = [(k, entry.pop(k, None)) for k in kinds]
            if not entry:
                mint_sub.pop(mint, None)
            for k, sid in sids:
                if sid is not None:
                    subs.pop(sid, None)
        for k, sid in sids:
            if sid is not None:
                req_seq["n"] += 1
                helius_send({"jsonrpc": "2.0", "id": req_seq["n"],
                             "method": "accountUnsubscribe", "params": [sid]})
                stats["unsubs"] += 1

    # ---- token bookkeeping ----
    def new_token(mint, d):
        tokens[mint] = {
            "birth_ts": d.get("_ts") or time.time(),
            "seed": d.get("solAmount") or 0,
            "creator": d.get("traderPublicKey"),
            "name": d.get("name"), "symbol": d.get("symbol"),
            "curve": d.get("bondingCurveKey"),
            "mcap_birth_sol": d.get("marketCapSol"),
            "grad_ts": None, "buys": 0, "sells": 0,
            "buy_sol": 0.0, "sell_sol": 0.0, "notifs": 0,
            "last_vsol": None, "last_mcap_sol": None, "snapped": [],
            "pool": None, "pool_try_ts": 0,
            "pool_buys": 0, "pool_sells": 0,
            "pool_buy_sol": 0.0, "pool_sell_sol": 0.0, "pool_notifs": 0,
            "pool_last_q": None, "pool_last_b": None, "pool_mcap": None,
            "pool_liq_sol": None, "pool_liq_min": None, "pool_liq_max": None,
        }

    def subscribe_pool(mint, t):
        p = t.get("pool")
        if p:
            subscribe_account(mint, "pool_q", p["pqt"])
            subscribe_account(mint, "pool_b", p["pbt"])

    # ---- Helius ws thread ----
    def helius_on_open(ws):
        hws_ref["open"] = True
        with LK:
            queued = list(sub_queue)
            sub_queue.clear()
            warm_c = [(m, t["curve"]) for m, t in tokens.items()
                      if t.get("curve") and "curve" not in mint_sub.get(m, {})
                      and time.time() - t["birth_ts"] < TRACK_MAX_AGE]
            warm_p = [(m, t) for m, t in tokens.items()
                      if t.get("pool") and not t.get("pool_done")
                      and time.time() - t["birth_ts"] < 26 * 3600]
        for mint, kind, address, rid in queued:
            helius_send({"jsonrpc": "2.0", "id": rid, "method": "accountSubscribe",
                         "params": [address, {"encoding": "base64",
                                              "commitment": "processed"}]})
        for mint, curve in warm_c[:MAX_TRACK]:
            subscribe_account(mint, "curve", curve)
        for mint, t in warm_p[:MAX_POOL_TRACK]:
            subscribe_pool(mint, t)

    def helius_on_message(ws, msg):
        try:
            d = json.loads(msg)
        except Exception:
            return
        if "error" in d:
            stats["helius_err"] += 1
            with LK:
                pending.pop(d.get("id"), None)
            return
        rid = d.get("id")
        if rid is not None and "result" in d:
            with LK:
                got = pending.pop(rid, None)
                if got:
                    mint, kind, _addr = got
                    subs[d["result"]] = (mint, kind)
                    mint_sub.setdefault(mint, {})[kind] = d["result"]
                    stats["curve_subs" if kind == "curve" else "pool_subs"] += 1
            return
        if d.get("method") != "accountNotification":
            return
        try:
            sid = d["params"]["subscription"]
            val = d["params"]["result"]["value"]
            data = val.get("data")
            b64 = data[0] if isinstance(data, list) else data
        except Exception:
            return
        with LK:
            got = subs.get(sid)
            if not got or got[0] not in tokens:
                return
            mint, kind = got
            t = tokens[mint]
            now = time.time()

            if kind == "curve":
                dec = _decode_curve(b64)
                if dec is None:
                    return
                vtok, vsol, complete = dec
                t["notifs"] += 1
                if vtok:
                    t["last_mcap_sol"] = round(vsol * 1e6 / vtok, 4)
                if complete and not t["grad_ts"]:
                    t["grad_ts"] = now
                    stats["complete_flags"] += 1
                if t["last_vsol"] is None:
                    t["last_vsol"] = vsol
                    return
                dv = vsol - t["last_vsol"]
                t["last_vsol"] = vsol
                if dv == 0:
                    return
                sol = abs(dv) / 1e9
                side = "buy" if dv > 0 else "sell"
                if dv > 0:
                    t["buys"] += 1
                    t["buy_sol"] += sol
                else:
                    t["sells"] += 1
                    t["sell_sol"] += sol
                stats["trades"] += 1
                rec = {"t": now, "mint": mint, "venue": "curve", "side": side,
                       "sol": round(sol, 6), "mcap_sol": t["last_mcap_sol"]}

            else:  # pool token accounts (SPL amount @64)
                amt = _decode_spl_amount(b64)
                if amt is None:
                    return
                t["pool_notifs"] += 1
                t["pool_last_ts"] = now
                if kind == "pool_b":
                    t["pool_last_b"] = amt
                else:
                    prev = t["pool_last_q"]
                    t["pool_last_q"] = amt
                    _liq_update(t)
                if t["pool_last_b"] and t["pool_last_q"] is not None:
                    t["pool_mcap"] = round(t["pool_last_q"] * 1e6
                                           / t["pool_last_b"], 4)
                if kind == "pool_b" or prev is None:
                    return  # trades counted on quote (WSOL) leg only
                dv = amt - prev
                if dv == 0:
                    return
                sol = abs(dv) / 1e9
                side = "buy" if dv > 0 else "sell"  # WSOL in = buy, out = sell
                if dv > 0:
                    t["pool_buys"] += 1
                    t["pool_buy_sol"] += sol
                else:
                    t["pool_sells"] += 1
                    t["pool_sell_sol"] += sol
                stats["pool_trades"] += 1
                rec = {"t": now, "mint": mint, "venue": "pool", "side": side,
                       "sol": round(sol, 6), "mcap_sol": t["pool_mcap"]}
        with TRADES.open("a") as f:
            f.write(json.dumps(rec) + "\n")

    def helius_loop():
        while not stop.is_set():
            ws = websocket.WebSocketApp(
                helius_wss, on_open=helius_on_open,
                on_message=helius_on_message,
                on_error=lambda w, e: None,
                on_close=lambda w, *a: hws_ref.update(open=False))
            hws_ref["ws"] = ws
            try:
                ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception:
                pass
            hws_ref["open"] = False
            if not stop.is_set():
                time.sleep(3)

    # ---- PumpPortal ws (births + migrations) ----
    def pump_on_message(ws, msg):
        try:
            d = json.loads(msg)
        except Exception:
            return
        if not isinstance(d, dict):
            return
        d["_ts"] = time.time()
        tt = d.get("txType") or ""
        mint = d.get("mint")
        if tt == "create":
            stats["births"] += 1
            with CURVES.open("a") as f:
                f.write(json.dumps(d) + "\n")
            seed = d.get("solAmount") or 0
            if seed >= SEED_MIN and mint:
                with LK:
                    fresh = mint not in tokens
                    n_open = sum(1 for t in tokens.values()
                                 if time.time() - t["birth_ts"] < TRACK_MAX_AGE)
                    if fresh and n_open < MAX_TRACK:
                        new_token(mint, d)
                        stats["big_seeds"] += 1
                        stats["new_tracks"] += 1
                        curve = d.get("bondingCurveKey")
                    else:
                        curve = None
                if curve:
                    subscribe_account(mint, "curve", curve)
        elif tt == "migrate":
            stats["migrations"] += 1
            with CURVES.open("a") as f:
                f.write(json.dumps(d) + "\n")
            with LK:
                if mint in tokens and not tokens[mint]["grad_ts"]:
                    tokens[mint]["grad_ts"] = d["_ts"]
        if time.time() > deadline:
            try:
                ws.close()
            except Exception:
                pass

    def pump_on_open(ws):
        ws.send(json.dumps({"method": "subscribeNewToken"}))
        ws.send(json.dumps({"method": "subscribeMigration"}))

    # ---- snapshot / pool-discovery / unsubscriber thread ----
    def snapshot_loop():
        while not stop.is_set():
            now = time.time()
            # 1) pool discovery for freshly graduated tokens (HTTP, ~1s)
            with LK:
                need = [(m, t) for m, t in tokens.items()
                        if t.get("grad_ts") and not t.get("pool")
                        and now - t.get("pool_try_ts", 0) > 60
                        and now - t["birth_ts"] < 26 * 3600]
            n_pool_tracked = sum(1 for t in tokens.values()
                                 if t.get("pool") and not t.get("pool_done"))
            for m, t in need[:5]:
                with LK:
                    t["pool_try_ts"] = now
                if n_pool_tracked >= MAX_POOL_TRACK:
                    break
                p = discover_pool(m)
                if p:
                    # seed baseline balances so dead pools still get an mcap
                    for k, addr in (("pool_last_b", p["pbt"]),
                                    ("pool_last_q", p["pqt"])):
                        try:
                            r2 = rpc("getAccountInfo",
                                     [addr, {"encoding": "base64"}])
                            v2 = (r2.get("result") or {}).get("value")
                            if v2:
                                amt = _decode_spl_amount(v2["data"][0])
                                with LK:
                                    t[k] = amt
                        except Exception:
                            pass
                    with LK:
                        if t.get("pool_last_b") and t.get("pool_last_q") is not None:
                            t["pool_mcap"] = round(t["pool_last_q"] * 1e6
                                                   / t["pool_last_b"], 4)
                        _liq_update(t)
                        t["pool"] = p
                        t["pool_last_ts"] = now
                        n_pool_tracked += 1
                        stats["pools_found"] += 1
                    subscribe_pool(m, t)
            # 2) snapshots
            with LK:
                items = list(tokens.items())
            for m, t in items:
                age = now - t["birth_ts"]
                ages = list(SNAP_AGES)
                if t.get("grad_ts"):
                    ages += list(GRAD_SNAP_AGES)
                for a in ages:
                    if age >= a and a not in t["snapped"]:
                        with LK:
                            t["snapped"].append(a)
                        rec = {"t": now, "mint": m, "age_s": a,
                               "seed": t["seed"], "creator": t["creator"],
                               "symbol": t["symbol"],
                               "grad": bool(t["grad_ts"]),
                               "grad_lag_s": (t["grad_ts"] - t["birth_ts"])
                               if t["grad_ts"] else None,
                               "buys": t["buys"], "sells": t["sells"],
                               "bs_ratio": round(t["buys"] / max(t["sells"], 1), 2),
                               "buy_sol": round(t["buy_sol"], 2),
                               "sell_sol": round(t["sell_sol"], 2),
                               "flow_ratio": round(t["buy_sol"]
                                                   / max(t["sell_sol"], 1e-9), 2),
                               "notifs": t["notifs"],
                               "mcap_sol": t["last_mcap_sol"],
                               "pool_found": bool(t.get("pool")),
                               "pool_buys": t["pool_buys"],
                               "pool_sells": t["pool_sells"],
                               "pool_buy_sol": round(t["pool_buy_sol"], 2),
                               "pool_sell_sol": round(t["pool_sell_sol"], 2),
                               "pool_flow_ratio": round(
                                   t["pool_buy_sol"]
                                   / max(t["pool_sell_sol"], 1e-9), 2),
                               "pool_mcap_sol": t["pool_mcap"],
                               "pool_liq_sol": t.get("pool_liq_sol"),
                               "pool_liq_min": t.get("pool_liq_min"),
                               "pool_liq_max": t.get("pool_liq_max")}
                        with SNAPS.open("a") as f:
                            f.write(json.dumps(rec) + "\n")
                        stats["snaps"] += 1
                # 2b) §56g: recycle pool slots — unsub pools quiet > 2h
                if t.get("pool") and not t.get("pool_done"):
                    last_pt = t.get("pool_last_ts")
                    if last_pt is None:
                        t["pool_last_ts"] = now  # 2h grace for legacy state
                    elif now - last_pt > POOL_QUIET_S:
                        unsubscribe_mint(m, kinds=("pool_q", "pool_b"))
                        t["pool_done"] = True
                        stats["pool_pruned"] = stats.get("pool_pruned", 0) + 1
                # 3) curve unsub only (pool subs live until token prunes)
                if age > TRACK_MAX_AGE or (t["grad_ts"] and age > 900):
                    unsubscribe_mint(m, kinds=("curve",))
                # 4) runner alert: deep pool + buy-dominant flow on a fresh grad
                if (m not in alerted and t.get("grad_ts") and t.get("pool")
                        and age <= ALERT_MAX_AGE
                        and (t.get("pool_liq_sol") or 0) >= ALERT_LIQ_MIN
                        and t["pool_buy_sol"] >= ALERT_BUY_MIN
                        and t["pool_buys"] >= ALERT_BUYS_MIN
                        and (t["pool_buy_sol"] / max(t["pool_sell_sol"], 1e-9))
                            >= ALERT_FLOW_MIN):
                    alerted.add(m)
                    stats["alerts"] += 1
                    arec = {"t": now, "mint": m, "symbol": t.get("symbol"),
                            "seed": t["seed"],
                            "pool_liq_sol": t.get("pool_liq_sol"),
                            "pool_flow_ratio": round(
                                t["pool_buy_sol"]
                                / max(t["pool_sell_sol"], 1e-9), 2),
                            "pool_buy_sol": round(t["pool_buy_sol"], 1),
                            "pool_buys": t["pool_buys"],
                            "pool_sells": t["pool_sells"],
                            "pool_mcap": t.get("pool_mcap")}
                    with ALERTS.open("a") as f:
                        f.write(json.dumps(arec) + "\n")
                    try:
                        subprocess.run(
                            ["osascript", "-e",
                             f'display notification "liq {arec["pool_liq_sol"]} SOL · '
                             f'flow {arec["pool_flow_ratio"]} · '
                             f'buys {arec["pool_buys"]}" '
                             f'with title "MFG RUNNER: {arec["symbol"] or m[:8]}"'],
                            capture_output=True, timeout=10)
                    except Exception:
                        pass
            stop.wait(10)

    def killer():
        time.sleep(WINDOW_S + 30)
        stop.set()
        for ref in (hws_ref["ws"], pump_ref["ws"]):
            try:
                ref.close()
            except Exception:
                pass

    pump_ref = {"ws": None}
    threading.Thread(target=killer, daemon=True).start()
    threading.Thread(target=helius_loop, daemon=True).start()
    threading.Thread(target=snapshot_loop, daemon=True).start()

    ws = websocket.WebSocketApp(PUMP_WSS, on_open=pump_on_open,
                                on_message=pump_on_message,
                                on_error=lambda w, e: None,
                                on_close=lambda w, *a: None)
    pump_ref["ws"] = ws
    ws.run_forever(ping_interval=20, ping_timeout=10)
    stop.set()

    tokens = _save_state(tokens)
    tracked = sum(1 for t in tokens.values()
                  if time.time() - t["birth_ts"] < 26 * 3600)
    # compact per-token table for the dashboard widget (most active first)
    now = time.time()
    board = []
    for m, t in tokens.items():
        age = now - t["birth_ts"]
        grad = bool(t.get("grad_ts"))
        if age > 2 * 3600 or not (t.get("notifs") or t.get("pool_notifs")):
            continue
        if grad and t.get("pool"):
            buy, sell = t["pool_buy_sol"], t["pool_sell_sol"]
            flow = (buy / sell) if sell > 0 else (99.0 if buy > 0 else 0.0)
            mcap = t.get("pool_mcap")
            buys, sells = t["pool_buys"], t["pool_sells"]
            act = t.get("pool_notifs", 0)
        else:
            buy, sell = t["buy_sol"], t["sell_sol"]
            flow = (buy / sell) if sell > 0 else (99.0 if buy > 0 else 0.0)
            mcap = t.get("last_mcap_sol")
            buys, sells = t["buys"], t["sells"]
            act = t.get("notifs", 0)
        board.append({
            "symbol": (t.get("symbol") or m[:6])[:18],
            "mint": m,
            "seed": round(t["seed"], 2),
            "age_min": round(age / 60, 1),
            "buys": buys, "sells": sells,
            "buy_sol": round(buy, 1), "sell_sol": round(sell, 1),
            "flow_ratio": round(flow, 2),
            "mcap_sol": mcap,
            "grad": grad,
            "pool": bool(t.get("pool")),
            "liq_sol": t.get("pool_liq_sol") if grad else None,
            "notifs": act,
        })
    board.sort(key=lambda r: -(r["buy_sol"] + r["sell_sol"]))
    try:
        paper = paper_score()
    except Exception:
        paper = {}
    return {"artifact": {
        "summary": (f"births={stats['births']} big_seeds={stats['big_seeds']} "
                    f"tracked={tracked} trades={stats['trades']} "
                    f"pool_trades={stats['pool_trades']} pools={stats['pools_found']} "
                    f"snaps={stats['snaps']} alerts={stats['alerts']} "
                    f"helius_err={stats['helius_err']} "
                    f"paper={paper.get('paper_positions', 0)}pos/"
                    f"{paper.get('paper_closed', 0)}closed "
                    f"exp={paper.get('paper_exp')}"),
        **stats, "tracked_open": tracked, **paper,
        "tokens": board[:12],
        "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }}
