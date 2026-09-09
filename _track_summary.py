import json
from datetime import datetime

outcomes = json.load(open('xchain_outcomes.json'))

# Find recently closed (last 24h)
now = 1788557429  # approximate current time from scan
recent_closed = []
for k, o in outcomes.items():
    if o.get('status') == 'closed':
        ct = o.get('closed_time', 0)
        if now - ct < 86400:
            recent_closed.append(o)

recent_closed.sort(key=lambda x: x.get('closed_time',0), reverse=True)
print(f"Closed in last 24h: {len(recent_closed)}")
for c in recent_closed[:10]:
    ret = c.get('return','?')
    if isinstance(ret, (int,float)):
        print(f"  {c.get('chain','?')} {c.get('name','?')}: {c.get('exit_reason','?')} → {ret:+.1%}")
    else:
        print(f"  {c.get('chain','?')} {c.get('name','?')}: {c.get('exit_reason','?')} → {ret}")

# Overall stats
returns = []
for k, o in outcomes.items():
    if o.get('status') == 'closed' and 'return' in o:
        returns.append(o['return'])

if returns:
    wins = [r for r in returns if r > 0]
    win_rate = len(wins)/len(returns)
    expectancy = sum(returns)/len(returns)
    print(f"\nAll-time closed: {len(returns)}")
    print(f"Win rate: {win_rate:.1%} ({len(wins)}/{len(returns)})")
    print(f"Expectancy: {expectancy:+.1%}")
