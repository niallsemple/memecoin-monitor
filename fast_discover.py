#!/usr/bin/env python3
"""
fast_discover.py — single-page new_pools scan for the watched EVM chains,
run at the START of every watcher loop window so pools appear in
xchain_scan.jsonl within minutes of launch instead of waiting for the
hourly scan. Record shape identical to xchain_scan.py.

Usage: python3 fast_discover.py bsc base
"""
import json, time, sys, urllib.request, urllib.error

GT = 'https://api.geckoterminal.com/api/v2'
OUT = 'xchain_scan.jsonl'


def get(url, retries=2):
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'mfg-xchain/1.0'})
            with urllib.request.urlopen(req, timeout=20) as r:
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


def main(nets):
    now = time.time()
    n_new = 0
    with open(OUT, 'a') as f:
        for net in nets:
            d = get(f'{GT}/networks/{net}/new_pools?page=1')
            if not d or not isinstance(d.get('data'), list):
                continue
            for p in d['data']:
                a = p.get('attributes') or {}
                created = a.get('pool_created_at')
                if not created:
                    continue
                try:
                    age_h = (now - (time.mktime(time.strptime(created[:19], '%Y-%m-%dT%H:%M:%S'))
                                    - time.timezone)) / 3600
                except Exception:
                    continue
                if age_h > 6.0 or age_h < 0:
                    continue
                liq = float(a.get('reserve_in_usd') or 0)
                tx = (a.get('transactions') or {}).get('h1') or {}
                buys, sells = tx.get('buys') or 0, tx.get('sells') or 0
                vol = float((a.get('volume_usd') or {}).get('h1') or 0)
                rec = dict(t=now, chain=net, name=a.get('name') or '?',
                           pair=a.get('address'),
                           dex=(p.get('relationships') or {}).get('dex', {}).get('data', {}).get('id'),
                           age_h=round(age_h, 2), liq_usd=round(liq),
                           buys_h1=buys, sells_h1=sells,
                           flow=round(buys / max(sells, 1), 2), vol_h1=round(vol))
                f.write(json.dumps(rec) + '\n')
                n_new += 1
            time.sleep(2.5)
    print(f'fast_discover: {n_new} fresh pool rows appended for {nets}')


if __name__ == '__main__':
    main(sys.argv[1:] or ['bsc', 'base'])
