#!/usr/bin/env python3
"""Kamino Lend obligation health radar — step 2 of the Economic Compiler v1.

Uses the stored health fields Kamino cranks refresh on-chain:
  borrow_factor_adjusted_debt_value_sf  (what you owe, risk-adjusted)
  unhealthy_borrow_value_sf             (liquidation trigger line)
An obligation is liquidatable when adjusted_debt > unhealthy_borrow_value
(and debt > 0). Both are u128 fixed-point / 2**60. No per-reserve oracle
math needed for the RANK — staleness risk handled by checking last_update
slot on candidates only.

gPA pattern copied from liq_health.py (memcmp disc filter + wide dataSlice;
Helius rejects tiny slices).
"""
import json, base64, time, sys
from pathlib import Path
import urllib.request

KEY = (Path(__file__).parent / "helius_key.txt").read_text().strip()
RPC = f"https://mainnet.helius-rpc.com/?api-key={KEY}"
KLEND = "KLend2g3cP87fffoy8q1mQqGKjrxjC8boSyAYavgmjD"

ALPH = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def b58encode(b: bytes) -> str:
    n = int.from_bytes(b, "big")
    s = ""
    while n:
        n, r = divmod(n, 58)
        s = ALPH[r] + s
    pad = 0
    for c in b:
        if c == 0: pad += 1
        else: break
    return "1" * pad + (s or "")

OBL_DISC = bytes([168, 206, 141, 106, 88, 76, 172, 167])  # sha256("account:Obligation")[:8]
SF60 = float(2 ** 60)

# offsets incl 8-byte disc (verified vs refs/kamino_lending_full.json)
OFF_ADJ_DEBT = 2208   # borrow_factor_adjusted_debt_value_sf u128
OFF_BORROWED_MV = 2224
OFF_ALLOWED = 2240
OFF_UNHEALTHY = 2256  # unhealthy_borrow_value_sf u128
OFF_LAST_UPDATE_SLOT = 16  # u64 inside LastUpdate
OFF_OWNER = 64           # pubkey

def rpc(method, params, timeout=120):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params}).encode()
    req = urllib.request.Request(RPC, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def u128le(raw: bytes, off: int) -> int:
    return int.from_bytes(raw[off:off+16], "little")

def main():
    t0 = time.time()
    print("fetching KLend obligations (disc memcmp + slice 2208..2272)...")
    resp = rpc("getProgramAccounts", [KLEND, {
        "encoding": "base64",
        "dataSlice": {"offset": OFF_ADJ_DEBT, "length": 64},
        "filters": [{"memcmp": {"offset": 0, "bytes": b58encode(OBL_DISC)}}],
    }], timeout=280)
    res = resp.get("result")
    if res is None:
        print("RPC ERROR:", json.dumps(resp.get("error"))[:300]); sys.exit(1)
    print(f"  {len(res)} obligations in {time.time()-t0:.0f}s")

    rows = []
    for r in res:
        raw = base64.b64decode(r["account"]["data"][0])
        if len(raw) < 64:
            continue
        adj = u128le(raw, 0) / SF60
        borrowed_mv = u128le(raw, 16) / SF60
        allowed = u128le(raw, 32) / SF60
        unhealthy = u128le(raw, 48) / SF60
        if adj <= 0:
            continue  # no debt
        margin = unhealthy - adj   # <0 => liquidatable per stored fields
        rows.append((margin, adj, unhealthy, borrowed_mv, allowed, r["pubkey"]))

    rows.sort()
    with_debt = len(rows)
    liquidatable = [x for x in rows if x[0] < 0]
    print(f"\nobligations with debt: {with_debt}")
    print(f"LIQUIDATABLE per stored fields: {len(liquidatable)}")
    for m, adj, unh, bmv, alw, pk in liquidatable[:15]:
        print(f"  {pk}  adj_debt=${adj:,.0f} unhealthy=${unh:,.0f} margin=${m:,.0f}")
    print(f"\nclosest to zero margin (still healthy):")
    for m, adj, unh, bmv, alw, pk in rows[:10]:
        if m >= 0:
            pct = (adj / unh * 100) if unh > 0 else 0
            print(f"  {pk}  adj=${adj:,.0f} unh=${unh:,.0f} margin=${m:,.0f} ({pct:.1f}% of trigger)")
    # sanity histogram of debt sizes
    import statistics
    debts = [x[1] for x in rows]
    if debts:
        print(f"\ndebt stats: median=${statistics.median(debts):,.0f} "
              f"p90=${sorted(debts)[int(len(debts)*0.9)]:,.0f} max=${max(debts):,.0f}")

    # dump candidates for follow-up (slot-age check + owner)
    out = [{"pubkey": pk, "adj_debt": a, "unhealthy": u, "margin": m}
           for m, a, u, b, al, pk in rows if m < max(500.0, 0.05 * a)]
    Path("kamino_candidates.json").write_text(json.dumps(out, indent=1))
    print(f"\nwrote {len(out)} near-line candidates to kamino_candidates.json")

if __name__ == "__main__":
    main()
