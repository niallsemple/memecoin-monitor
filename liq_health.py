#!/usr/bin/env python3
"""
DARWIN liquidation radar — Tier 2: health ranking (recon/paper only).

Combines §342 (balance layout), §345 (bank layout), §346 (Pyth pull oracle)
into one pass:

  1. Bank table: all 437 banks, full data, one gPA call.
  2. Oracle prices: unique Pyth-pull keys (setup byte == 1), one call each.
  3. Mint decimals from SPL mint accounts (byte 44), one call each.
  4. 256-shard balance-region scan (Tier 1), computing per-account with
     marginfi confidence-band pricing (band = min(2.12*conf, 5%*px)):
       assets = Σ asset_shares/2^48 × asset_share_value × (px-band) × asset_w_maint
       liabs  = Σ liab_shares/2^48  × liab_share_value  × (px+band) × liab_w_maint
     health = (assets - liabs) / liabs   (liquidatable when < 0)
  5. Log accounts with liab value >= MIN_DEBT_USD, ranked by health.

Only oracle_setup == 1 (Pyth pull @ offset 610) is priced; other setups are
counted and skipped (their accounts get health=None).
"""
import json
import time
import hashlib
import base64
import struct
import urllib.request
from pathlib import Path

MON = Path(__file__).resolve().parent
KEY = (MON / "helius_key.txt").read_text().strip()
RPC = f"https://mainnet.helius-rpc.com/?api-key={KEY}"
PROG = "MFv2hWf31Z9kbCa1snEPYctwafyhdvnV7FZnsebVacA"
LOG_PATH = str(MON / "liq_health_log.jsonl")
F48 = float(2 ** 48)
MIN_DEBT_USD = 100.0
# marginfi oracle confidence-band pricing (the §355 false-positive fix):
# collateral valued at px - band, liabilities at px + band,
# band = min(CONF_K * conf, CONF_CAP * px).  Raw midpoint pricing produced
# phantom "liquidatable whales"; the program sim showed them healthy.
CONF_K = 2.12      # CONF_INTERVAL_MULTIPLE (marginfi documented 2.12 sigma)
CONF_CAP = 0.05    # MAX_CONF_INTERVAL, fraction of price

ALPHA = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BAL_OFF, STRIDE, SLOTS = 72, 104, 16


def b58encode(b: bytes) -> str:
    n = int.from_bytes(b, "big")
    s = ""
    while n:
        n, r = divmod(n, 58)
        s = ALPHA[r] + s
    return "1" * (len(b) - len(b.lstrip(b"\0"))) + s


def disc(name: str) -> str:
    return b58encode(hashlib.sha256(f"account:{name}".encode()).digest()[:8])


def rpc(method: str, params: list, timeout: int = 300) -> dict:
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    req = urllib.request.Request(RPC, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def i80(b: bytes) -> float:
    return int.from_bytes(b, "little", signed=True) / F48


# Exact-pricing setups: 3 = PythPushOracle (multiplier-free); 4 = SwitchboardPull
# (price @2264 i128 / 1e18, conf from bank oracle_max_confidence fraction);
# 8 = Fixed (bank.config.fixed_price, zero conf, no staleness);
# 22 = PythLST with SPL-stake-pool multiplier. All other setups
# (Kamino/Drift/Solend/JupLend/Staked-SVSP/Scope/PT) carry exchange-rate
# multipliers we do not model yet -> skipped, not mispriced.
PYTH_SETUPS = {3}
SWB_SETUPS = {4}
FIXED_SETUPS = {8}
LST_SETUPS = {22}
SWB_MAX_AGE_S = 3600


def load_banks() -> dict:
    res = rpc("getProgramAccounts", [PROG, {"encoding": "base64",
              "filters": [{"memcmp": {"offset": 0, "bytes": disc("Bank")}}]}])["result"]
    banks = {}
    for r in res:
        raw = base64.b64decode(r["account"]["data"][0])
        if len(raw) < 642:
            continue
        entries = []  # (collateral_emode_tag, asset_weight_maint)
        emode_tag = 0
        risk_tier = 0
        if len(raw) >= 1344:
            risk_tier = raw[784]  # 0=Collateral, 1=Isolated (isolated collateral = 0 value)
            emode_tag = struct.unpack("<H", raw[920:922])[0]
            for i in range(10):  # MAX_EMODE_ENTRIES
                o = 944 + 40 * i
                tag = struct.unpack("<H", raw[o:o + 2])[0]
                if tag:
                    entries.append((tag, i80(raw[o + 24:o + 40])))  # maint weight @+24
        banks[r["pubkey"]] = {
            "mint": b58encode(raw[8:40]),
            "asset_sv": i80(raw[80:96]),
            "liab_sv": i80(raw[96:112]),
            "aw_maint": i80(raw[312:328]),
            "lw_maint": i80(raw[344:360]),
            "op_state": raw[608],   # 1=Operational; only Initial margin cares
            "setup": raw[609],      # OracleSetup discriminant (§357 fix: was 608)
            "oracle": b58encode(raw[610:642]),
            "max_conf": struct.unpack("<I", raw[804:808])[0] if len(raw) >= 824 else 0,
            "fixed_px": i80(raw[808:824]) if len(raw) >= 824 else 0.0,
            "oracle2": b58encode(raw[642:674]),  # LST stake pool / kamino reserve
            "mult": None,           # set by load_multipliers
            "risk_tier": risk_tier,
            "emode_tag": emode_tag,
            "emode_entries": entries,
        }
    return banks


def load_prices(banks: dict) -> dict:
    keys = {b["oracle"] for b in banks.values() if b["setup"] in PYTH_SETUPS | SWB_SETUPS}
    swb_oracles = {b["oracle"]: b["max_conf"] for b in banks.values()
                   if b["setup"] in SWB_SETUPS}
    px = {}
    for k in keys:
        if k in swb_oracles:
            # Switchboard pull: PullFeedAccountData — result.value i128 @2264
            # (abs), last_update_timestamp i64 @2216. PRECISION = 18.
            # conf band = px * min(max_conf / 2^32, 0.05); 0 disables band.
            try:
                v = rpc("getAccountInfo", [k, {"encoding": "base64"}])["result"]["value"]
                if not v:
                    continue
                d = base64.b64decode(v["data"][0])
                if len(d) < 2384:
                    continue
                value = int.from_bytes(d[2264:2280], "little", signed=True)
                pub = struct.unpack("<q", d[2216:2224])[0]
                price = value / 10.0 ** 18
                if not (0 < abs(price) < 10 ** 15):
                    continue
                frac = min(swb_oracles[k] / float(2 ** 32), CONF_CAP)
                px[k] = {"px": price, "conf_px": price * frac,
                         "age_s": time.time() - pub, "swb": True}
            except Exception:
                pass
            time.sleep(0.05)
            continue
        try:
            v = rpc("getAccountInfo", [k, {"encoding": "base64"}])["result"]["value"]
            if not v:
                continue
            d = base64.b64decode(v["data"][0])
            if len(d) < 101:
                continue
            price = struct.unpack("<q", d[73:81])[0]
            conf = struct.unpack("<Q", d[81:89])[0]
            expo = struct.unpack("<i", d[89:93])[0]
            pub = struct.unpack("<q", d[93:101])[0]
            if not (-30 <= expo <= 0) or not (0 < abs(price) < 10 ** 15):
                continue
            px[k] = {"px": price * 10.0 ** expo,
                     "conf_px": conf * 10.0 ** expo,
                     "age_s": time.time() - pub}
        except Exception:
            pass
        time.sleep(0.05)
    return px


def load_multipliers(banks: dict) -> None:
    """PythLST banks: LST/SOL rate = pool.total_lamports / pool.pool_token_supply
    (SPL stake pool layout, u64 @258 / @266 — verified vs Sanctum pool §357)."""
    for b in banks.values():
        if b["setup"] in PYTH_SETUPS | SWB_SETUPS | FIXED_SETUPS:
            b["mult"] = 1.0
        elif b["setup"] in LST_SETUPS:
            try:
                v = rpc("getAccountInfo", [b["oracle2"], {"encoding": "base64"}])["result"]["value"]
                d = base64.b64decode(v["data"][0])
                tl = struct.unpack("<Q", d[258:266])[0]
                pts = struct.unpack("<Q", d[266:274])[0]
                if tl > 0 and pts > 0:
                    b["mult"] = tl / pts
            except Exception:
                pass
            time.sleep(0.05)


def load_decimals(banks: dict) -> dict:
    mints = {b["mint"] for b in banks.values()}
    dec = {}
    for m in mints:
        try:
            v = rpc("getAccountInfo", [m, {"encoding": "base64"}])["result"]["value"]
            d = base64.b64decode(v["data"][0])
            dec[m] = d[44]
        except Exception:
            pass
        time.sleep(0.05)
    return dec


def health_scan(banks: dict, px: dict, dec: dict) -> dict:
    t0 = time.time()
    material = []
    scanned = skipped_setup = stale_oracle = 0
    for byte_val in range(256):
        resp = rpc("getProgramAccounts", [PROG, {
            "encoding": "base64",
            "dataSlice": {"offset": BAL_OFF, "length": STRIDE * SLOTS},
            "filters": [
                {"memcmp": {"offset": 0, "bytes": disc("MarginfiAccount")}},
                {"memcmp": {"offset": 40, "bytes": b58encode(bytes([byte_val]))}},
            ],
        }])
        for r in resp.get("result") or []:
            scanned += 1
            raw = base64.b64decode(r["account"]["data"][0])
            slots = []
            bad = False
            for i in range(SLOTS):
                o = i * STRIDE
                if o + STRIDE > len(raw) or raw[o] != 1:
                    continue
                bpk = b58encode(raw[o + 1:o + 33])
                b = banks.get(bpk)
                if not b:
                    continue
                d = dec.get(b["mint"])
                if b["mult"] is None:
                    skipped_setup += 1
                    bad = True
                    break
                if b["setup"] in FIXED_SETUPS:
                    if b["fixed_px"] <= 0:
                        bad = True
                        break
                    p = {"px": b["fixed_px"], "conf_px": 0.0, "age_s": 0}
                else:
                    p = px.get(b["oracle"])
                if not p or d is None or d > 18:
                    bad = True
                    break
                max_age = SWB_MAX_AGE_S if p.get("swb") else 120
                if p["age_s"] > max_age:
                    stale_oracle += 1
                    bad = True
                    break
                a_sh = i80(raw[o + 40:o + 56]) * b["asset_sv"]
                l_sh = i80(raw[o + 56:o + 72]) * b["liab_sv"]
                # shares x share_value = native token units; /10^d -> tokens
                # marginfi prices collateral LOW and debt HIGH by the oracle
                # confidence band — midpoint pricing here was the §355 bug.
                band = min(CONF_K * p["conf_px"], CONF_CAP * p["px"])
                slots.append({"b": b,
                              "a_nat": a_sh / (10 ** d),
                              "l_nat": l_sh / (10 ** d),
                              "px_lo": (p["px"] - band) * b["mult"],
                              "px_hi": (p["px"] + band) * b["mult"]})
            if bad:
                continue
            liab_slots = [s for s in slots if s["l_nat"] > 0]
            if not liab_slots:
                continue
            # Emode: reconcile the emode configs of EVERY liability bank the
            # account borrows from — a tag survives only if present in all of
            # them (weight = min). A liability bank with no entries zeroes it.
            rec = None
            for s in liab_slots:
                ent = dict(s["b"]["emode_entries"])
                if rec is None:
                    rec = ent
                else:
                    for t in list(rec):
                        if t in ent:
                            rec[t] = min(rec[t], ent[t])
                        else:
                            del rec[t]
            rec = rec or {}
            assets = liabs = 0.0
            for s in slots:
                b = s["b"]
                if s["a_nat"] > 0 and b["risk_tier"] != 1:
                    w = b["aw_maint"]
                    if b["emode_tag"]:
                        w = max(w, rec.get(b["emode_tag"], 0.0))
                    assets += s["a_nat"] * s["px_lo"] * w
                if s["l_nat"] > 0:
                    liabs += s["l_nat"] * s["px_hi"] * b["lw_maint"]
            if liabs > 0:
                material.append({
                    "pk": r["pubkey"],
                    "assets": round(assets, 2),
                    "liabs": round(liabs, 2),
                    "health": round((assets - liabs) / liabs, 4),
                })
    material = [m for m in material if m["liabs"] >= MIN_DEBT_USD]
    material.sort(key=lambda m: m["health"])
    return {
        "ts": time.time(),
        "kind": "liq_health_tier2",
        "scanned": scanned,
        "material": len(material),
        "skipped_setup_slots": skipped_setup,
        "stale_oracle_slots": stale_oracle,
        "secs": round(time.time() - t0, 1),
        "top20": material[:20],
        "liquidatable_now": [m for m in material if m["health"] < 0][:20],
    }


def main() -> dict:
    t0 = time.time()
    banks = load_banks()
    load_multipliers(banks)
    px = load_prices(banks)
    dec = load_decimals(banks)
    rec = health_scan(banks, px, dec)
    rec["banks"] = len(banks)
    rec["oracles_priced"] = len(px)
    rec["mints"] = len(dec)
    rec["total_secs"] = round(time.time() - t0, 1)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


if __name__ == "__main__":
    r = main()
    print(json.dumps({k: v for k, v in r.items() if k != "top20" and k != "liquidatable_now"}, indent=1))
    print("closest to liquidation:")
    for m in r["top20"][:10]:
        print(f"  {m['pk'][:12]}  health={m['health']:+.4f}  assets=${m['assets']:,.0f}  liabs=${m['liabs']:,.0f}")
    if r["liquidatable_now"]:
        print("LIQUIDATABLE NOW:")
        for m in r["liquidatable_now"][:10]:
            print(f"  {m['pk'][:12]}  health={m['health']:+.4f}  liabs=${m['liabs']:,.0f}")
