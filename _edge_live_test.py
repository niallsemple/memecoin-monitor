#!/usr/bin/env python3
"""_edge_live_test.py — grab one fresh pump.fun birth via PumpPortal and
screen it immediately (true entry-time conditions for edge_screen.py)."""
import json, sys, time
from pathlib import Path

MON = Path(__file__).resolve().parent
sys.path.insert(0, str(MON))

def grab_one(timeout_s=90):
    import websocket
    got = {}
    def on_open(ws):
        ws.send(json.dumps({"method": "subscribeNewToken"}))
    def on_message(ws, msg):
        try:
            d = json.loads(msg)
        except Exception:
            return
        if d.get("txType") == "create" and d.get("mint"):
            got.update(d)
            ws.close()
    ws = websocket.WebSocketApp("wss://pumpportal.fun/data-api/real-time",
                                on_open=on_open, on_message=on_message)
    import threading
    threading.Timer(timeout_s, ws.close).start()
    ws.run_forever(ping_interval=20)
    return got or None

if __name__ == "__main__":
    ev = grab_one()
    if not ev:
        print("no birth captured in window")
        sys.exit(1)
    mint = ev["mint"]
    print(f"captured birth: {ev.get('symbol','?')} ({ev.get('name','?')})")
    print(f"mint={mint}")
    print(f"creator={ev.get('traderPublicKey')}")
    from edge_screen import screen
    r = screen(mint, deployer=ev.get("traderPublicKey"))
    print(f"\nVERDICT: {r['verdict']} ({r['elapsed_s']}s)")
    for c in r["checks"]:
        mark = {"PASS": "✓", "WATCH": "~", "AVOID": "✗"}[c["verdict"]]
        print(f"  {mark} {c['check']:<22} {str(c['value']):<44} {c['note']}")
