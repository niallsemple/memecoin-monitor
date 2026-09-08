#!/usr/bin/env python3
"""
damm_v2_birth_listener.py — minute-zero Meteora DAMM v2 (cp-amm) pool-birth
detection.

Why: DAMM v2 is where new memecoin pools are actually born now (measured
2026-09-08: 41/80 sampled DAMM v2 pools created in the last 7 days vs 0/80
on DLMM). Pool-sized accounts are uniformly 1112 bytes owned by the cp-amm
program, so ONE getProgramAccounts call (dataSize=1112, dataSlice=0)
returns all of them; diffing against the previous run yields births.

Caveat measured 2026-09-08: the 1112-byte class holds ~1.46M accounts while
the datapi only tracks ~137k pools, and the pool discriminator memcmp is
silently ignored by the RPC (same count with/without), so this class likely
includes position accounts. Births that do not resolve against the REST API
are still recorded (resolved=false); the resolved subset is the
high-signal one.

First run baselines silently. Each birth is appended to
damm_v2_births.jsonl {t, pool, name?, x_addr?, y_addr?, tvl?, age_h?,
launchpad?} resolved against the DAMM v2 REST API (new pools may take
minutes to appear; unresolved fields stay null and the collector's births
pass picks the pool up later).

Runs as a mandatory step in the EVM watcher interval automation (~20min
cadence => pools caught at age ~0-20min instead of hours).
"""
import json, os, time, urllib.request

MON = os.path.dirname(os.path.abspath(__file__))
KEY = open(os.path.join(MON, "helius_key.txt")).read().strip()
RPC = f"https://mainnet.helius-rpc.com/?api-key={KEY}"
CPAMM = "cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG"
STATE = os.path.join(MON, "damm_v2_birth_state.json")
OUT = os.path.join(MON, "damm_v2_births.jsonl")
API = "https://damm-v2.datapi.meteora.ag/pools"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


def rpc(method, params, timeout=120):
    p = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                    "params": params}).encode()
    req = urllib.request.Request(RPC, data=p,
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def resolve(pool):
    try:
        req = urllib.request.Request(f"{API}/{pool}", headers=UA)
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.load(r)
        tx, ty = d.get("token_x") or {}, d.get("token_y") or {}
        ca = d.get("created_at")
        age_h = round((time.time() - ca / 1000) / 3600, 3) if ca else None
        return {"name": d.get("name"),
                "x_addr": tx.get("address"), "y_addr": ty.get("address"),
                "tvl": d.get("tvl"), "age_h": age_h,
                "launchpad": d.get("launchpad"),
                "x_verified": tx.get("is_verified"),
                "freeze_disabled": tx.get("freeze_authority_disabled"),
                "x_holders": tx.get("holders"), "x_mc": tx.get("market_cap")}
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
            [CPAMM, {"encoding": "base64",
                     "dataSlice": {"offset": 0, "length": 0},
                     "filters": [{"dataSize": 1112}]}])
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
                rec["resolved"] = bool(rec.get("name"))
                f.write(json.dumps(rec) + "\n")
                n_written += 1
    json.dump({"seen": sorted(now), "updated": time.time()},
              open(STATE, "w"))
    print(f"damm-v2 births: {len(now)} pools known, "
          f"{'baseline set' if baseline else f'{n_written} new'}")


if __name__ == "__main__":
    main()
