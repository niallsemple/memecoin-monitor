#!/usr/bin/env python3
"""lp_surf_live.py — REAL-SOL compounding LP-surf engine (Meteora DLMM only).

Owner directive 2026-09-11: 0.5 SOL starting bankroll, compounding,
"see how long it can go". Paper-proven ruleset from lp_surf_paper.py:

  scan    : Meteora DLMM pools, age 2-48h, TVL >= $25k, vol24h/TVL >= 0.5,
            fee24h/TVL >= 3%/day, not blacklisted, not on cooldown
  enter   : top candidate by fee_day; momentum guard (wait 20s, skip if
            price drops > 0.5%); single-sided Y (SOL) at 56% width below active
  exits   : harvest  feeY_accrued/deposit >= +2.0%   (feeY = real SOL fees)
            tripwire est. IL (ssy_v1) <= -3.0% on live price ratio
            timestop 90 min
  after   : exit -> sweep_to_sol -> measure wallet delta -> compound bankroll

Safety rails:
  - STOP_LIVE_TRADING file: no new entries (open position still managed)
  - bankroll cap: deposit = min(bankroll, wallet_SOL - RESERVE_SOL);
    RESERVE protects the MET-SOL cell + rent + gas
  - cooldown 6h per pool after tripwire or any exit with r < 1
  - 3 consecutive entry failures -> halt entries until state file cleared
  - strategy_tag 'lp_surf': guardian will NOT re-center these (its emergency
    exit on blacklist/TVL-collapse still applies — wanted)
"""
import json, os, subprocess, sys, time

MON = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, MON)
from lp_surf_paper import (scan_meteora, current_price, current_fee_day,
                           il_ssy, MIN_AGE_H, MAX_AGE_H, MIN_TVL,
                           MIN_VOL_TVL, MIN_FEE_DAY)

STATE_F = os.path.join(MON, 'surf_live_state.json')
LOG_F = os.path.join(MON, 'surf_live.jsonl')
KILL_F = os.path.join(MON, 'STOP_LIVE_TRADING')
BUNDLE = os.path.join(MON, 'lp_exec', 'meteora_lp.bundle.cjs')
SWEEP = os.path.join(MON, 'sweep_to_sol.py')
WALLET = 'CQcKkSee9bdHZ1bejYFDUXVtodbfKHe2KSx6AaAnTW2K'
HELIUS_KEY = open(os.path.join(MON, 'helius_key.txt')).read().strip()
RPC = f'https://mainnet.helius-rpc.com/?api-key={HELIUS_KEY}'

HARVEST_PCT = 0.02
TRIPWIRE_PCT = -0.03
TIME_STOP_MIN = 90
TRIPWIRE_COOLDOWN_H = 6.0
WIDTH_PCT = 0.56
START_BANKROLL = 0.5
RESERVE_SOL = 6.2          # never touch: MET-SOL cell + rent + gas cushion
MIN_DEPOSIT = 0.05
MAX_ENTRY_FAILS = 3
POS_FILE = os.path.join(MON, 'lp_positions.json')


def log(ev):
    ev = dict(ev); ev['ts'] = time.time()
    with open(LOG_F, 'a') as f:
        f.write(json.dumps(ev) + '\n')
    print(f"[{ev.get('kind')}] {json.dumps({k: v for k, v in ev.items() if k not in ('kind', 'ts')})[:300]}")


def load_state():
    if os.path.exists(STATE_F):
        return json.load(open(STATE_F))
    return {'bankroll': START_BANKROLL, 'started_with': START_BANKROLL,
            'open': None, 'cooldowns': {}, 'cycles': 0, 'wins': 0, 'losses': 0,
            'entry_fails': 0, 'halted': False}


def save_state(s):
    json.dump(s, open(STATE_F, 'w'), indent=1)


def wallet_sol():
    import urllib.request
    body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'getBalance',
                       'params': [WALLET]}).encode()
    req = urllib.request.Request(RPC, data=body, headers={'Content-Type': 'application/json'})
    d = json.load(urllib.request.urlopen(req, timeout=20))
    return d['result']['value'] / 1e9


def run_bundle(*args, timeout=180):
    r = subprocess.run(['node', BUNDLE, *args], capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr)


def position_status(pool):
    """Ground-truth fee/bin read for our open position in `pool`."""
    rc, out = run_bundle('statusjson')
    if rc != 0:
        return None
    try:
        arr = json.loads([l for l in out.splitlines() if l.strip().startswith('[')][-1])
    except Exception:
        return None
    for p in arr:
        if p.get('pool') == pool and not p.get('error'):
            return p
    return None


def pool_x_decimals(pool):
    import urllib.request
    try:
        req = urllib.request.Request(f'https://dlmm.datapi.meteora.ag/pools/{pool}',
                                     headers={'User-Agent': 'curl/8.0'})
        d = json.load(urllib.request.urlopen(req, timeout=20))
        return int((d.get('token_x') or {}).get('decimals'))
    except Exception:
        return None


def sweep():
    r = subprocess.run([sys.executable, SWEEP], capture_output=True, text=True, timeout=300)
    return r.returncode


def tx_sol_delta(sig):
    """Wallet SOL delta for one confirmed tx via Helius getTransaction."""
    try:
        import urllib.request
        rpc_url = f'https://mainnet.helius-rpc.com/?api-key={HELIUS_KEY}'
        req = urllib.request.Request(rpc_url, data=json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "getTransaction",
            "params": [sig, {"encoding": "json", "maxSupportedTransactionVersion": 0}]
        }).encode(), headers={'Content-Type': 'application/json'})
        res = json.load(urllib.request.urlopen(req, timeout=30)).get('result')
        if not res: return None
        keys = [k if isinstance(k, str) else k['pubkey'] for k in res['transaction']['message']['accountKeys']]
        i = keys.index(WALLET)
        return (res['meta']['postBalances'][i] - res['meta']['preBalances'][i]) / 1e9
    except Exception as e:
        print(f"tx_sol_delta err {sig[:12]}: {e}")
        return None


def reconcile_exit_onchain(o):
    """Sum wallet SOL deltas across this position's exit + add txs.
    Returns (returned, net) or None. Ground truth when wallet before/after
    measurement is polluted by concurrent guardian flows."""
    try:
        pos = json.load(open(POS_FILE))['positions']
    except Exception:
        return None
    rec = None
    for p in pos:
        if p.get('pool') == o['pool'] and p.get('status') == 'exited' and p.get('exit_sigs'):
            if rec is None or p.get('exit_ts', 0) > rec.get('exit_ts', 0):
                rec = p
    if not rec: return None
    total = 0.0
    for s in rec['exit_sigs'] + [rec.get('add_sig')]:
        if not s: return None
        d = tx_sol_delta(s)
        if d is None: return None
        total += d
    net = total  # exit deltas + add delta (add delta includes the liquidity deposit)
    returned = o['deposit'] + net
    return returned, net


def do_exit(st, why, gross_hint=None):
    o = st['open']
    before = wallet_sol()
    rc, out = run_bundle('exit', o['pool'])
    if rc != 0 or 'EXITED' not in out:
        log({'kind': 'exit_fail', 'pool': o['pool'], 'why': why, 'rc': rc, 'out': out[-200:]})
        return False
    time.sleep(3)
    sweep_rc = sweep()
    time.sleep(2)
    after = wallet_sol()
    returned = after - before
    # sanity: a successful EXIT can lose to fees/IL but never returns <= 0
    # (position is >= mostly SOL). <=0 means the wallet read was polluted by
    # concurrent guardian/sweep flows -> retry, then reconcile on-chain.
    if returned <= 0:
        for _ in range(3):
            time.sleep(10)
            after2 = wallet_sol()
            returned = after2 - before
            if returned > 0: break
    reconciled = False
    if returned <= 0:
        rec = reconcile_exit_onchain(o)
        if rec:
            returned, net_onchain = rec
            reconciled = True
            log({'kind': 'exit_reconciled', 'pool': o['pool'], 'returned': round(returned, 6), 'net': round(net_onchain, 6)})
        else:
            log({'kind': 'exit_measure_fail', 'pool': o['pool'], 'why': why,
                 'note': 'EXITED but wallet delta unreadable; bankroll preserved, halting for manual review'})
            st['open'] = None
            st['halted'] = True
            save_state(st)
            return True
    # reconciled net already includes entry rent/fees via the add-tx delta;
    # the wallet-delta path needs entry_cost (rent+fees) as the true basis.
    cost = o['deposit'] if reconciled else o.get('entry_cost', o['deposit'])
    net = returned - cost
    st['bankroll'] = st['bankroll'] - cost + returned
    st['cycles'] += 1
    if net > 0: st['wins'] += 1
    else: st['losses'] += 1
    log({'kind': 'exit', 'why': why, 'pool': o['pool'], 'pair': o['pair'],
         'mins': round((time.time() - o['entry_ts']) / 60, 1),
         'deposit': round(o['deposit'], 4), 'returned': round(returned, 6),
         'net': round(net, 6), 'bankroll': round(st['bankroll'], 6),
         'r': round(o.get('last_r', 1), 4), 'sweep_rc': sweep_rc})
    # cooldown on tripwire or any down-r exit (pool-specific)
    if why == 'tripwire' or o.get('last_r', 1) < 1:
        st['cooldowns'][o['pool']] = time.time() + TRIPWIRE_COOLDOWN_H * 3600
        log({'kind': 'cooldown', 'pool': o['pool'], 'hours': TRIPWIRE_COOLDOWN_H, 'why': why})
    st['open'] = None
    save_state(st)
    return True


def main():
    st = load_state()
    now = time.time()

    # --- manage open position ---
    if st.get('open'):
        o = st['open']
        ps = position_status(o['pool'])
        price = current_price(o)
        r = (price / o['entry_price']) if (price and o['entry_price']) else o.get('last_r', 1.0)
        o['last_r'] = r
        il = il_ssy(r)
        fee_y_sol = (int(ps['feeY_lamports']) / 1e9) if ps else o.get('fee_sol_last', 0.0)
        # X-side (token) fees, valued at current pool price — baton-type pools
        # accrue mostly in X when price rides the top of the band
        fee_x_sol = 0.0
        if ps and int(ps.get('feeX_lamports') or 0) > 0 and o.get('x_decimals') and price:
            fee_x_sol = int(ps['feeX_lamports']) / (10 ** o['x_decimals']) * price
        fee_sol = fee_y_sol + fee_x_sol
        if ps: o['fee_sol_last'] = fee_sol
        fee_pct = fee_sol / o['deposit'] if o['deposit'] else 0
        age_min = (now - o['entry_ts']) / 60
        in_range = ps.get('inRange') if ps else None
        # above-range abort: r>1.10 for 3 consecutive polls means the position
        # is pure SOL earning ~nothing (cycles 1-2 evidence: fees stall ~+0.3%).
        # Exit early, free the bankroll for a working pool. No cooldown — the
        # pool didn't fail, price just ran through the top of the band.
        o['above_streak'] = (o.get('above_streak', 0) + 1) if r > 1.10 else 0
        save_state(st)
        print(f"[open] {o['pair']} {age_min:.0f}min r={r:.3f} fees={fee_sol:.5f}SOL ({fee_pct*100:+.2f}%) "
              f"[Y={fee_y_sol:.5f} X={fee_x_sol:.5f}] il={il*100:+.2f}% inRange={in_range} "
              f"above_streak={o['above_streak']} bankroll={st['bankroll']:.4f}")
        if fee_pct >= HARVEST_PCT:
            do_exit(st, 'harvest')
        elif il <= TRIPWIRE_PCT:
            do_exit(st, 'tripwire')
        elif o['above_streak'] >= 3 and age_min >= 10:
            do_exit(st, 'above_range_abort')
        elif age_min >= TIME_STOP_MIN:
            do_exit(st, 'timestop')
        return

    # --- flat: consider a new entry ---
    if os.path.exists(KILL_F):
        print('[flat] STOP_LIVE_TRADING present — no entries'); return
    if st.get('halted'):
        print('[flat] halted (entry failures) — clear state to resume'); return
    if st['bankroll'] < MIN_DEPOSIT:
        print(f"[flat] bankroll {st['bankroll']:.4f} < min deposit — game over"); return

    cands = scan_meteora()
    st['cooldowns'] = {k: v for k, v in st.get('cooldowns', {}).items() if v > now}
    cands = [c for c in cands if c['pool'] not in st['cooldowns']]
    if not cands:
        print('[scan] no live qualifiers'); save_state(st); return
    cands.sort(key=lambda c: -c['fee_day'])
    c = cands[0]
    print(f"[scan] top: {c['pair']} ..{c['pool'][-6:]} age {c['age_h']:.1f}h "
          f"tvl ${c['tvl']/1e3:.0f}k fee/day {c['fee_day']*100:.1f}% v/t {c['vol_tvl']:.1f}")

    # momentum guard
    p1 = current_price(c)
    if not p1:
        print('[skip] no price'); return
    time.sleep(20)
    p2 = current_price(c)
    if not p2:
        print('[skip] no price re-read'); return
    mom = p2 / p1 - 1
    if mom < -0.005:
        log({'kind': 'skip_momentum', 'pair': c['pair'], 'mom': round(mom, 5)})
        save_state(st); return

    # sizing: compound bankroll, capped by wallet minus reserve
    try:
        ws = wallet_sol()
    except Exception as e:
        print(f'[skip] wallet read failed: {e}'); return
    deposit = round(min(st['bankroll'], ws - RESERVE_SOL), 4)
    if deposit < MIN_DEPOSIT:
        print(f'[skip] deposit {deposit} < min (wallet {ws:.4f}, reserve {RESERVE_SOL})'); return

    fee_day = current_fee_day(c)
    if os.environ.get('SURF_DRYRUN'):
        print(f"[dryrun] WOULD add {c['pair']} ..{c['pool'][-6:]} deposit={deposit} width={WIDTH_PCT} "
              f"price={p2} fee_day={fee_day:.4f} mom={mom:+.5f}")
        return
    rc, out = run_bundle('add', c['pool'], str(deposit), str(WIDTH_PCT), 'lp_surf')
    if rc != 0 or 'ADDED' not in out:
        st['entry_fails'] = st.get('entry_fails', 0) + 1
        if st['entry_fails'] >= MAX_ENTRY_FAILS: st['halted'] = True
        log({'kind': 'enter_fail', 'pair': c['pair'], 'rc': rc, 'out': out[-200:],
             'fails': st['entry_fails']})
        save_state(st); return
    st['entry_fails'] = 0
    st['open'] = {'provider': 'meteora', 'pool': c['pool'], 'pair': c['pair'],
                  'entry_ts': time.time(), 'entry_price': p2, 'deposit': deposit,
                  'fee_day_at_entry': fee_day, 'last_r': 1.0, 'fee_sol_last': 0.0,
                  'x_decimals': pool_x_decimals(c['pool'])}
    # true entry cost incl. position rent + tx fees, from the add tx itself
    try:
        time.sleep(5)
        pos = json.load(open(POS_FILE))['positions']
        rec = max((p for p in pos if p.get('pool') == c['pool'] and p.get('add_sig')),
                  key=lambda p: p.get('ts', 0), default=None)
        if rec:
            d = tx_sol_delta(rec['add_sig'])
            if d is not None and d < 0:
                st['open']['entry_cost'] = round(-d, 6)
    except Exception as e:
        print(f'[warn] entry_cost read failed: {e}')
    save_state(st)
    log({'kind': 'enter', 'pair': c['pair'], 'pool': c['pool'], 'price': p2,
         'deposit': deposit, 'fee_day': round(fee_day, 4), 'mom': round(mom, 5)})


if __name__ == '__main__':
    main()
