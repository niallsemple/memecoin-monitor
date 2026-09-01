import json

lines = open('xchain_scan.jsonl').readlines()
print(f'Total scan lines: {len(lines)}')

# Count MFG hits from this scan (the ones printed by xchain_scan.py)
# We know from output there were 6 MFG hits
# Let's verify by checking the latest entries in the jsonl
latest = [json.loads(l) for l in lines[-50:]]
for e in latest:
    if e.get('flow', 0) > 0 and e.get('buys_h1', 0) > 0:
        print(f"  {e['chain']:8} {e['name']:25} age={e['age_h']:.1f}h liq=${e.get('liq_usd', 0):,.0f} flow={e['flow']} vol1h=${e.get('vol_h1', 0):,.0f}")
