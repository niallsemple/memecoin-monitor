"""One-shot probe: does pumpportal subscribeTokenTrade deliver, and with what fields?"""
import json, time, sys
import websocket

KEYS = [
    "BGC8SQXMiqRh", "5H9rBWuJeM1n", "83adFHEgE7VA", "DoX6jRj6dybC",
]
# full mints loaded from state
st = json.loads(open("/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor/mfg_state.json").read())
full = []
for pref in KEYS:
    for m in st:
        if m.startswith(pref):
            full.append(m)
print("probing mints:", [m[:12] + "…" for m in full])

msgs = []
t0 = time.time()

def on_message(ws, msg):
    el = time.time() - t0
    try:
        d = json.loads(msg)
    except Exception:
        print(f"[{el:5.1f}s] non-json: {msg[:100]}")
        return
    msgs.append(d)
    keys = sorted(d.keys())
    print(f"[{el:5.1f}s] txType={d.get('txType')} keys={keys}")
    if d.get("txType") in ("buy", "sell"):
        print(f"        mint={str(d.get('mint'))[:12]}… sol={d.get('solAmount')} tok={d.get('tokenAmount')} mc={d.get('marketCapSol')}")

def on_open(ws):
    print("open; sending subscribeTokenTrade")
    ws.send(json.dumps({"method": "subscribeTokenTrade", "keys": full}))

def on_error(ws, e):
    print("error:", str(e)[:150])

def on_close(ws, *a):
    print("closed")

ws = websocket.WebSocketApp("wss://pumpportal.fun/api/data",
                            on_open=on_open, on_message=on_message,
                            on_error=on_error, on_close=on_close)
import threading
th = threading.Thread(target=lambda: ws.run_forever(ping_interval=20, ping_timeout=10), daemon=True)
th.start()
time.sleep(75)
try:
    ws.close()
except Exception:
    pass
print(f"\nTOTAL messages in 75s: {len(msgs)}")
