import json

# Read scan jsonl
lines = [json.loads(l) for l in open('xchain_scan.jsonl')]
recent = sorted(lines, key=lambda x: x.get('t',0), reverse=True)[:10]
print("Latest scan hits:")
for r in recent:
    if r.get('flow',0) >= 5 or r.get('liq_usd',0) > 10000:
        print(f"  {r['chain']:8s} {r['name']:30s}  liq=${r.get('liq_usd',0):>8,.0f}  flow={r.get('flow',0):.1f}")

# Count today's scan hits by chain
from collections import Counter
chains = Counter(l['chain'] for l in lines if l.get('flow',0) >= 5)
print(f"\nMFG hits by chain (flow>=5): {dict(chains)}")

# Read outcomes
outcomes = json.load(open('xchain_outcomes.json'))
print(f"Total tracked outcomes: {len(outcomes)}")

# Show stats
statuses = {}
returns = []
closed_list = []
for k, o in outcomes.items():
    s = o.get('status','?')
    statuses[s] = statuses.get(s, 0) + 1
    if s == 'closed' and 'return' in o:
        returns.append(o['return'])
        closed_list.append(o)

print(f"Statuses: {statuses}")
if returns:
    wins = [r for r in returns if r > 0]
    win_rate = len(wins)/len(returns)
    expectancy = sum(returns)/len(returns)
    print(f"Win rate: {win_rate:.1%} ({len(wins)}/{len(returns)})")
    print(f"Expectancy: {expectancy:.1%}")

# Recent closed
closed_recent = sorted(closed_list, key=lambda x: x.get('closed_time', x.get('time','')), reverse=True)[:5]
print("\nRecent closed positions:")
for c in closed_recent:
    name = c.get('name','?')
    chain = c.get('chain','?')
    reason = c.get('exit_reason', c.get('reason','?'))
    ret = c.get('return','?')
    if isinstance(ret, (int,float)):
        print(f"  {chain} {name}: {reason} → {ret:+.1%}")
    else:
        print(f"  {chain} {name}: {reason} → {ret}")

# Find today's scan hits (from this run)
# The scan output showed 2 MFG hits with flow >= 5
# Let's extract those specific ones
print("\nThis scan's new MFG hits (flow>=5):")
for r in recent:
    if r.get('flow',0) >= 5:
        print(f"  {r['chain']} {r['name']}  liq=${r.get('liq_usd',0):,.0f}  flow={r.get('flow',0):.1f}")
