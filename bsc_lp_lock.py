#!/usr/bin/env python3
"""
bsc_lp_lock.py — reconstruct WHO holds the LP tokens of a PancakeSwap-V2-style
pair at a given time, using only eth_getLogs + eth_call.

Hypothesis under test: pools that get LP-pulled minutes after our entry have
the deployer EOA holding ~all LP at entry (unlocked), while survivors have
locked/burned/distributed LP.

Usage: python3 bsc_lp_lock.py <pair> <entry_unix_t> [<pair> <entry_t> ...]
"""
import json, os, sys, time, urllib.request

RPC = os.environ.get("BSC_RPC", "https://bsc-dataseed.binance.org")
MINT_TOPIC = "0x4c209b5fc8ad50761f13e2e5478e99133531ac657f9371fff4d47f27d0c00d4c"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
CHUNK = 5000           # blocks per getLogs call (public RPC cap)
MAX_CHUNKS = 100       # scan back at most ~500k blocks
_id = 0


def rpc(method, params):
    global _id
    _id += 1
    payload = json.dumps({"jsonrpc": "2.0", "id": _id,
                          "method": method, "params": params}).encode()
    req = urllib.request.Request(RPC, data=payload,
                                 headers={"Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                out = json.load(r)
            if "error" in out:
                raise RuntimeError(str(out["error"]))
            return out.get("result")
        except Exception as e:
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))


def block_at(ts):
    """binary-search the latest block with timestamp <= ts"""
    latest = int(rpc("eth_blockNumber", []), 16)
    lo, hi = 0, latest
    while lo < hi:
        mid = (lo + hi + 1) // 2
        b = rpc("eth_getBlockByNumber", [hex(mid), False])
        if b is None:
            hi = mid - 1
            continue
        if int(b["timestamp"], 16) <= ts:
            lo = mid
        else:
            hi = mid - 1
    return lo


def get_logs(pair, topic0, frm, to):
    time.sleep(0.25)   # stay under public-RPC rate limits
    return rpc("eth_getLogs", [{"address": pair, "topics": [topic0],
                                "fromBlock": hex(frm), "toBlock": hex(to)}]) or []


def analyze(pair, entry_t):
    eb = block_at(entry_t)
    # 1) find the pair's first Mint (creation liquidity) scanning backwards
    first_mint_blk, mints = None, []
    to = eb
    for _ in range(MAX_CHUNKS):
        frm = max(0, to - CHUNK)
        logs = get_logs(pair, MINT_TOPIC, frm, to)
        if logs:
            mints = logs + mints
            first_mint_blk = int(logs[0]["blockNumber"], 16)
            break
        to = frm - 1
        if frm == 0:
            break
    if first_mint_blk is None:
        return {"pair": pair, "error": "no Mint found within scan window"}
    # 2) all LP Transfer events from creation to entry block
    transfers = []
    frm = first_mint_blk
    while frm <= eb:
        to = min(eb, frm + CHUNK)
        transfers += get_logs(pair, TRANSFER_TOPIC, frm, to)
        frm = to + 1
    # 3) replay: mints credit receiver; transfers move LP
    bal = {}

    def addr(topic):
        return "0x" + topic[-40:]

    # collect ALL mints from creation to entry (add-liquidity events)
    frm = first_mint_blk
    all_mints = []
    while frm <= eb:
        to = min(eb, frm + CHUNK)
        all_mints += get_logs(pair, MINT_TOPIC, frm, to)
        frm = to + 1
    events = []
    for m in all_mints:
        events.append((int(m["blockNumber"], 16), int(m["transactionIndex"], 16),
                       int(m["logIndex"], 16), "mint", m))
    for tr in transfers:
        events.append((int(tr["blockNumber"], 16), int(tr["transactionIndex"], 16),
                       int(tr["logIndex"], 16), "transfer", tr))
    events.sort()
    total = 0
    for _, _, _, kind, e in events:
        if kind == "mint":
            # Mint(address sender, uint amount0, uint amount1); the LP amount is
            # NOT in the event — use the matching Transfer-from-zero in same tx
            pass
    # Simpler + exact: reconstruct purely from Transfer events
    # (LP mint = Transfer from 0x0, burn = Transfer to 0x0/dead)
    bal = {}
    total = 0
    for tr in transfers:
        frm_a = addr(tr["topics"][1])
        to_a = addr(tr["topics"][2])
        val = int(tr["data"], 16)
        if int(frm_a, 16) == 0:
            total += val
        if int(to_a, 16) == 0:
            total -= val
        bal[frm_a] = bal.get(frm_a, 0) - val
        bal[to_a] = bal.get(to_a, 0) + val
    bal.pop("0x" + "0" * 40, None)
    if total <= 0:
        return {"pair": pair, "error": "no LP supply at entry"}
    top = max(bal.values()) if bal else 0
    dead = sum(v for a, v in bal.items()
               if a.lower() in ("0x" + "0" * 38 + "dead",))
    holders = sorted(bal.items(), key=lambda kv: -kv[1])[:5]
    return {
        "pair": pair, "entry_block": eb, "creation_block": first_mint_blk,
        "lp_total": total,
        "top_holder": holders[0][0] if holders else None,
        "top_frac": round(top / total, 4),
        "burned_frac": round(dead / total, 4),
        "n_holders": len(bal),
        "top5": [(a, round(v / total, 4)) for a, v in holders],
    }


if __name__ == "__main__":
    args = sys.argv[1:]
    for i in range(0, len(args), 2):
        pair, ts = args[i], int(float(args[i + 1]))
        try:
            print(json.dumps(analyze(pair, ts)))
        except Exception as e:
            print(json.dumps({"pair": pair, "error": str(e)}))
        sys.stdout.flush()
