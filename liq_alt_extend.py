#!/usr/bin/env python3
"""liq_alt_extend.py — §399: the flash-liquidate recipe blows the 1232-byte
packet by ~116B because 13 reusable non-program accounts (liquidatee mfi
account, its banks/oracles, JitoSOL mint, our liquidator mfi account) are not
in any of our 5 ALTs. Extend table #4 (75/256 used) with exactly those keys.

Run:  python3 liq_alt_extend.py          # dry: report coverage + plan
      python3 liq_alt_extend.py extend   # send the extend tx on-chain
"""
import json
import struct
import sys
import time
from pathlib import Path

MON = Path(__file__).resolve().parent
sys.path.insert(0, str(MON))

import liq_alt as la
import liq_health as lh
lt = la.lt

CANDIDATES = [
    "CjaPWKEBvhmEYvfFewTj5tsZHDaEjVwNBkdQfrt6gMy9",  # our liquidator mfi acct
    "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn",  # JitoSOL mint
    "83UzL8xX38xo1hueyfar2XZbV1aHyZpKdXTuS87gSDX8",  # liquidatee mfi acct
    "4MuP5Hfmwfm31kxfmSzMYcTeh2Zc5WTsmVeWF2VKZPLy",
    "6U91aKa8pmMxkJwBCfPTmUEfZi6dHe7DcFq2ALvB2tbB",
    "AvRYNtHwd26ySFHUoAX1w8iSV18usCMw2dBFX5EkxrEz",
    "9r8BRNSbeM3UjW8MydL643xEWmscXzVKW7dTPyDKnrAA",
    "D8cy77BBepLMngZx6ZukaTff5hCt1HrWyKk3Hnd9oitf",
    "7x4VcEX8aLd3kFsNWULTp1qFgVtDwyWSxpTGQkoMM6XX",
    "59v2cSbCsnyaWymLnsq6TWzE6cEN5KJYNTBNrcP4smRH",
    "BAT1Ndpu5gbLTp2AZkSXP79LJBZfCH4B3zGhi6LtvdhK",
    "4cG31VNF9TzFinNc7BmnjhFvGjxkY3sCETVMtMgbrhPs",
    "J1to1yufRnoWn81KYg1XkTWzmKjnYSnmE2VY8DGUJ9Qv",
]
STATE = MON / "liq_alts.json"


def covered_keys():
    st = json.loads(STATE.read_text())
    cov = set()
    # fetch directly via liq_flash.fetch_alt (raw account parse)
    import liq_flash as lf
    for t in st["tables"]:
        cov.update(lf.fetch_alt(t))
    return st, cov


def main():
    st, cov = covered_keys()
    infos = lh.rpc("getMultipleAccounts", [CANDIDATES, {"encoding": "base64"}])
    vals = (infos.get("result") or {}).get("value") or []
    to_add = []
    for pk, v in zip(CANDIDATES, vals):
        b = lt.b58dec(pk)
        if b in cov:
            print(f"  already covered: {pk}")
            continue
        exe = bool(v and v.get("executable"))
        if exe:
            print(f"  SKIP program (must stay static): {pk}")
            continue
        to_add.append(b)
        print(f"  add: {pk}")
    print(f"to_add: {len(to_add)}")
    if len(sys.argv) < 2 or sys.argv[1] != "extend" or not to_add:
        print("DRY — run with 'extend' to send on-chain")
        return
    ti = len(st["tables"]) - 1
    table = lt.b58dec(st["tables"][ti])
    have = st["done_extends"].get(str(ti), 0)
    if have + len(to_add) > la.MAX_PER_TABLE:
        raise RuntimeError("table full — need a new table")
    auth = lt.b58dec(lt._load_key()[1])
    bal0 = lh.rpc("getBalance", [lt._load_key()[1]])["result"]["value"]
    ext = (la.ALT_PROG, [(table, True, False), (auth, False, True),
                         (auth, True, True), (la.SYS, False, False)],
           struct.pack("<IQ", 2, len(to_add)) + b"".join(to_add))
    la.send([ext], f"extend table {ti} +{len(to_add)}")
    st["done_extends"][str(ti)] = have + len(to_add)
    st["ts"] = time.time()
    STATE.write_text(json.dumps(st, indent=1))
    bal1 = lh.rpc("getBalance", [lt._load_key()[1]])["result"]["value"]
    print(f"SOL spent: {(bal0 - bal1) / 1e9:.6f}; state saved")


if __name__ == "__main__":
    main()
