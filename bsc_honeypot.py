#!/usr/bin/env python3
"""
bsc_honeypot.py — pre-entry sellability/tax check for BSC tokens (§475 gating item).

Two layers:
  1. honeypot.is v2 API (free, no key): simulation-backed isHoneypot + buy/sell tax.
  2. Local RPC fallback: resolve token from pair (token0/token1, non-WBNB side),
     quote BOTH directions through PancakeSwap router getAmountsOut. A quote that
     fails token->WBNB is a hard reject even without the API.

Usage:
  python3 bsc_honeypot.py <token_or_pair_address> [--pair]
Cache: bsc_honeypot_cache.json (24h TTL) so the watcher never double-pays latency.
"""
import json, os, sys, time, urllib.request

RPC = os.environ.get("BSC_RPC", "https://bsc-dataseed.binance.org")
WBNB = "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c"
ROUTER = "0x10ED43C718714eb63d5aA57B78B54704E256024E"  # PancakeSwap v2
CACHE = "bsc_honeypot_cache.json"
TTL = 24 * 3600

# selectors
SEL_TOKEN0 = bytes.fromhex("0dfe1681")
SEL_TOKEN1 = bytes.fromhex("d21220a7")
SEL_RESERVES = bytes.fromhex("0902f1ac")
SEL_GET_OUT = bytes.fromhex("d06ca61f")  # getAmountsOut(uint256,address[])

# known numeraires (quote tokens) on BSC
NUMERAIRES = {
    "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c": "WBNB",
    "0x55d398326f99059ff775485246999027b3197955": "USDT",
    "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d": "USDC",
    "0xe9e7cea3dedca5984780bafc599bd69add087d56": "BUSD",
}


def rpc_call(to, data):
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "eth_call",
        "params": [{"to": to, "data": "0x" + data.hex()}, "latest"],
    }).encode()
    req = urllib.request.Request(RPC, data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        out = json.load(r)
    if "error" in out:
        raise RuntimeError(out["error"])
    return bytes.fromhex(out["result"][2:])


def pair_sides(pair):
    t0 = "0x" + rpc_call(pair, SEL_TOKEN0)[-20:].hex()
    t1 = "0x" + rpc_call(pair, SEL_TOKEN1)[-20:].hex()
    out = rpc_call(pair, SEL_RESERVES)
    r0 = int.from_bytes(out[0:32], "big")
    r1 = int.from_bytes(out[32:64], "big")
    if t0.lower() in NUMERAIRES:
        return t1.lower(), t0.lower(), r1, r0     # token, quote, res_token, res_quote
    if t1.lower() in NUMERAIRES:
        return t0.lower(), t1.lower(), r0, r1
    raise RuntimeError(f"no known numeraire in pair ({t0[:10]}/{t1[:10]})")


def quote_out(amount_in, path):
    # abi.encode(uint256, address[])
    data = SEL_GET_OUT
    data += amount_in.to_bytes(32, "big")
    data += (32 * 2).to_bytes(32, "big")          # offset to array
    data += len(path).to_bytes(32, "big")
    for a in path:
        data += bytes(12) + bytes.fromhex(a[2:])
    out = rpc_call(ROUTER, data)
    n = int.from_bytes(out[32:64], "big")
    return int.from_bytes(out[64 + 32 * (n - 1): 64 + 32 * n], "big")


def api_check(token):
    url = f"https://api.honeypot.is/v2/IsHoneypot?address={token}&chainID=56"
    req = urllib.request.Request(url, headers={"User-Agent": "darwin-labs/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def check(addr, is_pair=False):
    token = addr.lower()
    quote = WBNB
    res_tok = res_quote = None
    if is_pair:
        token, quote, res_tok, res_quote = pair_sides(addr)
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    ent = cache.get(token)
    if ent and time.time() - ent.get("ts", 0) < TTL:
        return ent
    res = {"token": token, "quote": NUMERAIRES.get(quote, quote), "ts": time.time(),
           "ok": True, "reasons": []}

    # layer 2: local two-way quote through the pair's ACTUAL numeraire,
    # sized at 0.1% of quote reserves so slippage isn't mistaken for tax.
    try:
        if is_pair and res_quote is not None:
            if res_quote == 0 or res_tok == 0:
                raise RuntimeError("dead pool: zero reserves")
            amt_in = max(res_quote // 1000, 10 ** 12)
        else:
            amt_in = 2 * 10 ** 16  # 0.02 units of numeraire when reserves unknown
        tok_amt = quote_out(amt_in, [quote, token])
        if tok_amt == 0:
            raise RuntimeError("buy quote returned 0 (no route / dead pool)")
        back = quote_out(tok_amt, [token, quote])
        implied_tax = 1 - back / amt_in
        res["rpc_roundtrip_tax"] = round(implied_tax, 4)
        if implied_tax > 0.25:
            res["ok"] = False
            res["reasons"].append(f"rpc roundtrip tax {implied_tax:.1%} > 25%")
    except Exception as e:
        res["ok"] = False
        res["reasons"].append(f"rpc sell quote failed: {e}")

    # layer 1: honeypot.is simulation
    try:
        hp = api_check(token)
        res["api"] = {
            "isHoneypot": hp.get("honeypotResult", {}).get("isHoneypot"),
            "buyTax": hp.get("simulationResult", {}).get("buyTax"),
            "sellTax": hp.get("simulationResult", {}).get("sellTax"),
            "simOK": hp.get("simulationSuccess", hp.get("simulationResult") is not None),
        }
        if res["api"]["isHoneypot"]:
            res["ok"] = False
            res["reasons"].append("honeypot.is: HONEYPOT")
        st = res["api"].get("sellTax") or 0
        if st and st > 25:
            res["ok"] = False
            res["reasons"].append(f"sellTax {st}% > 25%")
    except Exception as e:
        res["api_error"] = str(e)[:120]

    cache[token] = res
    json.dump(cache, open(CACHE, "w"))
    return res


if __name__ == "__main__":
    a = sys.argv[1]
    is_pair = "--pair" in sys.argv
    print(json.dumps(check(a, is_pair), indent=2))
