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
                    entry_flow_usd=w['cum'])
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
                w['armed'] = True   # fill on the next poll, not this one
                # §476 shadow honeypot/liveness annotation (log-only, non-blocking)
                try:
                    from bsc_honeypot import check as _hp
                    hp = _hp(pair, is_pair=True)
                    rec = {'t': r['t'], 'pair': pair, 'name': name,
                           'ok': hp.get('ok'), 'tax': hp.get('rpc_roundtrip_tax'),
                           'quote': hp.get('quote'), 'reasons': hp.get('reasons'),
                           'api': hp.get('api'), 'api_error': hp.get('api_error')}
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
            # free-roll fill at actual next-poll multiple
            pos['frac_left'] = 1 - FREE_PCT
            pos['freed'] = True
            pos['free_mult'] = mult
            del pos['pend_free']
            continue
        # signal evaluation -> execute next poll
        if not pos['freed'] and mult >= FREE_MULT:
            pos['pend_free'] = True
        if age_min >= ABORT_MIN and mult < ABORT_MULT and not pos['freed'] and not pos.get('pend_free'):
            pos['pend_exit'] = 'abort'
        elif pos['freed'] and mult <= pos['peak'] * TRAIL_PCT:
            pos['pend_exit'] = 'trail'
        elif age_min >= TSTOP_MIN:
            pos['pend_exit'] = 'tstop'


def _close(st, f, pair, pos, mult, t, reason):
    """Close position at price multiple `mult` for remaining fraction."""
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
