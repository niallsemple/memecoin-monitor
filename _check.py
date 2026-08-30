import json, os

SCAN = 'xchain_scan.jsonl'
STATE = 'xchain_outcomes.json'

MIN_LIQ_USD = 15_000.0
MIN_FLOW = 3.0
MIN_BUYS_H1 = 30
MIN_BUYVOL_H1 = 3_000.0

count = 0
for line in open(SCAN):
    try:
        r = json.loads(line)
    except:
        continue
    if (r.get('liq_usd', 0) >= MIN_LIQ_USD and r.get('flow', 0) >= MIN_FLOW
            and r.get('buys_h1', 0) >= MIN_BUYS_H1):
        bv = r.get('vol_h1', 0) * r['buys_h1'] / max(r['buys_h1'] + r.get('sells_h1', 0), 1)
        if bv >= MIN_BUYVOL_H1:
            count += 1

print(f'MFG hits in scan file: {count}')

st = {}
if os.path.exists(STATE) and os.path.getsize(STATE) > 2:
    try:
        st = json.load(open(STATE))
    except:
        pass
print(f'state entries: {len(st)}')
for k, v in st.items():
    print(f"  {k}: {v.get('name')} | status={v.get('status')} | exit={v.get('exit_reason')} | ret={v.get('ret')}")
