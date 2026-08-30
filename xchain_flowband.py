#!/usr/bin/env python3
"""
xchain_flowband.py — does flow-at-detection predict outcome cross-chain?

Takes every fresh pool from xchain_scan.jsonl meeting the activity floor
(liq >= $15k, h1 buys >= 30), buckets by h1 flow ratio, and replays hourly
OHLC from detection through the §56e stack (free-roll 1.5x/75%, trail 50%,
time-stop 120min, conservative low-before-high ordering).

Bands: [1.5-3) control, [3-15) candidate sweet spot, [15+) 'textbook MFG'.
"""
import json, time, os, urllib.request, urllib.error, collections

GT = 'https://api.geckoterminal.com/api/v2'
SCAN = 'xchain_scan.jsonl'
CACHE = 'xchain_flowband.json'

MIN_LIQ, MIN_BUYS = 15_000.0, 30
T_TARGET, F_SELL, TRAIL, TS_MIN = 1.5, 0.75, 0.5, 120


def get(url, retries=3):
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'mfg-xchain/1.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < retries:
                time.sleep(15 * (i + 1))
                continue
            return None
        except Exception:
            return None


def replay(candles, detect_t):
    """Close-based replay (wicks are unreliable on thin pools).
    Only candles starting at/after detection; entry = first such candle's close.
    Return (ret, freerolled, peak) or None."""
    cs = [c for c in candles if c[0] > detect_t - 3600 and c[4] and c[4] > 0]
    if not cs:
        return None
    e = cs[0][4]
    entry_t = detect_t
    peak = 1.0
    pos = 1.0
    proceeds = 0.0
    fr = False
    for ts, o, h, l, c, v in cs:
        r = c / e
        if pos > 0 and r <= TRAIL * peak:
            proceeds += pos * r
            pos = 0
            break
        peak = max(peak, r)
        if not fr and r >= T_TARGET:
            proceeds += F_SELL * T_TARGET
            pos -= F_SELL
            fr = True
        if not fr and (ts - entry_t) / 60 >= TS_MIN:
            proceeds += pos * r
            pos = 0
            break
    if pos > 0:
        proceeds += pos * (cs[-1][4] / e)
    return proceeds - 1, fr, peak


def band(flow):
    if flow < 3:
        return '1.5-3 (control)'
    if flow <= 15:
        return '3-15 (sweet spot?)'
    return '15+ (textbook MFG)'


def main():
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    pools = {}
    for line in open(SCAN):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get('liq_usd', 0) >= MIN_LIQ and r.get('buys_h1', 0) >= MIN_BUYS:
            pools[(r['chain'], r['pair'])] = r
    print(f'qualifying pools (liq>=$15k, buys>=30): {len(pools)}')

    bands = collections.defaultdict(list)
    for (chain, pair), r in sorted(pools.items()):
        key = f'{chain}:{pair}'
        cached = cache.get(key) or {}
        d = get(f'{GT}/networks/{chain}/pools/{pair}/ohlcv/hour?aggregate=1&limit=48&currency=usd')
        time.sleep(3.0)
        lst = []
        if d:
            lst = ((d.get('data') or {}).get('attributes') or {}).get('ohlcv_list') or []
        # merge fresh candles into cache by timestamp (dedup), replay fresh each run
        merged = {c[0]: c for c in (cached.get('candles') or [])}
        for c in lst:
            merged[c[0]] = c
        candles = sorted(merged.values(), key=lambda c: c[0])
        if candles:
            cache[key] = dict(candles=candles)
        out = replay(candles, r['t']) if candles else None
        res = dict(ret=out[0], fr=out[1], peak=out[2]) if out else None
        if res is None:
            continue
        bands[band(r['flow'])].append((r, res))
    json.dump(cache, open(CACHE, 'w'))

    print(f'\n{"flow band":22s} {"n":>3s} {"mean":>7s} {"wins":>6s} {"FR rate":>8s}')
    for b in ('1.5-3 (control)', '3-15 (sweet spot?)', '15+ (textbook MFG)'):
        rows = bands.get(b, [])
        if not rows:
            print(f'{b:22s}   0')
            continue
        rets = [x[1]['ret'] for x in rows]
        wins = sum(1 for v in rets if v > 0)
        frs = sum(1 for x in rows if x[1]['fr'])
        print(f'{b:22s} {len(rows):3d} {sum(rets)/len(rets)*100:+6.0f}% '
              f'{wins:3d}/{len(rows):<2d} {frs/len(rows)*100:6.0f}%')
    print('\nper-pool detail:')
    for b in ('1.5-3 (control)', '3-15 (sweet spot?)', '15+ (textbook MFG)'):
        for r, res in bands.get(b, []):
            print(f"  [{b[:12]:12s}] {r['chain']:7s} {str(r.get('name'))[:20]:20s} "
                  f"flow {r['flow']:5.1f} liq ${r['liq_usd']:>8,} "
                  f"peak {res['peak']:4.1f}x ret {res['ret']*100:+5.0f}%")


if __name__ == '__main__':
    main()
