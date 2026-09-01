import json

# MFG state
mfg = json.load(open('mfg_state.json'))
print(f'MFG state entries: {len(mfg)}')

# Count by chain
from collections import Counter
chains = Counter(v.get('chain', '?') for v in mfg.values() if isinstance(v, dict))
print('By chain:', dict(chains))

# Check mfg_funding_seen for hits
funding = json.load(open('mfg_funding_seen.json'))
print(f'MFG funding seen: {len(funding)}')

# Paper positions
paper = json.load(open('paper_v6.json'))
print(f'Paper v6 entries: {len(paper)}')
if isinstance(paper, dict):
    open_p = [v for v in paper.values() if isinstance(v, dict) and v.get('status') == 'open']
    closed_p = [v for v in paper.values() if isinstance(v, dict) and v.get('status') == 'closed']
    print(f'Paper open: {len(open_p)}, closed: {len(closed_p)}')
    if closed_p:
        wins = [p for p in closed_p if p.get('return_pct', 0) > 0]
        print(f'Paper win rate: {len(wins)}/{len(closed_p)} = {len(wins)/len(closed_p)*100:.1f}%')
        avg = sum(p.get('return_pct', 0) for p in closed_p) / len(closed_p)
        print(f'Paper avg return: {avg:+.2f}%')
        # Show last few closed
        for p in closed_p[-3:]:
            tok = p.get('token', p.get('name', '?'))
            if isinstance(tok, str): tok = tok[:20]
            print(f"  {tok:20} {p.get('exit_reason', '?'):12} {p.get('return_pct', 0):+.1f}%")
