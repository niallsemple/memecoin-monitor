#!/usr/bin/env python3
"""kamino_prestage.py — pre-stage ATAs for the top main-market Kamino reserves
so the liquidation fire tx never carries ATA-creation ixs (§461: KLend's
check_refresh sysvar scan panics on <8B ix data).

Creates (idempotent) our wallet's ATAs for each top reserve's liquidity mint
AND collateral (kToken) mint. Cost ~0.00204 SOL rent each, recoverable by
closing. Real on-chain writes — owner pre-authorized.
"""
import json, time
from pathlib import Path
import urllib.request
import kamino_hunt as kh
import live_trader as lt

W = json.loads((Path(__file__).parent / "live_wallet.json").read_text())["address"]
MKT = "7u3HeHxYDLhnCoErrtycNokbQYbWGzLs6JSDqGAv5PfF"
TOP_N = 6
PER_TX = 4


def top_reserves(n: int) -> list:
    url = f"https://api.kamino.finance/kamino-market/{MKT}/reserves/metrics"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        ms = json.loads(r.read())
    def usd(m):
        try:
            return float(m.get("totalSupplyUsd") or m.get("totalSupply") or 0)
        except Exception:
            return 0.0
    ms.sort(key=usd, reverse=True)
    out = []
    for m in ms[:n]:
        out.append({"reserve": m["reserve"], "symbol": m.get("liquidityToken"),
                    "liq_mint": m.get("liquidityTokenMint"),
                    "col_mint": m.get("collateralMint") or m.get("collateralTokenMint")})
    return out


def create_ix(ata_addr: str, mint: str, tp: str):
    return (lt.b58dec(kh.ATA_PROG), [
        (lt.b58dec(W), True, True),
        (lt.b58dec(ata_addr), True, False),
        (lt.b58dec(W), False, False),
        (lt.b58dec(mint), False, False),
        (lt.b58dec(kh.SYS_PROG), False, False),
        (lt.b58dec(tp), False, False)], b"\x01")  # CreateIdempotent


def main():
    rs = top_reserves(TOP_N)
    print(f"top {len(rs)} reserves:")
    todo = {}
    for r in rs:
        print(f"  {r['symbol']:10s} {r['reserve'][:12]}.. liq={r['liq_mint'][:8] if r['liq_mint'] else '?'}.. col={r['col_mint'][:8] if r['col_mint'] else '?'}..")
        for mint in (r["liq_mint"], r["col_mint"]):
            if mint:
                todo[mint] = None
    # resolve token programs + derive ATAs
    mints = sorted(todo)
    owners = {}
    for m in mints:
        owners[m] = kh.mint_owner(m)
        time.sleep(0.05)
    atas = {m: kh.ata(W, m, owners[m]) for m in mints}
    # existence check in one batch
    res = kh.rpc("getMultipleAccounts", [list(atas.values()),
                                         {"encoding": "base64"}])["result"]["value"]
    missing = [m for m, v in zip(mints, res) if not v]
    print(f"\n{len(mints)} mints → {len(missing)} ATAs missing")
    if not missing:
        print("all pre-staged already"); return
    sigs = []
    for i in range(0, len(missing), PER_TX):
        chunk = missing[i:i+PER_TX]
        ixs = [create_ix(atas[m], m, owners[m]) for m in chunk]
        tx = lt.build_legacy_tx(lt.b58dec(W), ixs)
        resp = kh.rpc("sendTransaction", [tx, {"encoding": "base64",
                                               "skipPreflight": False}])
        sig = (resp.get("result") if isinstance(resp, dict) else None)
        err = resp.get("error") if isinstance(resp, dict) else None
        print(f"  tx {i//PER_TX+1}: {sig or err}")
        if sig:
            sigs.append(sig)
        time.sleep(1.0)
    # confirm
    time.sleep(3)
    res2 = kh.rpc("getMultipleAccounts", [[atas[m] for m in missing],
                                          {"encoding": "base64"}])["result"]["value"]
    ok = sum(1 for v in res2 if v)
    print(f"confirmed {ok}/{len(missing)} ATAs now exist")
    log = {"ts": time.time(), "created": ok, "sigs": sigs,
           "mints": missing}
    with open("kamino_prestage.jsonl", "a") as f:
        f.write(json.dumps(log) + "\n")


if __name__ == "__main__":
    main()
