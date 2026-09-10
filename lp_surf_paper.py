#!/usr/bin/env python3
"""LP-surf PAPER engine — young-pool in/out rotation, simulated, no real funds.

Strategy (owner spec 2026-09-10): enter a young pool (2-48h old) during its
volume spike, harvest fees briefly, exit on target/tripwire/time-stop, compound
into the next pool. This engine simulates that loop on LIVE pool data so we
measure the true win rate before risking real SOL.

Entry gates (both providers):
  age 2-48h, TVL >= $25k, vol24h/TVL >= 0.5, fee yield >= 3%/day
Exit rules (first hit wins):
  harvest   : est. fees >= +2.0% of deposit
  tripwire  : est. IL <= -3.0% (price ratio r <= ~0.78 or >= ~1.28)
  time-stop : 90 min
Costs: measured fixed 0.002 SOL per full cycle (today's 4 verified re-centers).

Honesty labels: fee accrual is estimated from the pool's trailing fee24h/TVL
rate (not per-bin truth). IL model is provider-specific:
  meteora -> 'ssy_v1' single-sided-Y (SOL-only, wide_arm_v2 shape): upside
             moves cost 0 (position stays pure SOL, just stops earning);
             downside converts Y->X bin-by-bin across the range, value factor
             (1-f) + f*(1-r)/ln(1/r) with f = ln(1/r)/ln(1/RANGE_R_LO).
  raydium -> classic 2*sqrt(r)/(1+r) 50/50 CLMM approximation.
Paper only. PAPER ONLY.

Run: python3 lp_surf_paper.py     (one poll cycle per run)
State: lp_surf_state.json   Log: lp_surf_paper.jsonl
"""
import json, time, urllib.request, urllib.error

STATE_F = 'lp_surf_state.json'
LOG_F = 'lp_surf_paper.jsonl'
MET_API = 'https://dlmm.datapi.meteora.ag'
RAY_API = 'https://api-v3.raydium.io/pools/info/list'
SOL_MINT = 'So11111111111111111111111111111111111111112'

MIN_AGE_H, MAX_AGE_H = 2.0, 48.0
MIN_TVL = 25_000
MIN_VOL_TVL = 0.5
MIN_FEE_DAY = 0.03          # 3%/day
HARVEST_PCT = 0.02
TRIPWIRE_PCT = -0.03
TIMESTOP_MIN = 90
CYCLE_COST_SOL = 0.002      # measured 2026-09-10
# wide_arm_v2 canonical shape: ~68 bins x 0.8% step => range bottom ratio 0.58
# (matches the live MET-SOL position [322..390]); single-sided-Y deposits sit
# below the active bin and convert to X only as price descends through range.
RANGE_R_LO = 0.58
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}


def get(url, retries=2):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(1.5 * (i + 1)); continue
            return None
        except Exception:
            time.sleep(0.7 * (i + 1))
    return None


def log(ev):
    ev['ts'] = time.time()
    with open(LOG_F, 'a') as f:
        f.write(json.dumps(ev) + '\n')


def load_state():
    try:
        return json.load(open(STATE_F))
    except Exception:
        return {'bankroll': 1.0, 'open': None, 'cycles': 0}


def save_state(s):
    json.dump(s, open(STATE_F, 'w'), indent=1)


# ---------- IL models ----------

def il_classic(r):
    """50/50-equivalent CLMM: 2*sqrt(r)/(1+r) - 1. Loses in both directions."""
    return 2 * (r ** 0.5) / (1 + r) - 1 if r > 0 else -1


def il_ssy(r, r_lo=RANGE_R_LO):
    """Single-sided-Y (SOL-only) DLMM value factor minus 1, in SOL terms.

    r >= 1 (token up vs SOL): position stays pure SOL below the range ->
    no IL (it stops earning fees, which the fee estimate does not capture —
    noted in header). r < 1: price descends through the range converting
    Y->X bin by bin; converted fraction f = ln(1/r)/ln(1/r_lo) (uniform
    liquidity in ln-price), average execution factor (1-r)/ln(1/r).
    """
    import math
    if r <= 0:
        return -1
    if r >= 1:
        return 0.0
    f = min(1.0, math.log(1 / r) / math.log(1 / r_lo))
    avg = (1 - r) / math.log(1 / r)
    return (1 - f) + f * avg - 1


def il_for(provider, r):
    if provider == 'meteora':
        return il_ssy(r), 'ssy_v1'
    return il_classic(r), 'classic'


# ---------- candidate scans ----------

def scan_meteora():
    out = []
    now_ms = int(time.time() * 1000)
    for page in (1, 2):
        d = get(f'{MET_API}/pools?sort_key=volume&order_by=desc&page={page}&page_size=50')
        if not d or 'data' not in d:
            break
        for p in d['data']:
            try:
                if p.get('is_blacklisted'):
                    continue
                if (p.get('token_y') or {}).get('address') != SOL_MINT:
                    continue
                age_h = (now_ms - (p.get('created_at') or 0)) / 3600000
                tvl = p.get('tvl') or 0
                f24 = (p.get('fees') or {}).get('24h') or 0
                v24 = (p.get('volume') or {}).get('24h') or 0
                if not (MIN_AGE_H <= age_h <= MAX_AGE_H and tvl >= MIN_TVL
                        and v24 / tvl >= MIN_VOL_TVL and f24 / tvl >= MIN_FEE_DAY):
                    continue
                out.append({'provider': 'meteora', 'pool': p['address'],
                            'pair': p.get('name'), 'age_h': age_h, 'tvl': tvl,
                            'fee_day': f24 / tvl, 'vol_tvl': v24 / tvl})
            except Exception:
                continue
        time.sleep(0.15)
    return out


def scan_raydium():
    out = []
    now = time.time()
    for sf in ('fee24h', 'volume24h'):
        d = get(f'{RAY_API}?poolType=all&poolSortField={sf}&sortType=desc&pageSize=50&page=1')
        if not d or not d.get('success'):
            continue
        for p in d['data']['data']:
            try:
                ot = int(p.get('openTime') or 0)
                if not ot:
                    continue
                age_h = (now - ot) / 3600
                tvl = p.get('tvl') or 0
                day = p.get('day') or {}
                v24, f24 = day.get('volume') or 0, day.get('volumeFee') or 0
                if not (MIN_AGE_H <= age_h <= MAX_AGE_H and tvl >= MIN_TVL
                        and v24 / tvl >= MIN_VOL_TVL and f24 / tvl >= MIN_FEE_DAY):
                    continue
                out.append({'provider': 'raydium', 'pool': p['id'],
                            'pair': f"{p.get('mintA',{}).get('symbol')}/{p.get('mintB',{}).get('symbol')}",
                            'age_h': age_h, 'tvl': tvl, 'fee_day': f24 / tvl,
                            'vol_tvl': v24 / tvl, '_price': p.get('price')})
            except Exception:
                continue
    return out


def current_price(cand):
    if cand['provider'] == 'raydium':
        d = get(f'https://api-v3.raydium.io/pools/key/ids?ids={cand["pool"]}')
        try:
            return float(d['data'][0]['price'])
        except Exception:
            return cand.get('_price')
    d = get(f'{MET_API}/pools/{cand["pool"]}')
    try:
        return float(d['current_price'])
    except Exception:
        return None


def current_fee_day(cand):
    if cand['provider'] == 'raydium':
        d = get(f'https://api-v3.raydium.io/pools/key/ids?ids={cand["pool"]}')
        try:
            p = d['data'][0]
            return (p['day']['volumeFee'] or 0) / (p['tvl'] or 1)
        except Exception:
            return cand['fee_day']
    d = get(f'{MET_API}/pools/{cand["pool"]}')
    try:
        return ((d.get('fees') or {}).get('24h') or 0) / (d.get('tvl') or 1)
    except Exception:
        return cand['fee_day']


# ---------- main cycle ----------

def main():
    st = load_state()
    now = time.time()

    if st['open']:
        o = st['open']
        price = current_price(o)
        fee_day = current_fee_day(o)
        dt_day = (now - o['entry_ts']) / 86400
        o['fees_est'] = fee_day * dt_day                      # fraction of deposit
        r = (price / o['entry_price']) if (price and o['entry_price']) else 1.0
        il, il_model = il_for(o['provider'], r)
        age_min = (now - o['entry_ts']) / 60
        gross = (1 + o['fees_est']) * (1 + il) - 1
        print(f"[open] {o['pair']} ({o['provider']}) {age_min:.0f}min "
              f"r={r:.3f} fees={o['fees_est']*100:+.2f}% il={il*100:+.2f}% "
              f"({il_model}) gross={gross*100:+.2f}%")

        reason = None
        if o['fees_est'] >= HARVEST_PCT:
            reason = 'harvest'
        elif il <= TRIPWIRE_PCT:
            reason = 'tripwire'
        elif age_min >= TIMESTOP_MIN:
            reason = 'timestop'
        if reason:
            net_sol = o['deposit'] * gross - CYCLE_COST_SOL
            st['bankroll'] += net_sol
            st['cycles'] += 1
            log({'kind': 'exit', 'reason': reason, 'pair': o['pair'],
                 'provider': o['provider'], 'pool': o['pool'],
                 'age_min': round(age_min, 1), 'r': round(r, 4),
                 'fees_est': round(o['fees_est'], 5), 'il_est': round(il, 5),
                 'il_model': il_model,
                 'gross_pct': round(gross * 100, 3),
                 'net_sol': round(net_sol, 6), 'bankroll': round(st['bankroll'], 6)})
            print(f"[exit:{reason}] net {net_sol:+.6f} SOL -> bankroll {st['bankroll']:.6f}")
            st['open'] = None
        save_state(st)
        return

    # flat — scan for entry
    cands = scan_meteora() + scan_raydium()
    cands.sort(key=lambda c: -c['fee_day'])
    print(f"[scan] {len(cands)} qualifiers")
    for c in cands[:8]:
        print(f"  {c['provider']:8s} {str(c['pair'])[:22]:22s} ..{c['pool'][-6:]} age {c['age_h']:5.1f}h "
              f"tvl ${c['tvl']/1000:6.0f}k fee/day {c['fee_day']*100:6.2f}% v/t {c['vol_tvl']:.1f}")
    if not cands:
        save_state(st)
        return
    c = cands[0]
    price = current_price(c)
    if not price:
        print('[skip] no price for top candidate')
        save_state(st)
        return
    deposit = st['bankroll']                      # compound: full stack
    st['open'] = {'provider': c['provider'], 'pool': c['pool'], 'pair': c['pair'],
                  'entry_ts': now, 'entry_price': price, 'deposit': deposit,
                  'fees_est': 0.0, 'fee_day_at_entry': c['fee_day']}
    log({'kind': 'enter', 'pair': c['pair'], 'provider': c['provider'],
         'pool': c['pool'], 'price': price, 'deposit': round(deposit, 6),
         'age_h': round(c['age_h'], 1), 'fee_day': round(c['fee_day'], 5)})
    print(f"[enter] {c['pair']} ({c['provider']}) @ {price} deposit {deposit:.4f} SOL (paper)")
    save_state(st)


if __name__ == '__main__':
    main()
