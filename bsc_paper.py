#!/usr/bin/env python3
"""
bsc_paper.py — paper-trade BSC pools from bsc_flow.jsonl with the §59 stack.

Entry (E25-analog, USD-normalized, reserve-flow version):
  - cumulative net quote inflow >= ENTRY_USD within ENTRY_WIN_MIN of the
    pool's first observed activity (first nonzero d_usd)
  - entry price = price_raw at trigger poll
Exit stack (identical to Solana v2):
  - free-roll: sell FREE_PCT at FREE_MULT x entry
  - abort:     if price < ABORT_MULT x entry after ABORT_MIN minutes -> dump all
  - trail:     after free-roll, exit remainder if price falls to TRAIL_PCT of peak
  - time-stop: dump everything at TSTOP_MIN minutes

Fills at the NEXT poll's price after each signal (realistic next-tick fills).
State: bsc_paper_state.json (file offset, watches, open positions).
Closed trades append to bsc_paper_trades.jsonl.
"""
import json, os, sys

CHAIN = sys.argv[1] if len(sys.argv) > 1 else 'bsc'
VARIANT = sys.argv[2] if len(sys.argv) > 2 else ''
_SUF = f'_{VARIANT}' if VARIANT else ''
FLOW = f'{CHAIN}_flow.jsonl'
STATE = f'{CHAIN}_paper_state{_SUF}.json'
TRADES = f'{CHAIN}_paper_trades{_SUF}.jsonl'

# entry price-confirmation: shadow variant requires price >= this multiple of
# the price at first observed activity before arming (wash-flow filter A/B)
MIN_ENTRY_MULT = 1.05 if VARIANT == 'shadow' else 1.0
# 'replay' variant: fresh state, full-file re-run with the FIXED fill model
if VARIANT == 'replay':
    for fn in (STATE, TRADES):
        if os.path.exists(fn):
            os.remove(fn)

ENTRY_USD = 3000.0
ENTRY_WIN_MIN = 30
FREE_PCT, FREE_MULT = 0.75, 1.5
ABORT_MULT, ABORT_MIN = 1.15, 30
TRAIL_PCT = 0.5
TSTOP_MIN = 120
MAX_AGE_H = 30          # don't enter pools older than this (first-seen basis)
RUG_QRES_FRAC = 0.20    # quote reserve <20% of entry -> LP pulled, position ~worthless

# LP sinks: burn addresses + known BSC lockers. Burned LP is the strongest
# sink (unrecoverable); aligned with evm_watcher.py's LP_SINKS set.
LP_LOCKERS = {'burn_dead': '0x000000000000000000000000000000000000dEaD',
              'burn_zero': '0x0000000000000000000000000000000000000000',
              'pinklock': '0x407993575c91ce7643a4d4cCACc9A98c36eE1BBE',
              'pinklock_v1': '0x7ee058420e5937496F5A2096f04caA7721cf70cc',
              'uncx': '0xC765bddB93b0D1c1A88282BA0fa6B2d00E3e0c83',
              'uncx_alt': '0x7229247bd5cf29fa9b0764aa1568732be024084b'}
BSC_RPC = os.environ.get('BSC_RPC', 'https://bsc-dataseed.binance.org')
LOCKGATE_MIN = 0.95     # 'lockgate' variant: require >=95% LP in known lockers


def lp_lock_fracs(pair):
    """fraction of LP totalSupply held in known lockers (latest block)."""
    import urllib.request
    def _call(data):
        p = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'eth_call',
                        'params': [{'to': pair, 'data': data}, 'latest']}).encode()
        req = urllib.request.Request(BSC_RPC, data=p,
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=12) as r:
            h = json.load(r).get('result', '0x')
        return int(h, 16) if h and h != '0x' else 0
    ts = _call('0x18160ddd')
    if not ts:
        return {}
    out = {}
    for nm, lk in LP_LOCKERS.items():
        out[nm] = round(_call('0x70a08231' + '0' * 24 + lk[2:].lower()) / ts, 4)
    return out


QUOTE_TOKENS = {'0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c',   # WBNB
                '0x55d398326f99059ff775485246999027b3197955'}   # USDT
USDT_ADDR = '0x55d398326f99059ff775485246999027b3197955'


def _tokens_of(pair):
    import urllib.request
    def _call(data):
        p = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'eth_call',
                        'params': [{'to': pair, 'data': data}, 'latest']}).encode()
        req = urllib.request.Request(BSC_RPC, data=p,
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=12) as r:
            h = json.load(r).get('result', '0x')
        return '0x' + h[-40:] if h and h != '0x' else None
    return _call('0x0dfe1681'), _call('0xd21220a7')


def base_token_of(pair):
    """resolve the non-quote side of a V2 pair."""
    t0, t1 = _tokens_of(pair)
    if t0 and t0.lower() in QUOTE_TOKENS:
        return t1
    return t0


def quote_token_of(pair):
    """resolve the quote side of a V2 pair."""
    t0, t1 = _tokens_of(pair)
    if t0 and t0.lower() in QUOTE_TOKENS:
        return t0
    if t1 and t1.lower() in QUOTE_TOKENS:
        return t1
    return None


def goplus_check(token):
    """GoPlus token_security snapshot (free, no key). Log-only enrichment."""
    import urllib.request
    if not token:
        return {}
    url = ('https://api.gopluslabs.io/api/v1/token_security/56'
           f'?contract_addresses={token}')
    req = urllib.request.Request(url, headers={'User-Agent': 'darwin-labs/1.0'})
    with urllib.request.urlopen(req, timeout=20) as r:
        q = json.load(r)
    res = (q.get('result') or {}).get(token.lower()) or {}
    if not res:
        return {}
    ts_raw = res.get('total_supply')
    try:
        ts = float(ts_raw) if ts_raw else 0
    except Exception:
        ts = 0
    tops = []
    for h in (res.get('holders') or [])[:10]:
        try:
            v = float(h.get('percent') or 0)
        except Exception:
            v = 0
        if v > 1.5 and ts:      # some payloads return raw balance, not percent
            v = v / ts
        tops.append(round(v, 4))
    return {'gp_holders': res.get('holder_count'),
            'gp_honeypot': res.get('is_honeypot'),
            'gp_open_source': res.get('is_open_source'),
            'gp_owner_pct': res.get('owner_percent'),
            'gp_top10': tops,
            'gp_top10_sum': round(sum(tops), 4)}


def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE))
    return {'offset': 0, 'watch': {}, 'open': {}, 'entered': []}


def main():
    st = load_state()
    if not os.path.exists(FLOW):
        print('no flow file yet')
        return
    size = os.path.getsize(FLOW)
    if size < st['offset']:          # file rotated
        st['offset'] = 0
    rows = []
    with open(FLOW) as f:
        f.seek(st['offset'])
        for line in f:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
        st['offset'] = f.tell()
    if not rows:
        print('no new rows')
        json.dump(st, open(STATE, 'w'))
        return

    by_pair = {}
    for r in rows:
        by_pair.setdefault(r['pair'], []).append(r)

    now = max(r['t'] for r in rows)
    trades_f = open(TRADES, 'a')

    for pair, rs in by_pair.items():
        rs.sort(key=lambda x: x['t'])
        name = rs[-1].get('name', pair[:10])

        # ---------- open position management ----------
        pos = st['open'].get(pair)
        if pos:
            _manage(st, trades_f, pair, pos, rs)
            continue

        # ---------- entry detection ----------
        w = st['watch'].get(pair)
        if pair in st['entered']:
            continue
        if w is None:
            first = next((r for r in rs if r.get('d_usd')), None)
            if first:
                st['watch'][pair] = {'t0': first['t'], 'cum': 0.0, 'name': name,
                                     'px0': first['price_raw']}
                w = st['watch'][pair]
            else:
                continue
        filled_at = None
        for i, r in enumerate(rs):
            if r['t'] < w['t0']:
                continue
            # armed entry: fill at THIS row's price (next poll after trigger)
            if w.get('armed'):
                st['open'][pair] = dict(
                    name=name, entry_t=r['t'], entry_px=r['price_raw'],
                    peak=1.0, freed=False, frac_left=1.0,
                    entry_flow_usd=w['cum'],
                    entry_qres=r.get('quote_res') or 0)
                st['entered'].append(pair)
                st['watch'].pop(pair, None)
                print(f'ENTRY {name} cum_flow=${w["cum"]:,.0f} '
                      f'px={r["price_raw"]:.3e} (next-poll fill)')
                filled_at = i
                break
            w['cum'] += r.get('d_usd') or 0
            age_min = (r['t'] - w['t0']) / 60
            if age_min > ENTRY_WIN_MIN:
                break
            if w['cum'] >= ENTRY_USD and r['price_raw'] > 0:
                if MIN_ENTRY_MULT > 1.0 and w.get('px0'):
                    if r['price_raw'] / w['px0'] < MIN_ENTRY_MULT:
                        continue   # inflow without price lift: skip (shadow)
                # LP-sink annotation (+ hard gate for lockgate variants).
                # GATE USES PROFESSIONAL LOCKERS ONLY. Self-burn is excluded:
                # at-entry data shows burn_dead 0.95-0.96 is a rug-factory
                # signature (7/8 rugs), while PinkLock separates (3/3 USDT
                # winners; WBNB-quoted PinkLock pools were supply dumps).
                try:
                    locks = lp_lock_fracs(pair)
                except Exception:
                    locks = {}
                if VARIANT in ('lockgate', 'lockgate_usdt'):
                    if not locks:
                        continue        # RPC failed: retry next batch
                    lock_frac = sum(locks.get(k) or 0 for k in
                                    ('pinklock', 'pinklock_v1', 'uncx', 'uncx_alt'))
                    gate_ok = lock_frac >= LOCKGATE_MIN
                    if gate_ok and VARIANT == 'lockgate_usdt':
                        try:
                            gate_ok = (quote_token_of(pair) or '').lower() == USDT_ADDR
                        except Exception:
                            continue    # RPC failed: retry next batch
                    if not gate_ok:
                        st['entered'].append(pair)   # rejected, never retry
                        st['watch'].pop(pair, None)
                        print(f'GATE_REJECT {name} pro_lock={lock_frac:.2f}')
                        # shadow-annotate rejects too (log-only): builds the
                        # dataset to test if GoPlus concentration separates
                        # self-burn winners from mini-dumpers
                        try:
                            gp = goplus_check(base_token_of(pair))
                        except Exception:
                            gp = {}
                        try:
                            rec = {'t': r['t'], 'pair': pair, 'name': name,
                                   'gate_reject': True, 'variant': VARIANT,
                                   'pro_lock': lock_frac, 'lp_lock': locks, **gp}
                            with open(f'{CHAIN}_honeypot_log.jsonl', 'a') as hf:
                                hf.write(json.dumps(rec) + '\n')
                        except Exception:
                            pass
                        break
                w['armed'] = True   # fill on the next poll, not this one
                # §476 shadow honeypot/liveness annotation (log-only, non-blocking)
                try:
                    from bsc_honeypot import check as _hp
                    hp = _hp(pair, is_pair=True)
                    try:
                        gp = goplus_check(base_token_of(pair))
                    except Exception:
                        gp = {}
                    rec = {'t': r['t'], 'pair': pair, 'name': name,
                           'ok': hp.get('ok'), 'tax': hp.get('rpc_roundtrip_tax'),
                           'quote': hp.get('quote'), 'reasons': hp.get('reasons'),
                           'api': hp.get('api'), 'api_error': hp.get('api_error'),
                           'lp_lock': locks, **gp}
                    with open(f'{CHAIN}_honeypot_log.jsonl', 'a') as hf:
                        hf.write(json.dumps(rec) + '\n')
                except Exception:
                    pass
        # manage the remainder of THIS batch after an in-batch fill (replay)
        if filled_at is not None and pair in st['open']:
            _manage(st, trades_f, pair, st['open'][pair], rs[filled_at + 1:])
        # armed watch survives window boundary: fill at first row next run
        # stale watches die
        if pair in st['watch'] and not st['watch'][pair].get('armed') \
                and (now - st['watch'][pair]['t0']) > ENTRY_WIN_MIN * 60:
            st['watch'].pop(pair, None)

    trades_f.close()
    json.dump(st, open(STATE, 'w'))
    n_open = len(st['open'])
    print(f'paper: {len(st["entered"])} entered total, {n_open} open, '
          f'{len(rows)} rows consumed')


def _manage(st, trades_f, pair, pos, rs):
    """Position management over a row batch. Signals arm on one poll,
    fill on the next."""
    for r in rs:
        mult = r['price_raw'] / pos['entry_px'] if pos['entry_px'] else 0
        pos['peak'] = max(pos['peak'], mult)
        age_min = (r['t'] - pos['entry_t']) / 60
        # fills happen at THIS poll (signal came from prior state)
        if pos.get('pend_exit'):
            _close(st, trades_f, pair, pos, mult, r['t'], pos['pend_exit'])
            return
        if pos.get('pend_free'):
            # free-roll fill at actual next-poll multiple; if the LP was pulled
            # before the fill, the sale executes into dust -> ~0
            eq = pos.get('entry_qres') or 0
            pulled = eq and r.get('quote_res') is not None \
                and r['quote_res'] < eq * RUG_QRES_FRAC
            pos['frac_left'] = 1 - FREE_PCT
            pos['freed'] = True
            pos['free_mult'] = 0.0 if pulled else mult
            del pos['pend_free']
            continue
        # signal evaluation -> execute next poll
        # LP-pull guard: quote reserve collapse vs entry => dust pricing, ~total loss
        eq = pos.get('entry_qres') or 0
        if eq and r.get('quote_res') is not None \
                and r['quote_res'] < eq * RUG_QRES_FRAC:
            pos['pend_exit'] = 'rug'
        elif not pos['freed'] and mult >= FREE_MULT:
            pos['pend_free'] = True
        if age_min >= ABORT_MIN and mult < ABORT_MULT and not pos['freed'] and not pos.get('pend_free'):
            pos['pend_exit'] = 'abort'
        elif pos['freed'] and mult <= pos['peak'] * TRAIL_PCT:
            pos['pend_exit'] = 'trail'
        elif age_min >= TSTOP_MIN:
            pos['pend_exit'] = 'tstop'


def _close(st, f, pair, pos, mult, t, reason):
    """Close position at price multiple `mult` for remaining fraction."""
    if reason == 'rug':
        # LP pulled: remainder exits into dust liquidity, realistically ~0
        mult = 0.0
    if pos['freed']:
        # booked FREE_PCT at FREE_MULT, remainder exits at mult
        ret = FREE_PCT * pos.get('free_mult', FREE_MULT) + pos['frac_left'] * mult
    else:
        ret = mult
    rec = dict(name=pos['name'], pair=pair, entry_t=pos['entry_t'], exit_t=t,
               ret=round(ret, 4), exit=reason,
               entry_flow_usd=round(pos['entry_flow_usd'], 0),
               hold_min=round((t - pos['entry_t']) / 60, 1))
    f.write(json.dumps(rec) + '\n')
    del st['open'][pair]
    print(f"EXIT  {pos['name']} ret={ret:.3f}x ({reason}, {rec['hold_min']}m)")


if __name__ == '__main__':
    main()
