import json, time, os, sys

SCAN = 'xchain_scan.jsonl'
STATE = 'xchain_outcomes.json'

MAX_AGE_H = 6.0
MIN_LIQ_USD = 15_000.0
MIN_FLOW = 3.0
MIN_BUYS_H1 = 30
MIN_BUYVOL_H1 = 3_000.0

print('loading state')
state = json.load(open(STATE)) if os.path.exists(STATE) else {}
print('state loaded', len(state))

print('loading hits')
hits = {}
cnt = 0
for line in open(SCAN):
    cnt += 1
    try:
        r = json.loads(line)
    except Exception:
        continue
    if (r.get('liq_usd', 0) >= MIN_LIQ_USD and r.get('flow', 0) >= MIN_FLOW
            and r.get('buys_h1', 0) >= MIN_BUYS_H1):
        bv = r.get('vol_h1', 0) * r['buys_h1'] / max(r['buys_h1'] + r.get('sells_h1', 0), 1)
        if bv >= MIN_BUYVOL_H1:
            hits[(r['chain'], r['pair'])] = r
print('hits loaded', len(hits), 'lines scanned', cnt)
