import json

with open('mfg_state.json') as f:
    state = json.load(f)

# Count tracked hits (entries with 'scan' data)
tracked = {k:v for k,v in state.items() if v.get('scan')}
print(f"Total tracked hits: {len(tracked)}")

# Find closed positions
closed = []
for k,v in state.items():
    if v.get('status') == 'closed' and v.get('exit'):
        closed.append({
            'name': v.get('scan',{}).get('name','?'),
            'chain': v.get('scan',{}).get('chain','?'),
            'exit_reason': v['exit'].get('reason','?'),
            'return': v['exit'].get('return','?'),
            'exit_time': v['exit'].get('time','?')
        })

print(f"\nClosed positions: {len(closed)}")
for c in closed[-10:]:  # show last 10
    print(f"  {c['chain']} {c['name']}: {c['exit_reason']} → {c['return']:.1%}" if isinstance(c['return'], float) else f"  {c['chain']} {c['name']}: {c['exit_reason']} → {c['return']}")

# Compute stats
if closed:
    returns = [c['return'] for c in closed if isinstance(c['return'], (int, float))]
    wins = [r for r in returns if r > 0]
    win_rate = len(wins)/len(returns) if returns else 0
    expectancy = sum(returns)/len(returns) if returns else 0
    print(f"\nWin rate: {win_rate:.1%} ({len(wins)}/{len(returns)})")
    print(f"Expectancy: {expectancy:.1%}")

# New hits from this scan (check if any entries are very recent)
print("\nRecent entries (last 5 by scan.time):")
recent = sorted(state.items(), key=lambda x: x[1].get('scan',{}).get('time',''), reverse=True)[:5]
for k,v in recent:
    s = v.get('scan',{})
    print(f"  {s.get('chain','?')} {s.get('name','?')}: liq=${s.get('liq_usd',0):,.0f} flow={s.get('flow',0)}")
