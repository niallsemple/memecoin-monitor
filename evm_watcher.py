#!/usr/bin/env python3
"""
evm_watcher.py — chain-configurable Multicall3 reserve-polling listener.

Public EVM RPCs refuse eth_getLogs, but eth_call works. Polls getReserves()
for all tracked pools in ONE Multicall3 tryAggregate(false, calls) per cycle.
Price = quoteReserve / baseReserve (raw; ratios consistent per pool).
Net quote-reserve deltas between polls = inferred flow, USD-denominated via
a canonical quote/USD reference pair each cycle.

Usage: python3 evm_watcher.py <chain>     (bsc | base)
Writes <chain>_flow.jsonl; state in <chain>_watcher_state.json.
"""
import json, time, os, sys, urllib.request

MC3 = '0xcA11bde05977b3631167028862bE2a173976CA11'   # same on BSC + Base
TRY_AGG = 'bce38bd7'   # tryAggregate(false, calls)
GET_RESERVES = '0902f1ac'
TOKEN0 = '0dfe1681'
TOKEN1 = 'd21220a7'
TOTAL_SUPPLY = '18160ddd'
BALANCE_OF = '70a08231'   # + 32-byte address

# LP sink addresses: burn + known lockers per chain
DEAD = '000000000000000000000000000000000000dead'
ZERO = '0000000000000000000000000000000000000000'
LP_SINKS = {
    'bsc': [DEAD, ZERO,
            '407993575c91ce7643a4d4cCACc9A98c36eE1BBE'.lower(),   # PinkLock02 BSC
            '7ee058420e5937496f5a2096f04caa7721cf70cc',           # PinkLock v1 BSC
            '7229247bd5cf29fa9b0764aa1568732be024084b'],          # UNCX UniV2 locker BSC
    'base': [DEAD, ZERO,
             'dd6e31a046b828cbbafb939c2a394629aff8bbdc',          # PinkLock V2 Base
             'c4e637d37113192f4f1f060daebd7758de7f4131'],         # UNCX UniV2 locker Base
}
MIN_LP_SUNK = 0.5   # require >=50% of LP tokens burned/locked to watch a pool

CHAINS = {
    'bsc': dict(
        rpcs=('https://bsc-dataseed.binance.org',
              'https://bsc-dataseed1.defibit.io',
              'https://bsc-dataseed1.ninicoin.io'),
        quotes={'0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c':
                ('WBNB', 18, 'native'),
                '0x55d398326f99059ff775485246999027b3197955':
                ('USDT', 18, 'usd')},
        ref_pair='0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE',  # USDT/WBNB
        ref_token0_is_usd=True,     # token0=USDT -> native price = r0/r1
        ref_dec=(18, 18),
    ),
    'base': dict(
        rpcs=('https://mainnet.base.org',
              'https://base-rpc.publicnode.com',
              'https://base.drpc.org'),
        quotes={'0x4200000000000000000000000000000000000006':
                ('WETH', 18, 'native'),
                '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913':
                ('USDC', 6, 'usd')},
        ref_pair='0x88A43bbDF9D098eEC7bCEda4e2494615dfD9bB9C',  # UniV2 WETH/USDC
        ref_token0_is_usd=False,    # token0=WETH(18), token1=USDC(6)
        ref_dec=(18, 6),
    ),
}

_rpc_i = 0
CFG = None


def rpc(method, params, retries=3, quiet=False):
    global _rpc_i
    for attempt in range(retries + 1):
        url = CFG['rpcs'][_rpc_i % len(CFG['rpcs'])]
        try:
            body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method,
                               'params': params}).encode()
            req = urllib.request.Request(url, data=body,
                                         headers={'Content-Type': 'application/json',
                                                  'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'})
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.load(r)
            if 'error' in d:
                raise RuntimeError(d['error'])
            return d.get('result')
        except Exception as e:
            _rpc_i += 1
            if attempt == retries:
                if not quiet:
                    print(f'RPC fail {method}: {e}')
                return None
            time.sleep(0.8)


def encode_try_aggregate(calls):
    n = len(calls)
    tuple_offsets, pos, tuples = [], 32 * n, []
    for addr, data in calls:
        db = bytes.fromhex(data)
        tup = (bytes(12) + bytes.fromhex(addr[2:])
               + (0x40).to_bytes(32, 'big')
               + len(db).to_bytes(32, 'big')
               + db + bytes((32 - len(db) % 32) % 32))
        tuple_offsets.append(pos)
        tuples.append(tup)
        pos += len(tup)
    arr = (n.to_bytes(32, 'big')
           + b''.join(o.to_bytes(32, 'big') for o in tuple_offsets)
           + b''.join(tuples))
    head = (0).to_bytes(32, 'big') + (0x40).to_bytes(32, 'big')
    return '0x' + TRY_AGG + (head + arr).hex()


def decode_results(ret):
    data = bytes.fromhex(ret[2:])
    if len(data) < 64:
        return []
    arr_off = int.from_bytes(data[0:32], 'big')
    n = int.from_bytes(data[arr_off:arr_off + 32], 'big')
    outs = []
    for i in range(n):
        eoff = arr_off + 32 + int.from_bytes(data[arr_off + 32 + i * 32:
                                                 arr_off + 64 + i * 32], 'big')
        success = int.from_bytes(data[eoff:eoff + 32], 'big')
        boff = eoff + int.from_bytes(data[eoff + 32:eoff + 64], 'big')
        ln = int.from_bytes(data[boff:boff + 32], 'big')
        outs.append(data[boff + 32:boff + 32 + ln] if success else b'')
    return outs


def get_reserves_batch(pairs):
    calls = [(p, GET_RESERVES) for p in pairs]
    ret = rpc('eth_call', [{'to': MC3, 'data': encode_try_aggregate(calls)}, 'latest'])
    if not ret:
        return {}
    outs = decode_results(ret)
    res = {}
    for p, o in zip(pairs, outs):
        if len(o) >= 64:
            res[p] = (int.from_bytes(o[0:32], 'big'),
                      int.from_bytes(o[32:64], 'big'))
    return res


def lp_sunk_batch(pairs, chain):
    """One multicall: per pair -> totalSupply + balanceOf(each LP sink).
    -> {pair: sunk_ratio}. Works on any fresh pool instantly (plain eth_call)."""
    sinks = LP_SINKS.get(chain, [DEAD, ZERO])
    calls = []
    for p in pairs:
        calls.append((p, TOTAL_SUPPLY))
        for s in sinks:
            calls.append((p, BALANCE_OF + '0' * 24 + s))
    ret = rpc('eth_call', [{'to': MC3, 'data': encode_try_aggregate(calls)}, 'latest'])
    if not ret:
        return {}
    outs = decode_results(ret)
    res = {}
    stride = 1 + len(sinks)
    for i, p in enumerate(pairs):
        ts_o = outs[i * stride]
        if len(ts_o) < 32:
            continue
        ts = int.from_bytes(ts_o[:32], 'big')
        if not ts:
            continue
        sunk = 0
        for j in range(len(sinks)):
            o = outs[i * stride + 1 + j]
            if len(o) >= 32:
                sunk += int.from_bytes(o[:32], 'big')
        res[p] = sunk / ts
    return res


def token_call(pair, selector):
    ret = rpc('eth_call', [{'to': pair, 'data': '0x' + selector}, 'latest'],
              retries=0, quiet=True)
    return ('0x' + ret[-40:].lower()) if ret and len(ret) >= 66 else None


def native_usd():
    """Native token (BNB/ETH) USD price from the canonical reference pair,
    decimal-corrected via ref_dec = (token0_dec, token1_dec)."""
    d0, d1 = CFG.get('ref_dec', (18, 18))
    r = get_reserves_batch([CFG['ref_pair']])
    for k, (r0, r1) in r.items():
        if CFG.get('ref_token0_is_usd'):
            return (r0 / 10 ** d0) / (r1 / 10 ** d1) if r1 else None
        return (r1 / 10 ** d1) / (r0 / 10 ** d0) if r0 else None
    return None


def main(chain='bsc'):
    global CFG
    CFG = CHAINS[chain]
    OUT = f'{chain}_flow.jsonl'
    STATE = f'{chain}_watcher_state.json'
    now = time.time()
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}

    pools = {}
    if os.path.exists('xchain_scan.jsonl'):
        for line in open('xchain_scan.jsonl'):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if (r.get('chain') == chain and r.get('pair')
                    and now - r.get('t', now) < 24 * 3600
                    and (r.get('liq_usd') or 0) >= 10_000
                    and (r.get('buys_h1') or 0) >= 20):
                pools[r['pair'].lower()] = r.get('name')
    if not pools:
        print(f'{chain}: no pools to watch')
        return

    QUOTES = set(CFG['quotes'])
    t0map = state.setdefault('token0', {})
    for p in list(pools):
        if p not in t0map:
            z = token_call(p, TOKEN0)
            if z is None:
                del pools[p]
                continue
            if z not in QUOTES:
                z1 = token_call(p, TOKEN1)
                if z1 not in QUOTES:
                    del pools[p]
                    continue
                state.setdefault('token1', {})[p] = z1
            t0map[p] = z
            time.sleep(0.2)
        elif t0map[p] not in QUOTES:
            z1m = state.setdefault('token1', {})
            if p not in z1m:
                z1m[p] = token_call(p, TOKEN1)
                time.sleep(0.2)
            if z1m.get(p) not in QUOTES:
                del pools[p]

    px_native = native_usd()
    # LP-sink gate: drop pools with <50% LP burned/locked (rug filter, §64).
    # Re-check failures older than 10 min: teams sometimes lock AFTER launch.
    lpmap = state.setdefault('lp_sunk', {})
    lpts = state.setdefault('lp_sunk_t', {})
    newp = [p for p in pools if p not in lpmap]
    recheck = [p for p in pools if (lpmap.get(p) or 0) < MIN_LP_SUNK
               and now - lpts.get(p, 0) > 600]
    for i in range(0, len(newp) + len(recheck), 100):
        batch = (newp + recheck)[i:i + 100]
        if not batch:
            continue
        lpmap.update(lp_sunk_batch(batch, chain))
        for p in batch:
            lpts[p] = now
    for p in list(pools):
        if (lpmap.get(p) or 0) < MIN_LP_SUNK:
            del pools[p]
    reserves = get_reserves_batch(sorted(pools.keys()))
    prev = state.setdefault('prev', {})
    n = 0
    with open(OUT, 'a') as f:
        for p, (r0, r1) in reserves.items():
            z = t0map.get(p)
            if not z:
                continue
            base_r, quote_r = (r0, r1) if z not in QUOTES else (r1, r0)
            if not base_r:
                continue
            quote_addr = z if z in QUOTES else state.get('token1', {}).get(p)
            qsym, qdec, qkind = CFG['quotes'].get(quote_addr, ('?', 18, 'usd'))
            quote_usd = px_native if qkind == 'native' else 1.0
            price = quote_r / base_r
            pr = prev.get(p)
            d_quote = (quote_r - pr[1]) if pr else 0
            # quote decimals handled: d_usd exact; price_usd assumes 18-dec base
            d_usd = d_quote * (quote_usd or 0) / 10 ** qdec
            rec = dict(t=now, pair=p, name=pools[p], price_raw=price,
                       price_usd=price * (quote_usd or 0) / 10 ** qdec,
                       quote=qsym, quote_res=quote_r, base_res=base_r,
                       d_quote=d_quote, d_usd=d_usd, native_usd=px_native,
                       chain=chain)
            f.write(json.dumps(rec) + '\n')
            prev[p] = (base_r, quote_r)
            n += 1
    json.dump(state, open(STATE, 'w'))
    sym = 'BNB' if chain == 'bsc' else 'ETH'
    print(f'{chain}: pools watched: {len(pools)}, reserves read: {len(reserves)}, '
          f'{sym}=${px_native and round(px_native, 1)} -> {OUT} '
          f'(lp-gated: {len(lpmap)} known)')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'bsc')
