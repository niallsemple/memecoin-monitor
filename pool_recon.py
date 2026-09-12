#!/usr/bin/env python3
"""Generalized pool reconstruction: any DLMM pool, any window.

Usage: python3 pool_recon.py <pool_addr> <t_start> <t_end> <tag>

Steps:
 1. page getSignaturesForAddress over [t_start-600, t_end+600] (backoff on 429)
 2. batch getTransaction (jsonParsed) -> <tag>_txs.jsonl
 3. auto-discover reserve vaults: token-balance entries with owner == pool
 4. classify txs via DLMM-scope ops; vault deltas -> <tag>_swaps.jsonl,
    <tag>_prot_claims.jsonl, <tag>_lp_claims.jsonl, <tag>_liqops.jsonl

Output files land in the monitor dir, prefixed by tag.
"""
import json, os, re, sys, time, urllib.request

MON = os.path.dirname(os.path.abspath(__file__))
KEY = open(os.path.join(MON, "helius_key.txt")).read().strip()
RPC = f"https://mainnet.helius-rpc.com/?api-key={KEY}"
DLMM = 'LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo'
INSTR_RE = re.compile(r'Program log: Instruction: (\w+)')
SWAP_OPS = {'Swap', 'Swap2', 'SwapExactOut', 'SwapWithPriceImpact'}
PROT_CLAIM_OPS = {'MeteoraDlmmClaimFee2Automation', 'ClaimProtocolFee', 'ClaimProtocolFee2'}
LP_CLAIM_OPS = {'ClaimFee', 'ClaimFee2'}


def post(payload, timeout=60):
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    for attempt in range(8):
        try:
            req = urllib.request.Request(RPC, data=body,
                                         headers={"Content-Type": "application/json"})
            return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                w = min(2 ** attempt, 30)
                print(f"  429 backoff {w}s")
                time.sleep(w)
                continue
            raise
    raise RuntimeError("rate-limited out")


def rpc(method, params):
    return post({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})


def dlmm_ops(logs):
    ops, stack, in_dlmm = [], [], False
    for lg in logs:
        if lg.startswith('Program ') and ' invoke [' in lg:
            pid = lg.split(' ')[1]
            depth = int(lg.rsplit('[', 1)[1].rstrip(']'))
            while stack and stack[-1][1] >= depth:
                stack.pop()
            stack.append((pid, depth))
            if pid == DLMM:
                in_dlmm = True
            continue
        if lg.startswith('Program ') and (lg.endswith(' success') or lg.endswith(' failed')):
            pid = lg.split(' ')[1]
            while stack and stack[-1][0] != pid:
                stack.pop()
            if stack:
                stack.pop()
            if in_dlmm and not any(p == DLMM for p, _ in stack):
                in_dlmm = False
            continue
        if in_dlmm:
            m = INSTR_RE.match(lg)
            if m:
                ops.append(m.group(1))
    return ops


def acct_keys(tx, meta):
    keys = [k['pubkey'] if isinstance(k, dict) else k
            for k in tx['transaction']['message']['accountKeys']]
    la = meta.get('loadedAddresses') or {}
    return keys + (la.get('writable') or []) + (la.get('readonly') or [])


def main():
    pool, t0, t1, tag = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    lo, hi = t0 - 600, t1 + 600

    # ---- phase 1: signatures (cached)
    sigf = os.path.join(MON, f"{tag}_sigs.jsonl")
    if os.path.exists(sigf):
        sigs = [json.loads(l) for l in open(sigf)]
        print(f"cached sigs: {len(sigs)}")
    else:
        sigs, before = [], None
        while True:
            p = [pool, {"limit": 1000}]
            if before:
                p[1]["before"] = before
            batch = rpc("getSignaturesForAddress", p).get("result") or []
            if not batch:
                break
            sigs.extend(batch)
            before = batch[-1]["signature"]
            print(f"sigs {len(sigs)} oldest {batch[-1]['blockTime']}")
            if batch[-1]["blockTime"] < lo:
                break
            time.sleep(0.3)
        with open(sigf, "w") as f:
            for s in sigs:
                f.write(json.dumps({"sig": s["signature"], "slot": s["slot"],
                                    "blockTime": s["blockTime"]}) + "\n")
    # if we started from newest, drop everything newer than hi
    keep = [s for s in sigs if lo <= s["blockTime"] <= hi]
    # walk forward: we may have paged past hi on the first batch; that's fine
    print(f"in-window sigs: {len(keep)}")

    # ---- phase 2: fetch txs (resumable)
    txf = os.path.join(MON, f"{tag}_txs.jsonl")
    done = set()
    if os.path.exists(txf):
        for ln in open(txf):
            try:
                done.add(json.loads(ln)["sig"])
            except Exception:
                pass
    todo = [s for s in keep if s["signature"] not in done]
    print(f"resume: {len(done)} done, {len(todo)} to fetch")
    out = open(txf, "a")
    n_ok = 0
    for i in range(0, len(todo), 50):
        reqs = [{"jsonrpc": "2.0", "id": j, "method": "getTransaction",
                 "params": [s["signature"], {"encoding": "jsonParsed",
                            "maxSupportedTransactionVersion": 0,
                            "commitment": "confirmed"}]}
                for j, s in enumerate(todo[i:i + 50])]
        resp = post(reqs, timeout=120)
        for j, s in enumerate(todo[i:i + 50]):
            r = resp[j].get("result") if j < len(resp) else None
            if r:
                out.write(json.dumps({"sig": s["signature"], "slot": r.get("slot"),
                                      "blockTime": r.get("blockTime"), "tx": r}) + "\n")
                n_ok += 1
        out.flush()
        print(f"fetched {min(i + 50, len(todo))}/{len(todo)}")
        time.sleep(0.5)
    out.close()

    # ---- phase 3: discover vaults (owner == pool), most-frequent pair
    from collections import Counter
    c = Counter()
    rows = []
    for line in open(txf):
        d = json.loads(line)
        meta = d['tx'].get('meta') or {}
        if meta.get('err'):
            continue
        keys = acct_keys(d['tx'], meta)
        for b in (meta.get('postTokenBalances') or []):
            if b.get('owner') == pool and b['accountIndex'] < len(keys):
                c[keys[b['accountIndex']]] += 1
        rows.append(d)
    vaults = [a for a, n in c.most_common(4)]
    print("vault candidates:", [(a[:8], n) for a, n in c.most_common(4)])
    vx = vy = None
    # identify SOL vault (wSOL mint) vs token vault
    mint_of = {}
    for line in open(txf):
        d = json.loads(line)
        meta = d['tx'].get('meta') or {}
        keys = acct_keys(d['tx'], meta)
        for b in (meta.get('postTokenBalances') or []):
            if b.get('owner') == pool and b['accountIndex'] < len(keys):
                mint_of[keys[b['accountIndex']]] = b['mint']
    for a in vaults:
        if mint_of.get(a) == 'So11111111111111111111111111111111111111112':
            vy = a
        elif vx is None:
            vx = a
    if not vy:
        print("WARNING: no wSOL vault found; aborting parse")
        return
    print(f"vaults: X={vx and vx[:8]} Y={vy[:8]}")

    # ---- phase 4: parse
    n_sw = n_pc = n_lc = n_mix = n_lo = 0
    f_sw = open(os.path.join(MON, f"{tag}_swaps.jsonl"), "w")
    f_pc = open(os.path.join(MON, f"{tag}_prot_claims.jsonl"), "w")
    f_lc = open(os.path.join(MON, f"{tag}_lp_claims.jsonl"), "w")
    f_lo = open(os.path.join(MON, f"{tag}_liqops.jsonl"), "w")
    for d in rows:
        tx = d['tx']; meta = tx.get('meta') or {}
        if meta.get('err'):
            continue
        logs = meta.get('logMessages') or []
        if DLMM not in ' '.join(logs):
            continue
        ops = dlmm_ops(logs)
        if not ops:
            continue
        keys = acct_keys(tx, meta)
        pre, postb = {}, {}
        for b in (meta.get('preTokenBalances') or []):
            a = keys[b['accountIndex']] if b['accountIndex'] < len(keys) else None
            if a in (vx, vy):
                pre[a] = int(b['uiTokenAmount']['amount'])
        for b in (meta.get('postTokenBalances') or []):
            a = keys[b['accountIndex']] if b['accountIndex'] < len(keys) else None
            if a in (vx, vy):
                postb[a] = int(b['uiTokenAmount']['amount'])
        if vx is None and vy is None:
            continue
        dx = (postb.get(vx, pre.get(vx, 0)) - pre.get(vx, 0)) if vx else 0
        dy = (postb.get(vy, pre.get(vy, 0)) - pre.get(vy, 0)) if vy else 0
        if dx == 0 and dy == 0:
            continue
        rec = dict(sig=d['sig'], slot=d['slot'], blockTime=d['blockTime'],
                   dx=dx, dy=dy, ops=ops)
        kinds = set(ops)
        is_swap = bool(kinds & SWAP_OPS)
        is_pc = bool(kinds & PROT_CLAIM_OPS)
        is_lc = bool(kinds & LP_CLAIM_OPS)
        if is_swap and not (is_pc or is_lc):
            rec['dir'] = 'sell_x' if dx > 0 else 'buy_x'
            f_sw.write(json.dumps(rec) + '\n'); n_sw += 1
        elif is_pc and not is_swap:
            f_pc.write(json.dumps(rec) + '\n'); n_pc += 1
        elif is_lc and not is_swap:
            f_lc.write(json.dumps(rec) + '\n'); n_lc += 1
        elif is_swap:
            rec['mixed'] = True
            f_sw.write(json.dumps(rec) + '\n'); n_mix += 1
        else:
            f_lo.write(json.dumps(rec) + '\n'); n_lo += 1
    for fh in (f_sw, f_pc, f_lc, f_lo):
        fh.close()
    print(f"{tag}: swaps={n_sw} prot_claims={n_pc} lp_claims={n_lc} mixed={n_mix} liqops={n_lo}")


if __name__ == '__main__':
    main()
