#!/usr/bin/env python3
"""swap_forensics.py — is a pool's tx tape organic flow or wash trading?

Samples recent swap txs for a pool via RPC getTransaction and reports:
  - unique fee payers (signers) and repeat concentration
  - per-tx signer SOL delta distribution (wash bots recycle tiny amounts)
Usage: python3 swap_forensics.py <pool_prefix_or_full> [n_samples]
"""
import json, os, sys, time, urllib.request, collections

MON = os.path.dirname(os.path.abspath(__file__))
KEY = open(os.path.join(MON, "helius_key.txt")).read().strip()
URL = f"https://mainnet.helius-rpc.com/?api-key={KEY}"

def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params}).encode()
    req = urllib.request.Request(URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()).get("result")

def resolve_pool(prefix):
    if len(prefix) > 20:
        return prefix
    for line in open(os.path.join(MON, "txflow.jsonl")):
        try:
            p = json.loads(line)["pool"]
            if p.startswith(prefix):
                return p
        except Exception:
            continue
    raise SystemExit(f"pool {prefix} not found in txflow.jsonl")

def main():
    pool = resolve_pool(sys.argv[1])
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    sigs = rpc("getSignaturesForAddress", [pool, {"limit": 200}]) or []
    ok = [s["signature"] for s in sigs if s.get("err") is None][:n]
    print(f"pool {pool[:12]}... sampling {len(ok)} txs")

    payers = collections.Counter()
    deltas = []
    for i, sig in enumerate(ok):
        try:
            tx = rpc("getTransaction", [sig, {"encoding": "json",
                                              "maxSupportedTransactionVersion": 0}])
        except Exception as e:
            print(f"  tx fail: {str(e)[:50]}")
            continue
        if not tx:
            continue
        msg = tx["transaction"]["message"]
        payer = msg["accountKeys"][0]
        if isinstance(payer, dict):
            payer = payer.get("pubkey", str(payer))
        payers[payer] += 1
        meta = tx.get("meta") or {}
        pre, post = meta.get("preBalances", []), meta.get("postBalances", [])
        if pre and post:
            deltas.append((post[0] - pre[0]) / 1e9)  # payer SOL delta (incl fee)
        if i % 5 == 4:
            time.sleep(0.3)  # be polite to the RPC
    print(f"\nunique payers: {len(payers)} / {sum(payers.values())} txs")
    for payer, c in payers.most_common(8):
        print(f"  {payer[:12]}... x{c}")
    if deltas:
        import statistics
        ad = [abs(d) for d in deltas]
        print(f"\npayer SOL |delta|: median {statistics.median(ad):.6f}, "
              f"min {min(ad):.6f}, max {max(ad):.6f}")
    # verdict
    if payers:
        top_share = payers.most_common(1)[0][1] / sum(payers.values())
        if len(payers) <= 3 or top_share > 0.5:
            print("\nVERDICT: WASH-CONCENTRATED — tape is one/few wallets cycling")
        else:
            print("\nVERDICT: ORGANIC-DIVERSE — many wallets; flow is real, "
                  "paper zeros are claim-reset artifact -> fountains are live targets")

if __name__ == "__main__":
    main()
