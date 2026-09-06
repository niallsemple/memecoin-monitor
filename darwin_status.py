#!/usr/bin/env python3
"""DARWIN one-command status digest (§381). Prints: scheduler grid health,
memecoin book (cohort + full), open positions, liquidation radar, shock
watcher, wallet. Read-only."""
import json
import time
from pathlib import Path

MON = Path(__file__).resolve().parent
NOW = time.time()


def rows(path):
    p = MON / path
    if not p.exists():
        return []
    out = []
    for line in p.open():
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


trades = rows("mfg_live_trades.jsonl")
for r in trades:
    r["_ts"] = r.get("t") or r.get("ts") or 0

print("=== DARWIN status", time.strftime("%Y-%m-%d %H:%M:%S"), "===")

# --- book ---
opens = [r for r in trades if r.get("action") == "open_position" and r.get("mode") == "live"]
exits = {}
for r in trades:
    # §390: writeoffs ARE exits (rug dust) — excluding them hid rug losses
    # from the forward tally after §384/§389.
    if r.get("action") in ("exit_decision", "exit_writeoff"):
        exits.setdefault(r["mint"], []).append(r)
S376 = 1788643200  # §376 flip 21:00 UTC (22:00 BST) Sep 5
coh = [o for o in opens if o["_ts"] >= S376]
pnl376 = wins376 = closed376 = 0
for o in coh:
    xs = [e for e in exits.get(o["mint"], []) if e["_ts"] >= o["_ts"]]
    if xs and xs[-1].get("est_sol") is not None:
        closed376 += 1
        p = xs[-1]["est_sol"] - o["size_sol"]
        pnl376 += p
        wins376 += p > 0
tot_pnl = n_matched = 0
for o in opens:
    xs = [e for e in exits.get(o["mint"], []) if e["_ts"] >= o["_ts"]]
    if xs and xs[-1].get("est_sol") is not None:
        n_matched += 1
        tot_pnl += xs[-1]["est_sol"] - o["size_sol"]
print(f"book: {len(opens)} opens, {n_matched} closed, cumPnL(est) {tot_pnl:+.4f} SOL")
print(f"§376 forward: {len(coh)} opens, {closed376} closed, {wins376} wins, {pnl376:+.4f} SOL")

pos = {}
pf = MON / "live_positions.json"
if pf.exists():
    pos = json.loads(pf.read_text())
open_pos = [(m, p) for m, p in pos.items() if p.get("open")]
for m, p in open_pos:
    print(f"OPEN {m[:12]} age={(NOW - p['entry_t'])/60:.0f}m peak={p.get('peak_mult', 0):.3f}")
if not open_pos:
    print("open positions: none")

# --- liquidation radar ---
hl = rows("liq_health_log.jsonl")
if hl:
    h = hl[-1]
    print(f"liq scan: {(NOW - h['ts'])/60:.0f}m ago, material={h['material']}, "
          f"liquidatable_now={len(h.get('liquidatable_now') or [])}")
sw = rows("liq_shock_watch.jsonl")
if sw:
    s = sw[-1]
    print(f"shock watch: {(NOW - s['ts'])/60:.0f}m ago, watching {s['n']} accounts")
sf = rows("liq_shock_fires.jsonl")
print(f"shock crossings fired: {len(sf)}")

# --- H16 shadow forward test ---
h16 = rows("h16_shadow.jsonl")
if h16:
    opens = [r for r in h16 if r.get("action") == "h16_open"]
    closes = [r for r in h16 if r.get("action") == "h16_close"]
    wins = sum(1 for r in closes if r.get("outcome") == "win")
    print(f"H16 shadow: {len(opens)} opens, {len(closes)} closed, {wins} wins")

# --- §422: market heat gauge ---
try:
    hg = json.loads((MON / "heat_state.json").read_text())
    print(f"market heat: {hg['band']} ({hg['hot_pct']}% hot, "
          f"{hg['scorable']} scorable/{hg['seeds']} seeds, 60min)")
except Exception:
    pass

# --- wallet ---
try:
    import urllib.request
    key = (MON / "helius_key.txt").read_text().strip()
    req = urllib.request.Request(
        f"https://mainnet.helius-rpc.com/?api-key={key}",
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getBalance",
                         "params": ["CQcKkSee9bdHZ1bejYFDUXVtodbfKHe2KSx6AaAnTW2K"]}).encode(),
        headers={"Content-Type": "application/json"})
    bal = json.loads(urllib.request.urlopen(req, timeout=20).read())["result"]["value"] / 1e9
    print(f"wallet: {bal:.4f} SOL")
except Exception as e:
    print("wallet: query failed", str(e)[:60])
