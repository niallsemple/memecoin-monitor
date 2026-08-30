"""Loser base-rate for rotation recurrence (completes section 42 falsification).
Sample same-window LOSERS (born after 20:30Z 27 Aug, peak <1.3x, age >=2h so
peak is settled), scan first buyers, count wallets recurring in >=2 losers.
Compare against winners: 26 wallets in >=2 of 21 winners.
Incremental save to losers_scan.json."""
import json, time, urllib.request, collections, random
from cluster_tag import _key, _is_buy, cluster_wallets, HELIUS_TXS

MAX_PAGES = 8
MAX_BUYERS = 25
CUTOFF = 1787862600*1000  # 20:30Z 27 Aug 2026 ms

def scan(mint, key):
    url = HELIUS_TXS.format(mint, key)
    all_tx, before = [], None
    empty = 0
    for _ in range(MAX_PAGES):
        u = url + (f"&before={before}" if before else "")
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "memecoin-monitor/1.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                txs = json.loads(r.read().decode())
        except Exception as e:
            return {"error": str(e)[:100]}
        if not txs:
            empty += 1
            if empty >= 2:
                break
            time.sleep(0.8)
            continue
        empty = 0
        all_tx.extend(txs)
        before = txs[-1].get("signature")
        time.sleep(0.8)
    if not all_tx:
        return {"buyers": []}
    all_tx.sort(key=lambda t: t.get("timestamp", 0))
    buyers, seen = [], set()
    for tx in all_tx:
        if _is_buy(tx, mint):
            b = tx.get("feePayer")
            if b and b not in seen:
                seen.add(b); buyers.append(b)
        if len(buyers) >= MAX_BUYERS:
            break
    return {"buyers": buyers}

state = json.load(open('state.json'))
now_ms = time.time()*1000
losers = []
for key_, rec in state['seen'].items():
    if not key_.startswith('solana:'):
        continue
    born = rec.get('detect', {}).get('pair_created')
    hist = [h for h in rec.get('history', []) if h.get('mcap')]
    if not born or not hist or born < CUTOFF:
        continue
    age_h = (now_ms - born)/3.6e6
    if age_h < 2:
        continue
    base = hist[0]['mcap']; peak = max(h['mcap'] for h in hist)
    if base > 0 and peak/base < 1.3:
        losers.append(key_)
random.seed(42)
random.shuffle(losers)
print(f"eligible losers: {len(losers)}")

try:
    out = json.load(open('losers_scan.json'))
except Exception:
    out = []
done = {r['id'] for r in out}
todo = [l for l in losers if l not in done][:12]  # one batch per turn
key = _key()
cluster = cluster_wallets()
for lid in todo:
    mint = lid.split(':', 1)[1]
    t0 = time.time()
    r = scan(mint, key)
    buyers = r.get('buyers', [])
    out.append({'id': lid, 'cluster_hits': [b for b in buyers if b in cluster],
                'n_buyers': len(buyers), 'buyers': buyers, 'error': r.get('error')})
    json.dump(out, open('losers_scan.json', 'w'), indent=1)
    print(f"{lid[7:19]} buyers={len(buyers)} cluster={[b[:8] for b in buyers if b in cluster]} err={r.get('error')} ({time.time()-t0:.0f}s)", flush=True)

cnt = collections.Counter()
for r in out:
    for b in set(r.get('buyers', [])):
        if b not in cluster:
            cnt[b] += 1
recur = [(b, c) for b, c in cnt.most_common() if c >= 2]
print(f"\nlosers scanned total: {len(out)} | non-cluster recurring >=2: {len(recur)}")
for b, c in recur[:10]:
    print(f"  {b[:12]}... in {c} losers")
EOF_MARKER = None
