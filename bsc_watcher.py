#!/usr/bin/env python3
"""
bsc_watcher.py — Multicall3 reserve-polling listener for BSC meme pools.

Public BSC RPCs refuse eth_getLogs, but eth_call works. So instead of events
we poll getReserves() for ALL tracked pools in ONE Multicall3 aggregate call
per cycle (~5s). Price = quoteReserve / baseReserve (raw; ratios consistent
per pool). Net quote-reserve deltas between polls = inferred flow.

Also reads the canonical WBNB/USDT pair each cycle for a live BNB/USD price,
so flow thresholds can be USD-denominated like the Solana E25 rule.

Writes bsc_flow.jsonl: one line per pool per poll with price + deltas.
Paper-trading consumes this with the §59 stack (separate scorer).
"""
import json, time, os, urllib.request

RPCS = ('https://bsc-dataseed.binance.org',
        'https://bsc-dataseed1.defibit.io',
        'https://bsc-dataseed1.ninicoin.io')
MC3 = '0xcA11bde05977b3631167028862bE2a173976CA11'
AGGREGATE = 'bce38bd7'  # tryAggregate(false, calls) — tolerant of dead pools
GET_RESERVES = '0902f1ac'
TOKEN0 = '0dfe1681'
TOKEN1 = 'd21220a7'
WBNB = '0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c'
USDT = '0x55d398326f99059ff775485246999027b3197955'
WBNB_USDT_PAIR = '0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE'  # token0 = USDT
QUOTES = {WBNB, USDT}
OUT = 'bsc_flow.jsonl'
STATE = 'bsc_watcher_state.json'
_rpc_i = 0


def rpc(method, params, retries=3, quiet=False):
    global _rpc_i
    for attempt in range(retries + 1):
        url = RPCS[_rpc_i % len(RPCS)]
        try:
            body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method,
                               'params': params}).encode()
            req = urllib.request.Request(url, data=body,
                                         headers={'Content-Type': 'application/json'})
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


def encode_aggregate(calls):
    """calls: [(address, calldata_hex)] -> hex-encoded tryAggregate(false, calls) input.

    tryAggregate(bool requireSuccess, Call[] calls):
      word0 = bool (0), word1 = 0x40 offset to array, then array =
      [length N][N element offsets][tuples]; tuple = [address][0x40][len][data padded].
    """
    n = len(calls)
    tuple_offsets = []
    pos = 32 * n  # first tuple starts after N offset words
    tuples = []
    for addr, data in calls:
        db = bytes.fromhex(data)
        tup = (bytes(12) + bytes.fromhex(addr[2:])          # address
               + (0x40).to_bytes(32, 'big')                  # offset to bytes
               + len(db).to_bytes(32, 'big')                 # bytes length
               + db + bytes((32 - len(db) % 32) % 32))       # padded data
        tuple_offsets.append(pos)
        tuples.append(tup)
        pos += len(tup)
    arr = (n.to_bytes(32, 'big')
           + b''.join(o.to_bytes(32, 'big') for o in tuple_offsets)
           + b''.join(tuples))
    head = (0).to_bytes(32, 'big') + (0x40).to_bytes(32, 'big')  # requireSuccess=false
    return '0x' + AGGREGATE + (head + arr).hex()


def decode_aggregate(ret):
    """tryAggregate returns (bool success, bytes returnData)[] -> list of raw bytes
    for successful calls only (empty bytes placeholder for failed ones)."""
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
    """One Multicall3 call for many pools -> {pair: (r0, r1)}."""
    calls = [(p, GET_RESERVES) for p in pairs]
    ret = rpc('eth_call', [{'to': MC3, 'data': encode_aggregate(calls)}, 'latest'])
    if not ret:
        return {}
    outs = decode_aggregate(ret)
    res = {}
    for p, o in zip(pairs, outs):
        if len(o) >= 64:
            res[p] = (int.from_bytes(o[0:32], 'big'),
                      int.from_bytes(o[32:64], 'big'))
    return res


def token_call(pair, selector):
    """token0()/token1() — no retries on revert (V4 pools simply lack these)."""
    ret = rpc('eth_call', [{'to': pair, 'data': '0x' + selector}, 'latest'],
              retries=0, quiet=True)
    return ('0x' + ret[-40:].lower()) if ret and len(ret) >= 66 else None


def bnb_usd():
    """Live BNB price from the canonical WBNB/USDT pair (token0=USDT, token1=WBNB).
    Both tokens are 18 decimals on BSC, so BNB/USD = r0 / r1."""
    r = get_reserves_batch([WBNB_USDT_PAIR])
    for k, (r0, r1) in r.items():
        return r0 / r1 if r1 else None   # USDT per WBNB
    return None


def main():
    now = time.time()
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    # pool set: qualified BSC pairs from scan (24h window) — orientation cached
    pools = {}
    if os.path.exists('xchain_scan.jsonl'):
        for line in open('xchain_scan.jsonl'):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if (r.get('chain') == 'bsc' and r.get('pair')
                    and now - r.get('t', now) < 24 * 3600
                    and (r.get('liq_usd') or 0) >= 10_000
                    and (r.get('buys_h1') or 0) >= 20):
                pools[r['pair'].lower()] = r.get('name')
    if not pools:
        print('no pools to watch')
        return
    t0map = state.setdefault('token0', {})
    for p in list(pools):
        if p not in t0map:
            z = token_call(p, TOKEN0)
            if z is None:                # not a V2-style pool (e.g. V4) -> drop
                del pools[p]
                continue
            if z not in QUOTES:
                z1 = token_call(p, TOKEN1)
                if z1 not in QUOTES:     # quoted in an unknown token -> drop
                    del pools[p]
                    continue
            t0map[p] = z
            time.sleep(0.2)
        elif t0map[p] not in QUOTES:
            # cached orientation with unknown token0: verify token1 once
            z1m = state.setdefault('token1', {})
            if p not in z1m:
                z1m[p] = token_call(p, TOKEN1)
                time.sleep(0.2)
            if z1m.get(p) not in QUOTES:
                del pools[p]
    px_bnb = bnb_usd()
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
            is_wb = (quote_addr == WBNB)
            quote_usd = px_bnb if is_wb else 1.0   # WBNB->BNB price, USDT->1
            price = quote_r / base_r
            pr = prev.get(p)
            d_quote = (quote_r - pr[1]) if pr else 0
            # quote side is always 18-dec (WBNB/USDT) -> d_usd is exact.
            # price_usd assumes 18-dec base; use price RATIOS for multiples.
            d_usd = d_quote * (quote_usd or 0) / 1e18
            rec = dict(t=now, pair=p, name=pools[p], price_raw=price,
                       price_usd=price * (quote_usd or 0) / 1e18,
                       quote='WBNB' if is_wb else 'USDT',
                       quote_res=quote_r, base_res=base_r,
                       d_quote=d_quote, d_usd=d_usd, bnb_usd=px_bnb)
            f.write(json.dumps(rec) + '\n')
            prev[p] = (base_r, quote_r)
            n += 1
    json.dump(state, open(STATE, 'w'))
    print(f'pools watched: {len(pools)}, reserves read: {len(reserves)}, '
          f'BNB=${px_bnb and round(px_bnb, 1)} -> {OUT}')


if __name__ == '__main__':
    main()
