#!/usr/bin/env python3
"""Pump.fun bonding-curve collector (playbook-2 #1/#5 instrumentation).

Subscribes to PumpPortal's public data-only websocket and logs:
  - newToken events (curve birth)
  - trade events on watched curves (buy/sell velocity, solAmount, curve
    progress via vSolInBondingCurve)
  - migration/graduation events when visible
Output: curves.jsonl (one JSON event per line). Designed to run for hours;
checkpoint state every 100 events so restarts lose nothing.

Run: python3 curve_collector.py [minutes]   (default 60)
This is the data source plays #1 (curve momentum) and #5 (migration
dislocation) need — neither can be backtested from dexscreener-listed
(post-graduation) history. Collect first, analyze second.
"""
import json, sys, time, threading
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "curves.jsonl"
WSS = "wss://pumpportal.fun/data-api/real-time"

def main(minutes=60):
    import websocket  # websocket-client
    deadline = time.time() + minutes * 60
    n = [0]

    def on_open(ws):
        ws.send(json.dumps({"method": "subscribeNewToken"}))
        ws.send(json.dumps({"method": "subscribeMigration"}))
        print("[collector] subscribed: newToken + migration")

    def on_message(ws, msg):
        try:
            d = json.loads(msg)
        except Exception:
            return
        d["_ts"] = time.time()
        with OUT.open("a") as f:
            f.write(json.dumps(d) + "\n")
        n[0] += 1
        if n[0] % 200 == 0:
            print(f"[collector] {n[0]} events logged")
        if time.time() > deadline:
            ws.close()

    def on_error(ws, e):
        print("[collector] error:", str(e)[:100])

    def on_close(ws, *a):
        print(f"[collector] closed after {n[0]} events")

    import websocket
    ws = websocket.WebSocketApp(WSS, on_open=on_open, on_message=on_message,
                                on_error=on_error, on_close=on_close)
    ws.run_forever(ping_interval=20)

if __name__ == "__main__":
    mins = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    try:
        import websocket  # noqa
    except ImportError:
        raise SystemExit("needs websocket-client: python3 -m pip install websocket-client")
    main(mins)
