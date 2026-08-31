"""Probe v2: subscribe trades on the freshest births; print ack text."""
import json, time, threading
import websocket

mints = []
with open("/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor/curves.jsonl") as f:
    for line in f:
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("txType") == "create" and d.get("mint"):
            mints.append((d.get("_ts", 0), d["mint"]))
mints = [m for _, m in sorted(mints)[-12:]]
print(f"subscribing to {len(mints)} freshest births:", [m[:10] + "…" for m in mints])

msgs = []
t0 = time.time()

def on_message(ws, msg):
    el = time.time() - t0
    try:
        d = json.loads(msg)
    except Exception:
        print(f"[{el:5.1f}s] non-json: {msg[:120]}")
        return
    msgs.append(d)
    if "message" in d:
        print(f"[{el:5.1f}s] ACK: {d['message']}")
    else:
        print(f"[{el:5.1f}s] txType={d.get('txType')} mint={str(d.get('mint'))[:10]}… sol={d.get('solAmount')} mc={d.get('marketCapSol')} keys={sorted(d.keys())}")

def on_open(ws):
    print("open; sending subscribeTokenTrade")
    ws.send(json.dumps({"method": "subscribeTokenTrade", "keys": mints}))

def on_error(ws, e):
    print("error:", str(e)[:150])

ws = websocket.WebSocketApp("wss://pumpportal.fun/api/data",
                            on_open=on_open, on_message=on_message,
                            on_error=on_error, on_close=lambda *a: print("closed"))
threading.Thread(target=lambda: ws.run_forever(ping_interval=20, ping_timeout=10), daemon=True).start()
time.sleep(90)
try:
    ws.close()
except Exception:
    pass
trades = [m for m in msgs if m.get("txType") in ("buy", "sell")]
print(f"\nTOTAL msgs={len(msgs)}, trade msgs={len(trades)}")
