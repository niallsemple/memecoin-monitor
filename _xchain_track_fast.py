#!/usr/bin/env python3
"""
xchain_track.py — forward outcome tracker for cross-chain MFG hits.

Reads xchain_scan.jsonl, selects MFG-signature hits (same thresholds as
xchain_scan.py), polls each pool's current state via GeckoTerminal, and
scores the §56e free-roll stack against the price path observed across runs:
  entry = first-seen price; free-roll at 1.5x (sell 75%); trail at 50% of
  peak; time-stop 120 min after entry.
State persists in xchain_outcomes.json (rebuilt + updated each run).

Note: marks are only as frequent as runs — coarse vs the Solana trade-level
paper-trader. Directional only.
"""
import json, time, os, urllib.request, urllib.error

GT = 'https://api.geckoterminal.com/api/v2'
SCAN = 'xchain_scan.jsonl'
STATE = 'xchain_outcomes.json'

MAX_AGE_H = 6.0
MIN_LIQ_USD = 15_000.0
MIN_FLOW = 3.0
MIN_BUYS_H1 = 30
MIN_BUYVOL_H1 = 3_000.0

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
            print(f'HTTP {e.code} {url}')
            return None
        except Exception as e:
            print(f'ERR {e} {url}')
            return None


def load_hits():
    hits = {}
    if not os.path.exists(SCAN):
        return hits
    for line in open(SCAN):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if (r.get('liq_usd', 0) >= MIN_LIQ_USD and r.get('flow', 0) >= MIN_FLOW
                and r.get('buys_h1', 0) >= MIN_BUYS_H1):
            bv = r.get('vol_h1', 0) * r['buys_h1'] / max(r['buys_h1'] + r.get('sells_h1', 0), 1)
            if bv >= MIN_BUYVOL_H1:
                hits[(r['chain'], r['pair'])] = r
    return hits


def fetch_ohlc(chain, pair, limit=48):
    """Hourly OHLC candles [[ts, o, h, l, c, vol], ...] oldest-first."""
    d = get(f'{GT}/networks/{chain}/pools/{pair}/ohlcv/hour?aggregate=1&limit={limit}&currency=usd')
    if not d:
        return []
    lst = ((d.get('data') or {}).get('attributes') or {}).get('ohlcv_list') or []
    return sorted(lst, key=lambda c: c[0])


def apply_bar(st, close):
    """Walk one candle CLOSE through the exit stack (wicks unreliable on thin pools)."""
    e = st['entry_price']
    r = close / e
    if st['pos'] > 0 and r <= TRAIL * st['peak']:
        st['proceeds'] += st['pos'] * r
        st['pos'] = 0
        st['status'] = 'closed'
        st['exit_reason'] = 'trail'
        return
    st['peak'] = max(st['peak'], r)
    if not st['freerolled'] and r >= T_TARGET:
        st['proceeds'] += F_SELL * T_TARGET
        st['pos'] -= F_SELL
        st['freerolled'] = True


def main():
    now = time.time()
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    hits = load_hits()
    print(f'tracking {len(hits)} hits')

    for (chain, pair), h in hits.items():
        key = f'{chain}:{pair}'
        d = get(f'{GT}/networks/{chain}/pools/{pair}')
        time.sleep(1.5)
        if not d or 'data' not in d:
            continue
        a = d['data'].get('attributes') or {}
        price = float(a.get('base_token_price_usd') or 0)
        liq = float(a.get('reserve_in_usd') or 0)
        if price <= 0:
            continue
        st = state.get(key)
        if not st:
            st = dict(chain=chain, pair=pair, name=h.get('name'),
                      detect_t=h.get('t', now), entry_t=None, entry_price=None,
                      peak=1.0, pos=1.0, proceeds=0.0, freerolled=False,
                      status='open', exit_reason=None, marks=[], ohlc_done=0)
            state[key] = st
        # OHLC backfill/replay: true detection-time entry + gap-free path
        candles = [c for c in fetch_ohlc(chain, pair)
                   if c[0] > st['detect_t'] - 3600 and c[4] and c[4] > 0]
        time.sleep(1.5)
        if candles:
            if st['entry_price'] is None:
                c0 = candles[0]
                # entry at close of the candle containing detection;
                # time-stop measured from detection itself
                st['entry_price'] = c0[4]
                st['entry_t'] = st['detect_t']
            for c in candles:
                if c[0] <= st.get('ohlc_done', 0):
                    continue
                if st['status'] == 'open':
                    apply_bar(st, c[4])
                st['ohlc_done'] = c[0]
            # time-stop from true entry
            if (st['status'] == 'open' and not st['freerolled']
                    and (now - st['entry_t']) / 60 >= TS_MIN):
                st['proceeds'] += st['pos'] * (price / st['entry_price'])
                st['pos'] = 0
                st['status'] = 'closed'
                st['exit_reason'] = 'timestop'
        else:
            # no candles (too fresh) — fall back to live marks
            if st['entry_price'] is None:
                st['entry_t'] = now
                st['entry_price'] = price
        r = price / st['entry_price']
        st['peak'] = max(st['peak'], r)
        st['liq_now'] = round(liq)
        st['marks'].append([round(now), price])
        st['marks'] = st['marks'][-200:]
        # live-mark exit check (catches moves since last candle)
        if st['status'] == 'open':
            if not st['freerolled'] and r >= T_TARGET:
                st['proceeds'] += F_SELL * T_TARGET
                st['pos'] -= F_SELL
                st['freerolled'] = True
            if r <= TRAIL * st['peak'] and st['pos'] > 0:
                st['proceeds'] += st['pos'] * r
                st['pos'] = 0
                st['status'] = 'closed'
                st['exit_reason'] = 'trail'
            elif (not st['freerolled'] and st['entry_t']
                  and (now - st['entry_t']) / 60 >= TS_MIN):
                st['proceeds'] += st['pos'] * r
                st['pos'] = 0
                st['status'] = 'closed'
                st['exit_reason'] = 'timestop'
        cur = st['proceeds'] + (st['pos'] * r if st['pos'] > 0 else 0)
        st['ret'] = round(cur - 1, 4)
        st['r_now'] = round(r, 3)

    json.dump(state, open(STATE, 'w'))
    rows = sorted(state.values(), key=lambda s: s.get('entry_t', 0))
    print(f'\n{"name":22s} {"chain":8s} {"status":7s} {"exit":9s} {"FR":3s} {"peak":6s} {"now":6s} {"ret":>7s}')
    for s in rows:
        print(f"{str(s.get('name'))[:20]:22s} {s['chain']:8s} {s['status']:7s} "
              f"{str(s.get('exit_reason')):9s} {str(s['freerolled'])[:1]:3s} "
              f"{s['peak']:5.1f}x {s.get('r_now', 1):5.1f}x {s['ret']*100:+6.0f}%")
    closed = [s['ret'] for s in rows if s['status'] == 'closed']
    if closed:
        wins = sum(1 for v in closed if v > 0)
        print(f'\nclosed: {sum(closed)/len(closed)*100:+.0f}%/trade, win {wins}/{len(closed)}')


if __name__ == '__main__':
    main()
