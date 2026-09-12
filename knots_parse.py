#!/usr/bin/env python3
"""Parse KNOTS pool activity from knots_txs.jsonl via reserve-vault balance deltas.

The deployed DLMM build does not emit Anchor swap events into logMessages, so
per-swap truth comes from pre/postTokenBalances on the pool's two reserve
vaults (owned by the pool address). Per tx we classify DLMM-scope instruction
names (Swap/Swap2 -> swap; MeteoraDlmmClaimFee2Automation -> protocol claim;
ClaimFee/ClaimFee2 -> LP claim) and net the vault deltas.

Outputs:
  knots_swaps.jsonl        one record per tx that swapped on our pool
  knots_prot_claims.jsonl  protocol-fee claims (reserve -> protocol receiver)
  knots_lp_claims.jsonl    LP fee claims (incl. our own guardian claims)
"""
import json, re

DLMM = 'LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo'
POOL = 'nBXytBBfKLhj6teXarAv8rk6WNgUFBMyybUFRkuK7ad'
VAULT_X = '3RmWg8vk2zpMgvz3GzPoYe8QLnXyzzQmJfTUQaPqvozJ'   # KNOTS, 6 dec
VAULT_Y = '8VC9k294Pt9hbb64LcxDLS2YNKgogoDwQHq8cXQMjGBf'   # wSOL, 9 dec
INSTR_RE = re.compile(r'Program log: Instruction: (\w+)')

SWAP_OPS = {'Swap', 'Swap2', 'SwapExactOut', 'SwapWithPriceImpact'}
PROT_CLAIM_OPS = {'MeteoraDlmmClaimFee2Automation', 'ClaimProtocolFee', 'ClaimProtocolFee2'}
LP_CLAIM_OPS = {'ClaimFee', 'ClaimFee2'}


def dlmm_ops(logs):
    """Return list of instruction names executed inside DLMM scopes."""
    ops = []
    stack = []
    in_dlmm = False
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


def vault_deltas(tx, meta):
    """Net raw-unit deltas of the two pool vaults (post - pre)."""
    keys = [k['pubkey'] if isinstance(k, dict) else k
            for k in tx['transaction']['message']['accountKeys']]
    la = meta.get('loadedAddresses') or {}
    keys += la.get('writable') or []
    keys += la.get('readonly') or []
    pre = {}
    for b in (meta.get('preTokenBalances') or []):
        acc = keys[b['accountIndex']]
        if acc in (VAULT_X, VAULT_Y):
            pre[acc] = int(b['uiTokenAmount']['amount'])
    post = {}
    for b in (meta.get('postTokenBalances') or []):
        acc = keys[b['accountIndex']]
        if acc in (VAULT_X, VAULT_Y):
            post[acc] = int(b['uiTokenAmount']['amount'])
    if VAULT_X not in post and VAULT_X not in pre:
        return None
    dx = post.get(VAULT_X, pre.get(VAULT_X, 0)) - pre.get(VAULT_X, 0)
    dy = post.get(VAULT_Y, pre.get(VAULT_Y, 0)) - pre.get(VAULT_Y, 0)
    return dx, dy   # positive = vault gained tokens


def main():
    n_sw = n_pc = n_lc = n_mix = n_lo = 0
    f_sw = open('knots_swaps.jsonl', 'w')
    f_pc = open('knots_prot_claims.jsonl', 'w')
    f_lc = open('knots_lp_claims.jsonl', 'w')
    f_lo = open('knots_liqops.jsonl', 'w')
    with open('knots_txs.jsonl') as f:
        for line in f:
            d = json.loads(line)
            tx = d['tx']; meta = tx.get('meta') or {}
            if meta.get('err'):
                continue
            logs = meta.get('logMessages') or []
            if DLMM not in ' '.join(logs):
                continue
            ops = dlmm_ops(logs)
            if not ops:
                continue
            vd = vault_deltas(tx, meta)
            if vd is None:
                continue
            dx, dy = vd
            if dx == 0 and dy == 0:
                continue
            rec = dict(sig=d['sig'], slot=d['slot'], blockTime=d['blockTime'],
                       dx=dx, dy=dy, ops=ops)
            kinds = set(ops)
            is_swap = bool(kinds & SWAP_OPS)
            is_pc = bool(kinds & PROT_CLAIM_OPS)
            is_lc = bool(kinds & LP_CLAIM_OPS)
            if is_swap and not (is_pc or is_lc):
                # dx>0 => pool gained X => trader sold X for Y (swap_for_y)
                rec['dir'] = 'sell_x' if dx > 0 else 'buy_x'
                f_sw.write(json.dumps(rec) + '\n'); n_sw += 1
            elif is_pc and not is_swap:
                f_pc.write(json.dumps(rec) + '\n'); n_pc += 1
            elif is_lc and not is_swap:
                f_lc.write(json.dumps(rec) + '\n'); n_lc += 1
            elif is_swap:
                rec['mixed'] = True   # swap + claim/liq op in one tx
                f_sw.write(json.dumps(rec) + '\n'); n_mix += 1
            else:
                f_lo.write(json.dumps(rec) + '\n'); n_lo += 1
    for fh in (f_sw, f_pc, f_lc, f_lo):
        fh.close()
    print(f'swaps={n_sw} prot_claims={n_pc} lp_claims={n_lc} mixed={n_mix} liqops={n_lo}')


if __name__ == '__main__':
    main()
