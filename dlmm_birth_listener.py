#!/usr/bin/env python3
"""
dlmm_birth_listener.py — minute-zero Meteora DLMM pool-birth detection.

Why: the REST hot-list collector discovers pools at age 1-6h, too late for
the fast-exit/rotation mania window. Decoding every DLMM program tx is
impossible (~4.3k sigs/min >> Helius quota). Instead: LbPair accounts are
exactly 904 bytes owned by the DLMM program, so ONE getProgramAccounts call
(dataSize=904, dataSlice=0) returns all pool pubkeys in <1s; diffing against
the previous run yields births.

First run baselines silently (all existing pools marked seen, no births).
Each birth is appended to dlmm_births.jsonl {t, pool} and immediately
resolved against the Meteora REST API for name/mints/tvl/age when present
(new pools may take minutes to appear in the API).

Runs as a mandatory step in the EVM watcher interval automation (~20min
cadence => pools caught at age ~0-20min instead of 1-6h).
"""
import json, os, time, urllib.request

MON = os.path.dirname(os.path.abspath(__file__))
KEY = open(os.path.join(MON, "helius_key.txt")).read().strip()
RPC = f"https://mainnet.helius-rpc.com/?api-key={KEY}"
DLMM = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"
STATE = os.path.join(MON, "dlmm_birth_state.json")
OUT = os.path.join(MON, "dlmm_births.jsonl")
API = "https://dlmm.datapi.meteora.ag/pools"


def rpc(method, params, timeout=120):
    p = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                    "params": params}).encode()
    req = urllib.request.Request(RPC, data=p,
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def resolve(pool):
    try:
        with urllib.request.urlopen(f"{API}/{pool}", timeout=20) as r:
            d = json.load(r)
        return {"name": d.get("name"), "x_addr": d.get("mint_x"),
                "y_addr": d.get("mint_y"), "tvl": d.get("liquidity"),
                "age_h": d.get("age_h") or d.get("pool_age_h")}
    except Exception:
        return {}


def main():
    seen = set()
    if os.path.exists(STATE):
        try:
            seen = set(json.load(open(STATE))["seen"])
        except Exception:
            pass
    r = rpc("getProgramAccounts",
            [DLMM, {"encoding": "base64",
                    "dataSlice": {"offset": 0, "length": 0},
                    "filters": [{"dataSize": 904}]}])
    accts = r.get("result") or []
    now = set(a["pubkey"] for a in accts)
    baseline = not seen
    births = sorted(now - seen) if not baseline else []
    n_written = 0
    if births:
        with open(OUT, "a") as f:
            for pool in births:
                rec = {"t": time.time(), "pool": pool}
                rec.update(resolve(pool))
                f.write(json.dumps(rec) + "\n")
                n_written += 1
    json.dump({"seen": sorted(now), "updated": time.time()},
              open(STATE, "w"))
    print(f"dlmm births: {len(now)} pools known, "
          f"{'baseline set' if baseline else f'{n_written} new'}")


if __name__ == "__main__":
    main()
