import json

# pumpswap_live trades
with open('pumpswap_live_trades.jsonl') as f:
    ps = [json.loads(l) for l in f]
entries = [x for x in ps if x.get('action') == 'entry_signal']
exits = [x for x in ps if x.get('action') == 'exit_signal']
print(f"pumpswap_live: ENTRY={len(entries)} EXIT={len(exits)}")
for e in entries[-3:]:
    mode = e.get('mode', 'dry')
    tag = '[LIVE]' if mode == 'live' else '[dry]'
    print(f"  {tag} ENTRY {e.get('mint','')[:20]}... px={e.get('entry_px')} liq={e.get('liq')}")
for e in exits[-3:]:
    print(f"  EXIT {e.get('mint','')[:20]}... reason={e.get('reason')} ret={e.get('ret')} held={e.get('held_min')}m")

# Trade books line counts + open positions
files = [
    'base4_paper_trades.jsonl',
    'base4_paper_trades_crowd.jsonl',
    'bsc_paper_trades.jsonl',
    'bsc_paper_trades_lockgate.jsonl',
    'bsc_paper_trades_lockgate_usdt.jsonl',
    'bsc_paper_trades_lockgate_gp.jsonl',
    'base_paper_trades.jsonl',
]
print("\n--- Trade books ---")
for f in files:
    try:
        with open(f) as fh:
            lines = [json.loads(l) for l in fh if l.strip()]
        n = len(lines)
        opens = sum(1 for x in lines if x.get('open', False))
        print(f"{f}: lines={n} open={opens}")
    except Exception as e:
        print(f"{f}: ERROR {e}")
