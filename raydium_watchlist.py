#!/usr/bin/env python3
"""Raydium pool scanner — same gates as the Meteora watchlist, cross-provider.

Pulls pools from the public Raydium data API (api-v3.raydium.io), scores them
on fee yield (fee24h/TVL annualized), volume/TVL activity ratio, and TVL floor,
and writes a JSONL snapshot per run for trend tracking.

Modes:
  python3 raydium_watchlist.py          # aged/active candidates (default gates)
  python3 raydium_watchlist.py --fresh  # pools with recent openTime (LaunchLab grads)

No transactions, read-only. The point: compare Raydium CLMM/CPMM fee yields
against our Meteora DLMM cell before deploying anything.
"""
import json, sys, time, urllib.request

API = 'https://api-v3.raydium.io/pools/info/list'
SNAP_F = 'raydium_pool_snaps.jsonl'

# gates (mirror lp_deploy_watchlist.py intent)
MIN_TVL = 25_000          # $ — below this, fee estimates are noise
MIN_VOL_TVL = 0.5         # volume24h / tvl — pool must actually trade
FRESH_HOURS = 48          # --fresh: pools opened in last N hours
PAGES = 4                 # 100 pools per sort field


def fetch(sort_field):
    url = (f'{API}?poolType=all&poolSortField={sort_field}&sortType=desc'
           f'&pageSize=50&page=1')
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.load(r)
            if d.get('success'):
                return d['data']['data']
        except Exception as e:
            print(f'  fetch {sort_field} attempt {attempt+1} failed: {e}')
            time.sleep(2)
    return []


def score(p):
    tvl = p.get('tvl') or 0
    day = p.get('day') or {}
    vol = day.get('volume') or 0
    fee = day.get('volumeFee') or 0
    fee_apr = (day.get('feeApr') or 0)
    vt = vol / tvl if tvl else 0
    try:
        ot = int(p.get('openTime') or 0)
    except (TypeError, ValueError):
        ot = 0
    age_h = (time.time() - ot) / 3600 if ot else None
    return {
        'id': p.get('id'), 'type': p.get('type'),
        'pair': f"{p.get('mintA',{}).get('symbol')}/{p.get('mintB',{}).get('symbol')}",
        'mintB': p.get('mintB', {}).get('address'),
        'tvl': tvl, 'vol24h': vol, 'fee24h': fee,
        'fee_apr_pct': fee_apr, 'fee_yield_day_pct': fee_apr / 365,
        'vol_tvl': vt, 'age_h': age_h, 'feeRate': p.get('feeRate'),
    }


def main():
    fresh = '--fresh' in sys.argv
    seen = {}
    for sf in ('fee24h', 'volume24h'):
        for p in fetch(sf):
            seen[p['id']] = p
    rows = [score(p) for p in seen.values()]
    print(f'scanned {len(rows)} unique pools (top by fee24h + volume24h)')

    if fresh:
        cands = [r for r in rows if r['age_h'] is not None and r['age_h'] <= FRESH_HOURS
                 and r['tvl'] >= MIN_TVL / 5]
        cands.sort(key=lambda r: r['age_h'] or 0)
        print(f'\nFRESH pools (<{FRESH_HOURS}h old, tvl>${MIN_TVL/5:.0f}k): {len(cands)}')
    else:
        cands = [r for r in rows if r['tvl'] >= MIN_TVL and r['vol_tvl'] >= MIN_VOL_TVL]
        cands.sort(key=lambda r: -r['fee_yield_day_pct'])
        print(f'CANDIDATES (tvl>=${MIN_TVL/1000:.0f}k, vol/tvl>={MIN_VOL_TVL}): {len(cands)}')

    for r in cands[:20]:
        age = f"{r['age_h']:.1f}h" if r['age_h'] is not None else 'old'
        print(f"  {r['pair'][:24]:24s} {r['type'][:12]:12s} tvl ${r['tvl']/1000:7.0f}k "
              f"vol/tvl {r['vol_tvl']:5.1f} fee/day {r['fee_yield_day_pct']:6.2f}% age {age}")

    with open(SNAP_F, 'a') as f:
        f.write(json.dumps({'ts': time.time(), 'mode': 'fresh' if fresh else 'aged',
                            'n_scanned': len(rows), 'cands': cands[:50]}) + '\n')
    print(f'\nsnapshot appended to {SNAP_F}')


if __name__ == '__main__':
    main()
