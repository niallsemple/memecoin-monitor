#!/usr/bin/env python3
"""
goplus_gate.py — rug-risk gate for EVM meme tokens via the free GoPlus
Token Security API (no key). Directly attacks the observed BSC base rate:
4/5 inflow-triggering pools rugged within 60 min (§64).

Pass criteria (conservative):
  - not a honeypot, buy/sell tax <= 10%
  - cannot mint new supply, no owner balance-change / hidden-owner powers
  - LP mostly locked or burned (holders analysis: locked+ burned >= 50%)
  - not a proxy with external-call risk flags, not blacklisting

Usage:
  python3 goplus_gate.py bsc <base_token_addr> [<addr2> ...]
  python3 goplus_gate.py bsc --pairs            # gate all currently watched pools
Exit code 0 always; prints PASS/FAIL + reasons per token. JSON to stdout with -j.
"""
import json, sys, time, urllib.request, urllib.error

CHAIN_ID = {'bsc': '56', 'base': '8453', 'eth': '1'}
API = 'https://api.gopluslabs.io/api/v1/token_security'


def fetch(chain, addrs):
    url = f"{API}/{CHAIN_ID[chain]}?contract_addresses={','.join(addrs)}"
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'mfg-gate/1.0'})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r).get('result') or {}
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < 2:
                time.sleep(6 * (i + 1))
                continue
            print(f'HTTP {e.code} {url}')
            return {}
        except Exception as e:
            print(f'ERR {e}')
            return {}


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def judge(chain, addr, d):
    """-> (passed: bool, reasons: list[str])"""
    reasons = []
    if not d:
        return False, ['no data from GoPlus']
    if d.get('is_honeypot') == '1':
        reasons.append('honeypot')
    bt, stax = _f(d.get('buy_tax')), _f(d.get('sell_tax'))
    if (bt or 0) > 0.10 or (stax or 0) > 0.10:
        reasons.append(f'tax buy={bt} sell={stax}')
    if d.get('is_mintable') == '1':
        reasons.append('mintable')
    if d.get('hidden_owner') == '1':
        reasons.append('hidden_owner')
    if d.get('can_take_back_ownership') == '1':
        reasons.append('can_take_back_ownership')
    if d.get('owner_change_balance') == '1':
        reasons.append('owner_change_balance')
    if d.get('is_blacklisted') == '1':
        reasons.append('blacklist_func')
    if d.get('is_proxy') == '1':
        reasons.append('proxy')
    # LP lock/burn check
    locked = 0.0
    for h in (d.get('lp_holders') or []):
        if h.get('is_locked') == '1' or 'dead' in (h.get('address') or '').lower() \
                or (h.get('address') or '').lower().endswith('000000000000000000000000000000000000dead'):
            locked += _f(h.get('percent')) or 0.0
    if locked < 0.5:
        reasons.append(f'lp_locked={locked:.0%}')
    return (not reasons), reasons


def watched_base_tokens(chain):
    """All currently watched pools -> (pair, name, base_token_addr)."""
    st = json.load(open(f'{chain}_watcher_state.json'))
    import evm_watcher as w
    quotes = set(w.CHARS_QUOTES) if hasattr(w, 'CHARS_QUOTES') else set(w.CHAINS[chain]['quotes'])
    out = []
    t0 = st.get('token0', {})
    t1 = st.get('token1', {})
    names = {}
    for line in open('xchain_scan.jsonl'):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get('chain') == chain and r.get('pair'):
            names[r['pair'].lower()] = r.get('name')
    for p, z in t0.items():
        if z in quotes:
            base = t1.get(p)
        else:
            base = z
        if base:
            out.append((p, names.get(p, p[:10]), base))
    return out


if __name__ == '__main__':
    chain = sys.argv[1] if len(sys.argv) > 1 else 'bsc'
    args = sys.argv[2:]
    json_out = '-j' in args
    args = [a for a in args if a != '-j']
    if args and args[0] == '--pairs':
        targets = watched_base_tokens(chain)
    else:
        targets = [(a, a[:10], a.lower()) for a in args]
    if not targets:
        print('no targets')
        sys.exit(0)
    res = fetch(chain, [t[2] for t in targets])
    report = []
    for pair, name, base in targets:
        d = None
        for k, v in res.items():
            if k.lower() == base.lower():
                d = v
                break
        ok, reasons = judge(chain, base, d)
        report.append(dict(chain=chain, pair=pair, name=name, token=base,
                           passed=ok, reasons=reasons))
        print(f"{'PASS' if ok else 'FAIL'} {name[:26]:26s} {base[:12]}... "
              f"{'; '.join(reasons) if reasons else 'clean'}")
    if json_out:
        print(json.dumps(report))
