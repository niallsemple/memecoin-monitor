#!/usr/bin/env python3
"""
bsc_listener.py — trade-level BSC pool listener (EVM precision for xchain).

Polls eth_getLogs for PancakeSwap V2 Swap events across all tracked BSC pools
(from xchain_scan.jsonl hits, tracked for 24h from detection). Decodes each
swap to a per-trade price (quote per base) and side; writes trades to
bsc_trades.jsonl in the mfg_trades.jsonl schema so the §59 paper-trader stack
can consume them unchanged.

V2 Swap event: topic0 = keccak("Swap(address,uint256,uint256,uint256,address)")
data = amount0In, amount1In, amount0Out, amount1Out (uint256 x4)
Buy  = quote in, base out.  Sell = base in, quote out.
Price = quote_amount / base_amount (raw decimals cancel in ratios).

Public BSC RPC: https://bsc-dataseed.binance.org (eth_getLogs, batch addrs).
"""
import json, time, os, urllib.request, urllib.error

RPCS = ('https://bsc-dataseed.binance.org',
        'https://bsc-dataseed1.defibit.io',
        'https://bsc-dataseed1.ninicoin.io')
SCAN = 'xchain_scan.jsonl'
OUT = 'bsc_trades.jsonl'
STATE = 'bsc_listener_state.json'
SWAP_V2 = '0xd78ad95fa46c994b6551d0a85ebcfd42c61f2b0d97a4c1f26b2b7c1accd2fc17'
WBNB = '0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c'
USDT = '0x55d398326f99059ff775485246999027b3197955'
QUOTES = {WBNB, USDT}
TRACK_H = 24
_rpc_i = 0


def rpc(method, params, retries=2):
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
                print(f'RPC fail {method}: {e}')
                return None
            time.sleep(1)


def tracked_pools(now):
    """Qualified BSC pairs (activity floor) from scan, tracked TRACK_H hours."""
    pools = {}
    if not os.path.exists(SCAN):
        return pools
    for line in open(SCAN):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get('chain') != 'bsc' or not r.get('pair'):
            continue
        if now - r.get('t', now) > TRACK_H * 3600:
            continue
        if (r.get('liq_usd') or 0) < 15_000 or (r.get('buys_h1') or 0) < 30:
            continue
        pools[r['pair'].lower()] = r   # latest scan record wins
    return pools


def pool_token0(pair):
    """eth_call token0() -> address."""
    res = rpc('eth_call', [{'to': pair, 'data': '0x0dfe1681'}, 'latest'])
    if res and len(res) >= 66:
        return '0x' + res[-40:].lower()
    return None


def decode_swap(log, base_is_token0):
    """Return (side, quote_amt, base_amt) raw integer amounts or None."""
    data = log.get('data', '0x')[2:]
    if len(data) < 256:
        return None
    a0in = int(data[0:64], 16)
    a1in = int(data[64:128], 16)
    a0out = int(data[128:192], 16)
    a1out = int(data[192:256], 16)
    if base_is_token0:
        bin_, bout, qin, qout = a0in, a0out, a1in, a1out
    else:
        bin_, bout, qin, qout = a1in, a1out, a0in, a0out
    if qin > 0 and bout > 0:      # quote in, base out = BUY
        return 'buy', qin, bout
    if bin_ > 0 and qout > 0:     # base in, quote out = SELL
        return 'sell', qout, bin_
    return None


def latest_block():
    res = rpc('eth_blockNumber', [])
    return int(res, 16) if res else None


def poll_once(state, pools_meta):
    """One poll cycle: fetch Swap logs for all tracked pools since last block."""
    addrs = sorted(pools_meta.keys())
    if not addrs:
        return 0
    from_block = state.get('last_block')
    to_block = latest_block()
    if to_block is None:
        return 0
    if from_block is None:
        from_block = to_block - 900  # ~45 min backfill on first run (3s blocks)
    if to_block <= from_block:
        return 0
    logs = []
    for i in range(0, len(addrs), 50):
        chunk = rpc('eth_getLogs', [{
            'address': addrs[i:i + 50],
            'topics': [SWAP_V2],
            'fromBlock': hex(from_block + 1),
            'toBlock': hex(to_block),
        }])
        if chunk:
            logs.extend(chunk)
        time.sleep(0.3)
    state['last_block'] = to_block
    if not logs:
        return 0
    n = 0
    with open(OUT, 'a') as f:
        for lg in logs:
            pair = lg.get('address', '').lower()
            meta = pools_meta.get(pair)
            if not meta:
                continue
            t0 = state.setdefault('token0', {}).get(pair)
            if t0 is None:
                t0 = pool_token0(pair)
                if t0:
                    state['token0'][pair] = t0
                else:
                    continue
            base_is_token0 = t0 not in QUOTES
            dec = decode_swap(lg, base_is_token0)
            if not dec:
                continue
            side, qamt, bamt = dec
            if bamt == 0:
                continue
            price = qamt / bamt  # quote per base, raw — ratios consistent per pool
            ts = int(lg.get('blockNumber', '0x0'), 16)
            rec = dict(t=time.time(), chain='bsc', venue='pool', mint=pair,
                       symbol=(meta.get('name') or '').split(' / ')[0],
                       side=side, sol=None, price_raw=price,
                       block=ts, tx=lg.get('transactionHash'))
            f.write(json.dumps(rec) + '\n')
            n += 1
    return n


def main():
    now = time.time()
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    pools = tracked_pools(now)
    print(f'tracked BSC pools: {len(pools)}')
    n = poll_once(state, pools)
    json.dump(state, open(STATE, 'w'))
    print(f'new swap events written: {n} -> {OUT}')


if __name__ == '__main__':
    main()
