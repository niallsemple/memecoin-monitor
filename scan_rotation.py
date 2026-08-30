"""Wallet-rotation scan (section 42): for every post-silence winner, fetch swap
history via Helius (cluster_tag internals), extract first buyers, then:
  (a) cluster-wallet presence per winner
  (b) cross-winner recurrence of NON-cluster wallets = rotation signal
Incremental save to rotation_scan.json."""
import json, time, urllib.request, collections
from cluster_tag import _key, _is_buy, cluster_wallets, HELIUS_TXS

MAX_PAGES = 8
MAX_BUYERS = 25

def scan(mint, key):
    url = HELIUS_TXS.format(mint, key)
    all_tx, before = [], None
    empty_streak = 0
    for _ in range(MAX_PAGES):
        u = url + (f"&before={before}" if before else "")
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "memecoin-monitor/1.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                txs = json.loads(r.read().decode())
        except Exception as e:
            return {"error": str(e)[:100]}
        if not txs:
            empty_streak += 1
            if empty_streak >= 2:
                break
            time.sleep(0.8)
            continue
        empty_streak = 0
        all_tx.extend(txs)
        before = txs[-1].get("signature")
        time.sleep(0.8)
    if not all_tx:
        return {"buyers": [], "pages": 0}
    all_tx.sort(key=lambda t: t.get("timestamp", 0))
    buyers, seen = [], set()
    for tx in all_tx:
        if _is_buy(tx, mint):
            b = tx.get("feePayer")
            if b and b not in seen:
                seen.add(b); buyers.append(b)
        if len(buyers) >= MAX_BUYERS:
            break
    return {"buyers": buyers, "pages": len(all_tx) // 100 + 1}

winners = json.load(open('post_silence_winners.json'))
cluster = cluster_wallets()
key = _key()
try:
    out = json.load(open('rotation_scan.json'))
except Exception:
    out = []
done = {r['id'] for r in out}

for w in winners:
    if w['id'] in done:
        continue
    mint = w['id'].split(':', 1)[1]
    t0 = time.time()
    r = scan(mint, key)
    buyers = r.get('buyers', [])
    rec = {'id': w['id'], 'peak_x': w['peak_x'], 'born_z': w['born_z'],
           'cluster_hits': [b for b in buyers if b in cluster],
           'n_buyers': len(buyers), 'buyers': buyers, 'error': r.get('error')}
    out.append(rec)
    done.add(w['id'])
    json.dump(out, open('rotation_scan.json', 'w'), indent=1)
    print(f"{w['id'][7:19]} peak={w['peak_x']}x cluster={rec['cluster_hits']} buyers={len(buyers)} err={r.get('error')} ({time.time()-t0:.0f}s)", flush=True)

# recurrence analysis
cnt = collections.Counter()
for r in out:
    for b in set(r.get('buyers', [])):
        if b not in cluster:
            cnt[b] += 1
recur = [(b, c) for b, c in cnt.most_common() if c >= 2]
print(f"\nwinners scanned: {len(out)} | with cluster wallet: {sum(1 for r in out if r['cluster_hits'])}")
print(f"non-cluster wallets in >=2 winners: {len(recur)}")
for b, c in recur[:15]:
    print(f"  {b[:12]}... in {c} winners")
json.dump(recur, open('rotation_recurring.json', 'w'), indent=1)
