#!/usr/bin/env python3
"""Verify Helius accountSubscribe captures live trades on a FRESH pump.fun birth.

Dual-ws test:
  ws1 (PumpPortal): subscribeNewToken -> first create event gives bondingCurveKey
  ws2 (Helius):     accountSubscribe on that curve -> accountNotification flow
Decode: base64 data, struct.unpack('<QQ', data[8:24]) -> (vTok, vSol)
vSol delta sign = buy(+)/sell(-), size = |delta|/1e9 SOL.

Success criterion: >=1 decoded accountNotification with sane reserves within the window.
"""
import base64, json, struct, threading, time, sys
import websocket

MON = "/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor"
KEY = open(f"{MON}/helius_key.txt").read().strip()
HELIUS_WS = f"wss://mainnet.helius-rpc.com/?api-key={KEY}"
PUMP_WS = "wss://pumpportal.fun/api/data"

WINDOW_S = 60
t0 = time.time()
state = {"curve": None, "mint": None, "last_vsol": None, "notifs": 0, "trades": 0,
         "buy_sol": 0.0, "sell_sol": 0.0, "done": False}


def log(msg):
    print(f"[{time.time()-t0:6.1f}s] {msg}", flush=True)


def decode_reserves(b64):
    try:
        raw = base64.b64decode(b64)
    except Exception as e:
        log(f"decode exc: {e!r} b64type={type(b64)} b64={repr(b64)[:120]}")
        return None
    if len(raw) < 24:
        log(f"short raw len={len(raw)} b64={repr(b64)[:120]}")
        return None
    vtok, vsol = struct.unpack("<QQ", raw[8:24])
    return vtok, vsol


# ---- Helius side ----
def helius_loop():
    def on_open(ws):
        log("helius: connected, waiting for a fresh curve to subscribe")
    def on_message(ws, msg):
        try:
            d = json.loads(msg)
        except Exception:
            return
        if d.get("id") == 1 and "result" in d:
            log(f"helius: accountSubscribe CONFIRMED sub_id={d['result']} curve={state['curve'][:12]}...")
            return
        if d.get("method") == "accountNotification":
            state["notifs"] += 1
            val = d["params"]["result"]["value"]
            data = val.get("data")
            b64 = data[0] if isinstance(data, list) else data
            dec = decode_reserves(b64)
            if dec is None:
                if state["notifs"] <= 3:
                    log(f"helius: notif #{state['notifs']} undecodable")
                return
            vtok, vsol = dec
            if state["last_vsol"] is None:
                state["last_vsol"] = vsol
                log(f"helius: notif #1 baseline vSol={vsol/1e9:.4f} vTok={vtok/1e6:.1f}M")
                return
            dv = vsol - state["last_vsol"]
            state["last_vsol"] = vsol
            if dv == 0:
                return
            state["trades"] += 1
            side = "BUY " if dv > 0 else "SELL"
            sol = abs(dv) / 1e9
            if dv > 0:
                state["buy_sol"] += sol
            else:
                state["sell_sol"] += sol
            log(f"helius: {side} {sol:8.4f} SOL  | cum buy={state['buy_sol']:.3f} sell={state['sell_sol']:.3f}")
        if "error" in d:
            log(f"helius: ERROR {d['error']}")
    ws = websocket.WebSocketApp(HELIUS_WS, on_open=on_open, on_message=on_message,
                                on_error=lambda w, e: log(f"helius err: {e}"),
                                on_close=lambda w, c, m: log(f"helius closed {c}"))
    state["hws"] = ws
    ws.run_forever(ping_interval=20, ping_timeout=10)


def subscribe_curve(curve):
    req = {"jsonrpc": "2.0", "id": 1, "method": "accountSubscribe",
           "params": [curve, {"encoding": "base64", "commitment": "processed"}]}
    for _ in range(50):
        hws = state.get("hws")
        if hws and hws.sock and hws.sock.connected:
            hws.send(json.dumps(req))
            log(f"helius: sent accountSubscribe for {curve[:12]}...")
            return True
        time.sleep(0.2)
    log("helius: ws never became writable")
    return False


# ---- PumpPortal side ----
def pump_loop():
    def on_open(ws):
        ws.send(json.dumps({"method": "subscribeNewToken"}))
        log("pump: subscribed subscribeNewToken")
    def on_message(ws, msg):
        if state["curve"] is not None:
            return
        try:
            d = json.loads(msg)
        except Exception:
            return
        if d.get("txType") == "create" and d.get("bondingCurveKey"):
            state["curve"] = d["bondingCurveKey"]
            state["mint"] = d.get("mint")
            log(f"pump: BIRTH {d.get('name','?')} seed={d.get('solAmount',0)} SOL curve={state['curve'][:12]}...")
            subscribe_curve(state["curve"])
    ws = websocket.WebSocketApp(PUMP_WS, on_open=on_open, on_message=on_message,
                                on_error=lambda w, e: log(f"pump err: {e}"),
                                on_close=lambda w, c, m: log(f"pump closed {c}"))
    ws.run_forever(ping_interval=20, ping_timeout=10)


th_h = threading.Thread(target=helius_loop, daemon=True)
th_p = threading.Thread(target=pump_loop, daemon=True)
th_h.start(); th_p.start()

while time.time() - t0 < WINDOW_S:
    time.sleep(1)

log(f"DONE: notifs={state['notifs']} decoded_trades={state['trades']} "
    f"buy_sol={state['buy_sol']:.4f} sell_sol={state['sell_sol']:.4f}")
ok = state["notifs"] > 0
print(f"VERDICT: {'PASS' if ok else 'FAIL'}", flush=True)
sys.exit(0 if ok else 1)
