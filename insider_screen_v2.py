#!/usr/bin/env python3
"""insider_screen_v2.py — §215: creation-transfer-classified overhang.

v1 flaw (§214): pool-buyer cross-reference only — bonding-curve buyers
who never touch the pool read as insiders, inverting the metric
(green EoBTrx 44.3% > LUTN drain 13.75%).

v2: for each top holder, find the FIRST tx that credited its token
account and classify by origin:
  - tx touches pump.fun curve (6EF8rrec...), PumpSwap AMM
    (pAMMBay6...), or Jupiter (JUP6...)  => BUYER (economic purchase)
  - otherwise (plain SPL transfer from deployer/mint authority/
    another wallet at creation)                          => INSIDER

overhang_v2% = supply share held by INSIDER-classified top holders.
Works live at entry time (all ATAs open); fails retrospectively once
killer ATAs close — by design, the gate only needs entry time.

Usage: python3 insider_screen_v2.py <mint> [mint...]
"""
import json, sys, time, base64, urllib.request
from pathlib import Path

MON = Path(__file__).resolve().parent
RPCS = ["https://mainnet.helius-rpc.com/?api-key="
        + (MON / "helius_key.txt").read_text().strip(),
        "https://api.mainnet-beta.solana.com"]
POOLS = json.loads((MON / "mint_pools.json").read_text()) \
    if (MON / "mint_pools.json").exists() else {}
LEDGER = MON / "mfg_wallet_trades.jsonl"

SWAP_PROGS = ("6EF8rre",          # pump.fun bonding curve
              "pAMMBay6",         # PumpSwap AMM
              "JUP6",             # Jupiter aggregator
              "JUP4",             # Jupiter v4
              "whirLbMi",         # Orca whirlpool (defensive)
              )
MIN_SHARE = 0.005          # 0.5% — below this, not a whale
CLASSIFY_CAP = 10          # classify at most this many candidate whales
STOP_AT = 0.15             # cumulative insider share where we can stop


def rpc(method, params, tries=3):
    for i in range(tries):
        for url in RPCS:
            try:
                req = urllib.request.Request(
                    url, data=json.dumps({"jsonrpc": "2.0", "id": 1,
                                          "method": method,
                                          "params": params}).encode(),
                    headers={"Content-Type": "application/json"})
                r = json.load(urllib.request.urlopen(req, timeout=25))
                if "result" in r:
                    return r
            except Exception:
                time.sleep(1.0)
        time.sleep(1.7 * (i + 1))
    return {}


def ledger_buyers(mint):
    buyers = set()
    if LEDGER.exists():
        for line in LEDGER.open():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                if r.get("mint") == mint and r.get("side") == "buy":
                    buyers.add(r["wallet"])
            except Exception:
                continue
    return buyers


_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58encode(b):
    n = int.from_bytes(b, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = _B58[r] + out
    pad = sum(1 for c in b if c == 0)
    return "1" * pad + (out or "")


def classify_holder(mint, ata):
    """'buyer' | 'insider' | 'unknown' from first credit tx origin."""
    sigs = rpc("getSignaturesForAddress",
               [ata, {"limit": 30}]).get("result") or []
    if not sigs:
        return "unknown", None
    # oldest first
    for s in reversed(sigs):
        if s.get("err"):
            continue
        tx = rpc("getTransaction",
                 [s["signature"], {"encoding": "json",
                                   "maxSupportedTransactionVersion": 0}]
                 ).get("result")
        time.sleep(1.0)
        if not tx:
            continue
        meta = tx.get("meta") or {}
        keys = [k if isinstance(k, str) else k["pubkey"]
                for k in tx["transaction"]["message"]["accountKeys"]]
        pre = {b["accountIndex"]: float(b["uiTokenAmount"]["amount"])
               for b in meta.get("preTokenBalances", [])
               if b.get("mint") == mint}
        credited = False
        for b in meta.get("postTokenBalances", []):
            if b.get("mint") != mint:
                continue
            i = b["accountIndex"]
            if i < len(keys) and keys[i] == ata:
                if float(b["uiTokenAmount"]["amount"]) - pre.get(i, 0.0) > 0:
                    credited = True
        if not credited:
            continue
        # first credit found — classify by programs touched
        progs = set()
        msg = tx["transaction"]["message"]
        for ix in msg.get("instructions", []):
            pid = ix.get("programId")
            if pid is None:
                continue
            pid = pid if isinstance(pid, str) else keys[pid]
            progs.add(pid)
        for ix in (meta.get("innerInstructions") or []):
            for i2 in ix.get("instructions", []):
                pid = i2.get("programId")
                if isinstance(pid, str):
                    progs.add(pid)
        hit = any(any(pid.startswith(p) for pid in progs)
                  for p in SWAP_PROGS)
        return ("buyer" if hit else "insider"), s["signature"]
    return "unknown", None


def screen_v2(mint, verbose=False):
    supply_r = rpc("getTokenSupply", [mint])
    supply = float(supply_r.get("result", {}).get("value", {})
                   .get("amount", 0))
    if not supply:
        return {"mint": mint, "error": "no supply"}
    la = rpc("getTokenLargestAccounts", [mint])
    accts = la.get("result", {}).get("value", [])
    if not accts:
        return {"mint": mint, "error": "no largest accounts"}
    addrs = [a["address"] for a in accts]
    owners_r = rpc("getMultipleAccounts", [addrs, {"encoding": "base64"}])
    owners = {}
    for addr, acc in zip(addrs, owners_r.get("result", {}).get("value", [])):
        if acc and acc.get("data"):
            raw = base64.b64decode(acc["data"][0])
            owners[addr] = b58encode(raw[32:64])
    buyers = ledger_buyers(mint)
    pool = POOLS.get(mint)
    rows, overhang, classified = [], 0.0, 0
    for a in accts:
        amt = float(a["amount"])
        share = amt / supply
        owner = owners.get(a["address"], "?")
        is_pool = (a["address"] == pool) or (owner == pool)
        row = {"share": round(share * 100, 2), "owner": owner[:10],
               "pool": is_pool, "buyer_ledger": owner in buyers}
        if not is_pool and share >= MIN_SHARE and classified < CLASSIFY_CAP \
                and overhang < STOP_AT:
            cls, sig = classify_holder(mint, a["address"])
            classified += 1
            row["cls"] = cls
            if cls == "insider":
                overhang += share
        elif not is_pool and share >= MIN_SHARE:
            row["cls"] = "unclassified"
        rows.append(row)
    return {"mint": mint, "overhang_v2_pct": round(overhang * 100, 2),
            "classified": classified, "top": rows}


if __name__ == "__main__":
    for mint in sys.argv[1:]:
        s = screen_v2(mint)
        if "error" in s:
            print(f"{mint[:8]}… ERROR {s['error']}")
            continue
        print(f"{mint[:8]}… overhang_v2={s['overhang_v2_pct']}%  "
              f"(classified {s['classified']})")
        for r in s["top"]:
            tag = "POOL" if r["pool"] else r.get("cls", "·")
            print(f"    {r['share']:>6}%  {r['owner']}…  {tag}")
        time.sleep(1.0)
