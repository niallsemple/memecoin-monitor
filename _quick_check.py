import json

d = json.load(open('xchain_outcomes.json'))
print(f'total outcome keys: {len(d)}')

# d is likely a dict mapping token -> outcome dict
items = list(d.values())
closed = [o for o in items if isinstance(o, dict) and o.get('status') == 'closed']
print(f'closed: {len(closed)}')
wins = [o for o in closed if o.get('return_pct', 0) > 0]
if closed:
    print(f'wins: {len(wins)} / {len(closed)} = {len(wins)/len(closed)*100:.0f}%')
    avg_r = sum(o.get('return_pct', 0) for o in closed) / len(closed)
    print(f'avg return: {avg_r:+.1f}%')
    for o in closed[-5:]:
        tok = o.get('token', '?')
        if isinstance(tok, str):
            tok = tok[:22]
        print(f"  {tok:22} {o.get('exit_reason', '?'):12} {o.get('return_pct', 0):+.1f}%")
else:
    print('no closed positions')
