#!/usr/bin/env python3
"""kamino_arb_pnl3.py — price the 'complex' txs by extracting IMPLIED mint prices
from swap legs inside each transaction.

Method: walk all parsed SPL transfers (outer+inner). Any token account that
receives mint A and sends mint B within the tx is a swap vault leg:
  implied:  px[B] = px[A] * amtA_in / amtB_out   (A priced -> price B)
Iterate until fixpoint (chains through multi-hop). Seeds: USDC/USDT=$1,
wSOL=Binance daily close. Then value the payer's balance deltas (from
pre/postTokenBalances, owner-attributed) at implied prices.

Only re-processes rows marked complex in kamino_arb_pnl2.jsonl.
Appends kamino_arb_pnl3.jsonl; checkpoint kamino_arb_pnl3_done.json.
"""
import json, time, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from kamino_tail import rpc

MON = Path(__file__).resolve().parent
PNL2 = MON / "kamino_arb_pnl2.jsonl"
OUT = MON / "kamino_arb_pnl3.jsonl"
DONE = MON / "kamino_arb_pnl3_done.json"
SOLCACHE = MON / "sol_daily_px.json"

USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
WSOL = "So11111111111111111111111111111111111111112"
KLEND = "KLend2g3cP87fffoy8q1mQqGKjrxjC8boSyAYavgmjD"
# verified against 7tUACGesj pure-arb tx (§486)
FLASH_B = bytes([135, 231, 52, 167, 7, 52, 212, 193])
FLASH_R = bytes([185, 117, 0, 203, 96, 245, 180, 186])
REFRESH_RES = bytes([2, 218, 138, 235, 79, 201, 25, 102])
PURE_ARB_DISCS = {FLASH_B, FLASH_R, REFRESH_RES}

ALPH = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def b58decode(s):
    n = 0
    for c in s:
        n = n * 58 + ALPH.index(c)
    b = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\0" * (len(s) - len(s.lstrip("1"))) + b

def klend_discs(tx):
    """Distinct KLend instruction discs, outer + inner."""
    out = set()
    ixs = list(tx["transaction"]["message"].get("instructions", []))
    for inner in (tx.get("meta") or {}).get("innerInstructions") or []:
        ixs += inner.get("instructions", [])
    for ix in ixs:
        if isinstance(ix, dict) and ix.get("programId") == KLEND and ix.get("data"):
            try:
                out.add(b58decode(ix["data"])[:8])
            except Exception:
                pass
    return out


def transfers(tx):
    """All parsed spl-token transfer/transferChecked ixs: (source, dest, mint, amt)."""
    out = []
    ixs = list(tx["transaction"]["message"].get("instructions", []))
    for inner in (tx.get("meta") or {}).get("innerInstructions") or []:
        ixs += inner.get("instructions", [])
    for ix in ixs:
        if not isinstance(ix, dict) or ix.get("program") != "spl-token":
            continue
        p = ix.get("parsed") or {}
        if p.get("type") not in ("transfer", "transferChecked"):
            continue
        info = p.get("info") or {}
        try:
            if p["type"] == "transferChecked":
                amt = float(info["tokenAmount"]["uiAmount"])
                mint = info["mint"]
            else:
                amt = float(info["amount"])  # raw; mint unknown -> skip
                continue
            out.append((info.get("source"), info.get("destination"), mint, amt))
        except Exception:
            continue
    return out


def owner_mint_deltas(tx):
    """owner -> {mint: net delta} from pre/postTokenBalances (vaults incl.)."""
    pre, post = {}, {}
    meta = tx.get("meta") or {}
    for b in meta.get("preTokenBalances") or []:
        k = (b.get("owner"), b["mint"])
        pre[k] = pre.get(k, 0) + float(b["uiTokenAmount"].get("uiAmount") or 0)
    for b in meta.get("postTokenBalances") or []:
        k = (b.get("owner"), b["mint"])
        post[k] = post.get(k, 0) + float(b["uiTokenAmount"].get("uiAmount") or 0)
    out = {}
    for k in set(pre) | set(post):
        d = post.get(k, 0) - pre.get(k, 0)
        if abs(d) > 1e-12 and k[0]:
            out.setdefault(k[0], {})[k[1]] = out.get(k[0], {}).get(k[1], 0) + d \
                if k[0] in out else d
    # fix double-setdefault bug: rebuild cleanly
    out = {}
    for k in set(pre) | set(post):
        d = post.get(k, 0) - pre.get(k, 0)
        if abs(d) > 1e-12 and k[0]:
            out.setdefault(k[0], {})
            out[k[0]][k[1]] = out[k[0]].get(k[1], 0) + d
    return out


def implied_prices(owners, seeds):
    """Fixpoint: an owner (pool authority) with priced +X and unpriced −Y
    (or vice versa) is a swap leg: px[Y] = px[X]*|X| / |Y|."""
    px = dict(seeds)
    for _ in range(10):
        changed = False
        for legs in owners.values():
            pin = [(m, a) for m, a in legs.items() if a > 0 and m in px]
            uout = [(m, -a) for m, a in legs.items() if a < 0 and m not in px]
            pout = [(m, -a) for m, a in legs.items() if a < 0 and m in px]
            uin = [(m, a) for m, a in legs.items() if a > 0 and m not in px]
            if pin and len(uout) == 1 and not uin:
                m_in, a_in = max(pin, key=lambda x: x[1] * px[x[0]])
                m_out, a_out = uout[0]
                if a_in > 0 and a_out > 0:
                    px[m_out] = px[m_in] * a_in / a_out
                    changed = True
            elif pout and len(uin) == 1 and not pin:
                m_out, a_out = max(pout, key=lambda x: x[1] * px[x[0]])
                m_in, a_in = uin[0]
                if a_out > 0 and a_in > 0:
                    px[m_in] = px[m_out] * a_out / a_in
                    changed = True
        if not changed:
            break
    return px


def payer_deltas(tx, payer):
    pre, post = {}, {}
    meta = tx.get("meta") or {}
    for b in meta.get("preTokenBalances") or []:
        if b.get("owner") == payer:
            pre[(b["accountIndex"], b["mint"])] = float(
                b["uiTokenAmount"].get("uiAmount") or 0)
    for b in meta.get("postTokenBalances") or []:
        if b.get("owner") == payer:
            post[(b["accountIndex"], b["mint"])] = float(
                b["uiTokenAmount"].get("uiAmount") or 0)
    by_mint = {}
    for k in set(pre) | set(post):
        d = post.get(k, 0) - pre.get(k, 0)
        if abs(d) > 1e-12:
            by_mint[k[1]] = by_mint.get(k[1], 0) + d
    sol = 0.0
    msg = tx["transaction"]["message"]
    keys = [k["pubkey"] if isinstance(k, dict) else k for k in msg["accountKeys"]]
    if payer in keys:
        i = keys.index(payer)
        sol = (meta["postBalances"][i] - meta["preBalances"][i]) / 1e9
    return by_mint, sol


def main():
    max_s = float(sys.argv[1]) if len(sys.argv) > 1 else 240
    t0 = time.time()
    done = set(json.load(open(DONE))) if DONE.exists() else set()
    pxcache = json.load(open(SOLCACHE)) if SOLCACHE.exists() else {}
    todo = [json.loads(l) for l in open(PNL2) if json.loads(l)["complex"]]
    n = 0
    f = open(OUT, "a")
    for r in todo:
        if time.time() - t0 > max_s:
            break
        sig = r["sig"]
        if sig in done:
            continue
        done.add(sig)
        try:
            tx = rpc("getTransaction", [sig, {"encoding": "jsonParsed",
                     "maxSupportedTransactionVersion": 0}]).get("result")
        except Exception:
            continue
        if not tx:
            continue
        d = time.strftime("%Y-%m-%d", time.gmtime(r["ts"]))
        seeds = {USDC: 1.0, USDT: 1.0}
        if pxcache.get(d):
            seeds[WSOL] = pxcache[d]
        px = implied_prices(owner_mint_deltas(tx), seeds)
        deltas, sol_net = payer_deltas(tx, r["payer"])
        pnl, unpriced = 0.0, []
        for m, amt in deltas.items():
            if m in px:
                pnl += amt * px[m]
            else:
                unpriced.append(m[:8])
        if seeds.get(WSOL):
            pnl += sol_net * seeds[WSOL]
        discs = klend_discs(tx)
        pure = bool(discs) and discs <= PURE_ARB_DISCS
        f.write(json.dumps({"sig": sig, "ts": r["ts"], "payer": r["payer"],
                            "pnl_usd": round(pnl, 5), "n_priced_mints": len(px),
                            "pure_arb": pure, "unpriced": unpriced[:5]}) + "\n")
        f.flush()
        n += 1
        time.sleep(0.1)
    f.close()
    json.dump(sorted(done), open(DONE, "w"))
    print(f"repriced {n} (total {len(done)}/{len(todo)})")


if __name__ == "__main__":
    main()
