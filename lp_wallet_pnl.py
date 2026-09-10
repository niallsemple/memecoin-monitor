#!/usr/bin/env python3
"""Wallet-level P&L for a Meteora LP cell, from on-chain transaction deltas.

Deposit-size comparisons lie (re-centers release/pull wallet SOL). This script
sums the wallet's SOL delta across every LP transaction for one pool — initial
deploy, re-center exits and redeploys — then adds the current open position's
value and any swept fee proceeds. Result: true net P&L of the cell.

Run: python3 lp_wallet_pnl.py [pool_prefix]   (default AsSyvUnb = MET-SOL)
"""
import json, re, sys, time, urllib.request

KEY = open('helius_key.txt').read().strip()
RPC = f'https://mainnet.helius-rpc.com/?api-key={KEY}'
WALLET = 'CQcKkSee9bdHZ1bejYFDUXVtodbfKHe2KSx6AaAnTW2K'
POOL_PREFIX = sys.argv[1] if len(sys.argv) > 1 else 'AsSyvUnb'
# SOL proceeds from sweeping claimed X-side fees (lp_sweep sells). Recorded from
# sweep output; the sweep sell sig is not captured in the logs.
SWEEP_PROCEEDS = 0.001277271


def tx(sig):
    req = urllib.request.Request(RPC, data=json.dumps({
        'jsonrpc': '2.0', 'id': 1, 'method': 'getTransaction',
        'params': [sig, {'encoding': 'json', 'maxSupportedTransactionVersion': 0}]
    }).encode(), headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=30)).get('result')


def wallet_delta(t):
    keys = [k['pubkey'] if isinstance(k, dict) else k
            for k in t['transaction']['message']['accountKeys']]
    if WALLET not in keys:
        return None
    i = keys.index(WALLET)
    m = t['meta']
    return (m['postBalances'][i] - m['preBalances'][i]) / 1e9


st = json.load(open('lp_positions.json'))
pool_positions = [p for p in st['positions'] if p.get('pool', '').startswith(POOL_PREFIX)]
assert pool_positions, f'no positions for pool {POOL_PREFIX}'

# ordered sig list: deploys from position records, exits from guardian log
sigs = []  # (label, sig)
for p in pool_positions:
    if p.get('add_sig'):
        sigs.append((f"deploy {p.get('sol_in')} SOL", p['add_sig']))
    for s in (p.get('exit_sigs') or []):
        sigs.append(('exit', s))
# guardian recenter sigs (exits not always recorded on the position record)
for l in open('lp_guardian_actions.jsonl'):
    r = json.loads(l)
    if not str(r.get('pool', '')).startswith(POOL_PREFIX):
        continue
    if r.get('kind') in ('recenter_exit', 'emergency_exit', 'recenter_redeploy'):
        for m in re.findall(r'sigs?=([1-9A-HJ-NP-Za-km-z]{80,90})', r.get('out') or ''):
            sigs.append((r['kind'], m))

# dedupe preserving order
seen, ordered = set(), []
for label, s in sigs:
    if s not in seen:
        seen.add(s)
        ordered.append((label, s))

total = 0.0
deltas = {}
print(f"pool {POOL_PREFIX}…  {len(ordered)} txs")
for label, s in ordered:
    t = tx(s)
    if not t:
        print(f"  {label:24s} {s[:12]}…  NOT FOUND")
        continue
    d = wallet_delta(t)
    if d is None:
        print(f"  {label:24s} {s[:12]}…  wallet not in tx")
        continue
    deltas[s] = d
    total += d
    bt = t.get('blockTime') or 0
    print(f"  {label:24s} {s[:12]}…  {d:+.6f} SOL  {time.strftime('%m-%d %H:%M', time.gmtime(bt))}")
    time.sleep(0.25)

open_pos = [p for p in pool_positions if p.get('status') == 'open']
open_val = sum(p.get('sol_in', 0) for p in open_pos)
# position-account rent is locked in the open position but recoverable on exit
rent = 0.0
for p in open_pos:
    d = deltas.get(p.get('add_sig'))
    if d is not None:
        rent += max(0.0, abs(d) - p.get('sol_in', 0) - 0.00002)
print(f"\nnet wallet flow      : {total:+.6f} SOL")
print(f"swept fee proceeds   : {SWEEP_PROCEEDS:+.6f} SOL")
print(f"open position value  : {open_val:.6f} SOL liquidity + {rent:.6f} SOL locked rent ({len(open_pos)} open)")
print(f"cell P&L             : {total + SWEEP_PROCEEDS + open_val + rent:+.6f} SOL")
