#!/usr/bin/env python3
"""Dump raw Helius accountNotification payloads to see the actual shape."""
import json, time
import websocket

MON = "/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor"
KEY = open(f"{MON}/helius_key.txt").read().strip()
HELIUS_WS = f"wss://mainnet.helius-rpc.com/?api-key={KEY}"
CURVE = "BwWK17cbHxwW"  # truncated -- will be replaced at runtime by fresh birth
PUMP_WS = "wss://pumpportal.fun/api/data"

count = {"n": 0}
t0 = time.time()

def on_open(ws):
    ws.send(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "accountSubscribe",
                        "params": [CURVE_FULL, {"encoding": "base64", "commitment": "processed"}]}))
    print("sent accountSubscribe", flush=True)

def on_message(ws, msg):
    count["n"] += 1
    if count["n"] <= 3:
        print(f"--- msg {count['n']} ---", flush=True)
        print(msg[:2000], flush=True)
    if time.time() - t0 > 30:
        ws.close()

# get a fresh curve first
import threading
CURVE_FULL = None
def pump():
    global CURVE_FULL
    def po(ws):
        ws.send(json.dumps({"method": "subscribeNewToken"}))
    def pm(ws, msg):
        global CURVE_FULL
        try:
            d = json.loads(msg)
        except Exception:
            return
        if d.get("txType") == "create" and d.get("bondingCurveKey") and CURVE_FULL is None:
            CURVE_FULL = d["bondingCurveKey"]
            print(f"fresh curve: {CURVE_FULL}", flush=True)
            ws.close()
    w = websocket.WebSocketApp(PUMP_WS, on_open=po, on_message=pm)
    w.run_forever()

pump()
if not CURVE_FULL:
    raise SystemExit("no birth seen")

ws = websocket.WebSocketApp(HELIUS_WS, on_open=on_open, on_message=on_message,
                            on_error=lambda w, e: print(f"err: {e}", flush=True))
ws.run_forever(ping_interval=20, ping_timeout=10)
print(f"total msgs: {count['n']}", flush=True)
