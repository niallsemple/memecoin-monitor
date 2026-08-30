#!/usr/bin/env python3
"""
xchain_scan.py — cross-chain scan for manufactured-launch (MFG) signatures.

Universe: GeckoTerminal free API new_pools per network (solana, base, bsc, eth).
Signature (§56 alert rule, USD units):
  age <= 6h, liquidity >= $15k, h1 buy/sell txn ratio >= 3,
  h1 buys >= 30, h1 buy-side volume proxy >= $3k (vol_h1 * buy share).
Solana hit-rate doubles as sanity check vs MFG tracker ground truth.

Output: xchain_scan.jsonl + console comparison.
"""
import json, time, urllib.request, urllib.error, collections

GT = 'https://api.geckoterminal.com/api/v2'
NETWORKS = ('solana', 'base', 'bsc', 'eth')
OUT = 'xchain_scan.jsonl'

MAX_AGE_H = 6.0
MIN_LIQ_USD = 15_000.0
MIN_FLOW = 3.0
MIN_BUYS_H1 = 30
MIN_BUYVOL_H1 = 3_000.0


def get(url, retries=2):
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'mfg-xchain/1.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < retries:
                time.sleep(8 * (i + 1))
                continue
            print(f'HTTP {e.code} for {url}')
            return None
        except Exception as e:
            print(f'ERR {e} for {url}')
            return None


def scan_network(net):
    pools = []
    for page in (1, 2, 3):
        d = get(f'{GT}/networks/{net}/new_pools?page={page}')
        if not d or not isinstance(d.get('data'), list):
            break
        pools.extend(d['data'])
        time.sleep(2.5)  # ~30 req/min free tier
    return pools


def main():
    now = time.time()
    stats = collections.defaultdict(lambda: dict(fresh=0, hits=0, deep_dump=0))
    hits = []
    n_seen = 0
    with open(OUT, 'a') as f:  # append: hits accumulate across runs for xchain_track
        for net in NETWORKS:
            pools = scan_network(net)
            for p in pools:
                a = p.get('attributes') or {}
                created = a.get('pool_created_at')
                if not created:
                    continue
                try:
                    age_h = (now - time.mktime(time.strptime(created[:19], '%Y-%m-%dT%H:%M:%S'))) / 3600
                    # pool_created_at is UTC; time.mktime assumes local — correct below
                    age_h = (now - (time.mktime(time.strptime(created[:19], '%Y-%m-%dT%H:%M:%S'))
                                    - time.timezone)) / 3600
                except Exception:
                    continue
                if age_h > MAX_AGE_H or age_h < 0:
                    continue
                n_seen += 1
                liq = float(a.get('reserve_in_usd') or 0)
                tx = (a.get('transactions') or {}).get('h1') or {}
                buys, sells = tx.get('buys') or 0, tx.get('sells') or 0
                vol = float((a.get('volume_usd') or {}).get('h1') or 0)
                flow = buys / max(sells, 1)
                buy_vol = vol * buys / max(buys + sells, 1)
                name = a.get('name') or '?'
                rec = dict(t=now, chain=net, name=name, pair=a.get('address'),
                           dex=(p.get('relationships') or {}).get('dex', {}).get('data', {}).get('id'),
                           age_h=round(age_h, 2), liq_usd=round(liq),
                           buys_h1=buys, sells_h1=sells, flow=round(flow, 2),
                           vol_h1=round(vol))
                f.write(json.dumps(rec) + '\n')
                s = stats[net]
                s['fresh'] += 1
                if liq >= MIN_LIQ_USD:
                    if flow >= MIN_FLOW and buys >= MIN_BUYS_H1 and buy_vol >= MIN_BUYVOL_H1:
                        s['hits'] += 1
                        hits.append(rec)
                    elif sells > buys * 2:
                        s['deep_dump'] += 1

    print(f'fresh pools scanned (<= {MAX_AGE_H}h): {n_seen}\n')
    print(f'{"chain":10s} {"fresh":>6s} {"MFG hits":>9s} {"hit rate":>9s} {"deep&dumping":>13s}')
    for c in NETWORKS:
        s = stats[c]
        rate = f"{s['hits'] / s['fresh'] * 100:.0f}%" if s['fresh'] else '—'
        print(f'{c:10s} {s["fresh"]:6d} {s["hits"]:9d} {rate:>9s} {s["deep_dump"]:13d}')
    print(f'\nMFG-signature hits ({len(hits)}):')
    for h in sorted(hits, key=lambda r: -r['liq_usd'])[:25]:
        print(f"  {h['chain']:8s} {h['name'][:22]:22s} age {h['age_h']:4.1f}h "
              f"liq ${h['liq_usd']:>8,} flow {h['flow']:5.1f} buys {h['buys_h1']:4d} "
              f"vol1h ${h['vol_h1']:>7,}")


if __name__ == '__main__':
    main()
