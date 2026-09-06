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
WATCH_LOG_PATH = str(MON / "liq_shock_watch.jsonl")
F48 = float(2 ** 48)
MIN_DEBT_USD = 100.0
# §374 shock pre-positioning: material accounts with health below this get a
# per-oracle asset/liab USD breakdown logged, so a price-shock watcher can
# recompute health instantly on a sharp dip instead of waiting 20 min for the
# next full scan.
SHOCK_WATCH_MAX_HEALTH = 0.30
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
SVSP_SETUPS = {5}   # StakedWithPythPush: SOL px x SVSP NAV/supply
KAMINO_SETUPS = {6, 7}  # KaminoPythPush / KaminoSwitchboardPull: feed px x reserve rate
DRIFT_SETUPS = {9, 10}  # DriftPythPull / DriftSwitchboardPull: feed px x spot mkt cum. interest
JUP_SETUPS = {15, 16}   # JuplendPythPull / JuplendSwitchboardPull: feed px x token_exchange_price
SWB_MAX_AGE_S = 3600
STAKED_FLAG_ONRAMP = 1024
RENT_PER_BYTE = 6960  # rent-exempt = (128 + len) * 6960 lamports (mainnet constant)

# §368: Drift MinimalSpotMarket (drift-mocks state.rs, disc [100,177,8,107,168,65,65,39]):
# mult = cumulative_deposit_interest u128 / 1e10. Struct offset 456 (+8 disc) = 464.
DRIFT_DISC = bytes([100, 177, 8, 107, 168, 65, 65, 39])
DRIFT_CUM_DEP_INT = 464
# §368: JupLend Lending (juplend-mocks state.rs, repr(C, packed),
# disc [135,199,82,16,249,131,182,241]): mult = token_exchange_price u64 / 1e12.
# Struct offset 107 (+8 disc) = 115.
JUP_DISC = bytes([135, 199, 82, 16, 249, 131, 182, 241])
JUP_TOKEN_EXCH_PX = 115

# Kamino MinimalReserve (refs/kamino_mocks_state.rs, 8616B + 8B disc, repr(C)).
# Discriminator [43,242,204,202,26,247,59,127]. _sf fields are I68F60 u128 (/2^60).
KM_DISC = bytes([43, 242, 204, 202, 26, 247, 59, 127])
KM_AVAILABLE = 224        # u64
KM_BORROWED_SF = 232      # u128 I68F60
KM_MINT_DECIMALS = 272    # u64
KM_PROTOCOL_FEES_SF = 344
KM_REFERRER_FEES_SF = 360
KM_PENDING_REFERRER_SF = 376
KM_MINT_TOTAL_SUPPLY = 2592  # u64 (collateral tokens)
SF60 = float(2 ** 60)


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
            "tag": raw[785] if len(raw) >= 786 else 0,  # asset_tag: 2=staked (§371 6047 gate)
            "oracle": b58encode(raw[610:642]),
            "max_conf": struct.unpack("<I", raw[804:808])[0] if len(raw) >= 824 else 0,
            "fixed_px": i80(raw[808:824]) if len(raw) >= 824 else 0.0,
            # §366: liquidation fees (u32 centi, u32::MAX=100%; 0 => default 2.5%)
            "liq_fee": (struct.unpack("<I", raw[1544:1548])[0] / 4294967295.0
                        if len(raw) >= 1552 else 0.0) or 0.025,
            "ins_fee": (struct.unpack("<I", raw[1548:1552])[0] / 4294967295.0
                        if len(raw) >= 1552 else 0.0) or 0.025,
            "oracle3": b58encode(raw[674:706]),   # SVSP pool stake account
            "oracle4": b58encode(raw[706:738]),   # SVSP onramp (may be default)
            "flags": struct.unpack("<Q", raw[840:848])[0] if len(raw) >= 848 else 0,
            "oracle2": b58encode(raw[642:674]),  # LST stake pool / kamino reserve
            "mult": None,           # set by load_multipliers
            "risk_tier": risk_tier,
            "emode_tag": emode_tag,
            "emode_entries": entries,
        }
    return banks


def load_prices(banks: dict) -> dict:
    keys = {b["oracle"] for b in banks.values()
            if b["setup"] in PYTH_SETUPS | SWB_SETUPS | SVSP_SETUPS | KAMINO_SETUPS
            | DRIFT_SETUPS | JUP_SETUPS}
    swb_oracles = {b["oracle"]: b["max_conf"] for b in banks.values()
                   if b["setup"] in SWB_SETUPS or b["setup"] in (7, 10, 16)}  # Kamino/Drift/Jup SwbPull
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


def fetch_prices_batched(keys, banks: dict) -> dict:
    """§374 part 2: lightweight live-price fetch for a specific set of oracle
    keys via getMultipleAccounts (100/call). Mirrors load_prices parsing but
    returns bare {oracle_key: price} — used by shock_recheck between full scans.
    """
    keys = list(dict.fromkeys(keys))
    swb_conf = {b["oracle"] for b in banks.values()
                if b["setup"] in SWB_SETUPS or b["setup"] in (7, 10, 16)}
    px = {}
    for i in range(0, len(keys), 100):
        batch = keys[i:i + 100]
        try:
            res = rpc("getMultipleAccounts", [batch, {"encoding": "base64"}])
            vals = (res.get("result") or {}).get("value") or []
        except Exception:
            continue
        for k, v in zip(batch, vals):
            if not v:
                continue
            try:
                d = base64.b64decode(v["data"][0])
                if k in swb_conf:
                    if len(d) < 2384:
                        continue
                    value = int.from_bytes(d[2264:2280], "little", signed=True)
                    price = value / 10.0 ** 18
                else:
                    if len(d) < 101:
                        continue
                    price_i = struct.unpack("<q", d[73:81])[0]
                    expo = struct.unpack("<i", d[89:93])[0]
                    if not (-30 <= expo <= 0):
                        continue
                    price = price_i * 10.0 ** expo
                if 0 < abs(price) < 10 ** 15:
                    px[k] = price
            except Exception:
                pass
    return px


def _tail_hooks():
    """§429: independent watcher modules — MUST run even when the liq
    early-returns fire (empty watch list etc.). Byte-bookmarked, each
    isolated; second invocation per pass is a cheap no-op."""
    # §432: h16_early2 + e2_live_bridge moved to tracker_live's 15s
    # e2_fast_loop (single driver — no state-write race; edge decays
    # ~0.04%/trade per second of entry lag, §431).
    for name in ("h16_shadow", "birth_watch", "exec_journal", "dbc_scout",
                 "h16_early", "heat_gauge"):
        try:
            import importlib.util as _ilu
            _sp = _ilu.spec_from_file_location(name, MON / f"{name}.py")
            _m = _ilu.module_from_spec(_sp)
            _sp.loader.exec_module(_m)
            _m.run_pass()
        except Exception:
            pass


def shock_recheck(watch_path: str = WATCH_LOG_PATH) -> list:
    """§374 part 2: re-estimate watched accounts' health from FRESH oracle
    prices without a full rescan. Returns [{pk, health, assets, liabs}] for
    accounts estimated to have crossed below health 0 (small margin applied —
    the hunt drill re-verifies exact on-chain state before any sim/fire).
    """
    _tail_hooks()  # §429: before any early return
    try:
        last = None
        with open(watch_path) as f:
            for line in f:
                if line.strip():
                    last = line
        rec = json.loads(last) if last else {}
    except Exception:
        return []
    accts = rec.get("accounts") or []
    if not accts:
        return []
    banks = load_banks()
    keys = set()
    for a in accts:
        keys |= set(a.get("a_by_key") or {})
        keys |= set(a.get("l_by_key") or {})
    fixed = {k for k in keys if k in banks}  # fixed-setup keys are bank pubkeys
    px_new = fetch_prices_batched([k for k in keys if k not in fixed], banks)
    out = []
    for a in accts:
        old_px = a.get("px_by_key") or {}
        a_new = l_new = 0.0
        ok = True
        for k, usd in (a.get("a_by_key") or {}).items():
            o = old_px.get(k)
            if k in fixed or not o:
                a_new += usd
            elif px_new.get(k):
                a_new += usd * px_new[k] / o
            else:
                ok = False
                break
        if not ok:
            continue
        for k, usd in (a.get("l_by_key") or {}).items():
            o = old_px.get(k)
            if k in fixed or not o:
                l_new += usd
            elif px_new.get(k):
                l_new += usd * px_new[k] / o
            else:
                ok = False
                break
        if not ok or l_new <= 0:
            continue
        h = (a_new - l_new) / l_new
        if h < -0.003:  # margin vs conf-band noise; drill re-verifies exactly
            out.append({"pk": a["pk"], "health": round(h, 4),
                        "assets": round(a_new, 2), "liabs": round(l_new, 2)})
    # §398e: H16 shadow scorer piggybacks on the 90s shock cadence —
    # byte-bookmark tails only; never raises into the liq path.
    try:
        import importlib.util as _iluh
        _sh = _iluh.spec_from_file_location("h16_shadow", MON / "h16_shadow.py")
        _h16 = _iluh.module_from_spec(_sh)
        _sh.loader.exec_module(_h16)
        _h16.run_pass()
    except Exception:
        pass
    # §404b: birth-venue watcher (Meteora DBC + Raydium LaunchLab),
    # same cadence + isolation. Read-only; logs births to
    # birth_watch.jsonl. Discriminator is standard Anchor sighash of the
    # documented init method — unproven until first birth lands; benign
    # if wrong (log-only).
    try:
        import importlib.util as _ilub
        _bw = _ilub.spec_from_file_location("birth_watch", MON / "birth_watch.py")
        _bwm = _ilub.module_from_spec(_bw)
        _bw.loader.exec_module(_bwm)
        _bwm.run_pass()
    except Exception:
        pass
    # §407b: execution journal resolver — mark submitted txs landed/failed.
    try:
        import importlib.util as _ilej2
        _ej2 = _ilej2.spec_from_file_location("exec_journal", MON / "exec_journal.py")
        _ejm2 = _ilej2.module_from_spec(_ej2)
        _ej2.loader.exec_module(_ejm2)
        _ejm2.run_pass()
    except Exception:
        pass
    # §411b: dbc_scout — Jupiter tick capture for birth_watch mints at
    # fixed post-birth ages. Log-only; same cadence + isolation.
    try:
        import importlib.util as _ilds
        _ds = _ilds.spec_from_file_location("dbc_scout", MON / "dbc_scout.py")
        _dsm = _ilds.module_from_spec(_ds)
        _ds.loader.exec_module(_dsm)
        _dsm.run_pass()
    except Exception:
        pass
    # §415b: h16_early — 60s-entry shadow clone (§414 evidence: the move
    # starts before +180s). Parallel forward test, own state/log.
    try:
        import importlib.util as _ilhe
        _he = _ilhe.spec_from_file_location("h16_early", MON / "h16_early.py")
        _hem = _ilhe.module_from_spec(_he)
        _he.loader.exec_module(_hem)
        _hem.run_pass()
    except Exception:
        pass
    # §432: h16_early2 (ex-§417b) now runs ONLY in tracker_live's 15s
    # e2_fast_loop — removed here to keep a single state driver.
    # §422b: heat_gauge — rolling 60min mom60 heat reading for regime-
    # aware sizing. Log-only; writes heat_state.json for darwin_status.
    try:
        import importlib.util as _ilhg
        _hg = _ilhg.spec_from_file_location("heat_gauge", MON / "heat_gauge.py")
        _hgm = _ilhg.module_from_spec(_hg)
        _hg.loader.exec_module(_hgm)
        _hgm.run_pass()
    except Exception:
        pass
    # §432: e2_live_bridge (ex-§427b) also moved to the 15s e2_fast_loop.
    return out


def load_multipliers(banks: dict) -> None:
    """PythLST banks: LST/SOL rate = pool.total_lamports / pool.pool_token_supply
    (SPL stake pool layout, u64 @258 / @266 — verified vs Sanctum pool §357)."""
    for b in banks.values():
        if b["setup"] in PYTH_SETUPS | SWB_SETUPS | FIXED_SETUPS:
            b["mult"] = 1.0
        elif b["setup"] in SVSP_SETUPS:
            # StakedWithPythPush (lst_stake_price.rs): mult = NAV / supply.
            # Onramp path: NAV = (pool.lamports - rent) + (onramp.lamports - rent),
            #   supply_eff = mint_supply + 1e9 (phantom).
            # Legacy: NAV = stake.delegation.stake (@156 in StakeStateV2) - 1e9,
            #   supply_eff = raw mint supply.
            try:
                mint_v = rpc("getAccountInfo", [b["mint"], {"encoding": "base64"}])["result"]["value"]
                supply = struct.unpack("<Q", base64.b64decode(mint_v["data"][0])[36:44])[0]
                pool_v = rpc("getAccountInfo", [b["oracle3"], {"encoding": "base64"}])["result"]["value"]
                pool_data = base64.b64decode(pool_v["data"][0])
                pool_nav = pool_v["lamports"] - (128 + len(pool_data)) * RENT_PER_BYTE
                if b["flags"] & STAKED_FLAG_ONRAMP and b["oracle4"].strip("1"):
                    onr_v = rpc("getAccountInfo", [b["oracle4"], {"encoding": "base64"}])["result"]["value"]
                    onr_data = base64.b64decode(onr_v["data"][0])
                    pool_nav += onr_v["lamports"] - (128 + len(onr_data)) * RENT_PER_BYTE
                    supply_eff = supply + 10 ** 9
                else:
                    pool_nav = int.from_bytes(pool_data[156:164], "little") - 10 ** 9
                    supply_eff = supply
                rate = pool_nav / supply_eff if supply_eff > 0 else 0
                # Bound wide: BAD-like banks legitimately run ~2.26 SOL/token
                # (validated vs program sim §364); only reject garbage (<=0, absurd).
                if 0.001 < rate < 1000:
                    b["mult"] = rate
            except Exception:
                pass
            time.sleep(0.05)
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
        elif b["setup"] in KAMINO_SETUPS:
            # Kamino cToken rate (refs/kamino_mocks_state.rs):
            # mult = total_liq / total_col where
            # total_liq = available + borrowed_sf - protocol_fees_sf
            #             - referrer_fees_sf - pending_referrer_fees_sf
            # (scale_supplies divides both by 10^decimals -> cancels in ratio).
            # NOTE: on-chain requires reserve refreshed in the SAME slot
            # (ensure_kamino_reserve_fresh) — fire txs must bundle the Kamino
            # refresh_reserve ix; scanner uses last-refreshed state for health.
            try:
                v = rpc("getAccountInfo", [b["oracle2"], {"encoding": "base64"}])["result"]["value"]
                d = base64.b64decode(v["data"][0])
                if d[:8] != KM_DISC or len(d) < 2600:
                    continue
                avail = struct.unpack("<Q", d[KM_AVAILABLE:KM_AVAILABLE + 8])[0]
                borr = int.from_bytes(d[KM_BORROWED_SF:KM_BORROWED_SF + 16], "little") / SF60
                pf = int.from_bytes(d[KM_PROTOCOL_FEES_SF:KM_PROTOCOL_FEES_SF + 16], "little") / SF60
                rf = int.from_bytes(d[KM_REFERRER_FEES_SF:KM_REFERRER_FEES_SF + 16], "little") / SF60
                prf = int.from_bytes(d[KM_PENDING_REFERRER_SF:KM_PENDING_REFERRER_SF + 16], "little") / SF60
                supply = struct.unpack("<Q", d[KM_MINT_TOTAL_SUPPLY:KM_MINT_TOTAL_SUPPLY + 8])[0]
                total_liq = avail + borr - pf - rf - prf
                if supply > 0:
                    rate = total_liq / supply
                    # cToken rate appreciates slowly from 1.0; wide bound vs garbage
                    if 0.5 < rate < 100:
                        b["mult"] = rate
            except Exception:
                pass
            time.sleep(0.05)
        elif b["setup"] in DRIFT_SETUPS:
            # §368: mult = cumulative_deposit_interest / 1e10 (interest-bearing
            # scaled balance -> underlying). Sim side note: drift spot market
            # must be fresh on-chain (same-slot rule like Kamino).
            try:
                v = rpc("getAccountInfo", [b["oracle2"], {"encoding": "base64"}])["result"]["value"]
                d = base64.b64decode(v["data"][0])
                if d[:8] != DRIFT_DISC or len(d) < 480:
                    continue
                cum = int.from_bytes(d[DRIFT_CUM_DEP_INT:DRIFT_CUM_DEP_INT + 16], "little")
                rate = cum / 10.0 ** 10
                if 0.5 < rate < 100:
                    b["mult"] = rate
            except Exception:
                pass
            time.sleep(0.05)
        elif b["setup"] in JUP_SETUPS:
            # §368: mult = token_exchange_price / 1e12 (fToken -> underlying).
            try:
                v = rpc("getAccountInfo", [b["oracle2"], {"encoding": "base64"}])["result"]["value"]
                d = base64.b64decode(v["data"][0])
                if d[:8] != JUP_DISC or len(d) < 123:
                    continue
                tep = struct.unpack("<Q", d[JUP_TOKEN_EXCH_PX:JUP_TOKEN_EXCH_PX + 8])[0]
                rate = tep / 10.0 ** 12
                if 0.5 < rate < 100:
                    b["mult"] = rate
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
                slots.append({"b": b, "bpk": bpk,
                              "a_nat": a_sh / (10 ** d),
                              "l_nat": l_sh / (10 ** d),
                              "px_mid": p["px"] * b["mult"],
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
            a_by_key, l_by_key, px_by_key = {}, {}, {}
            for s in slots:
                b = s["b"]
                okey = s["bpk"] if b["setup"] in FIXED_SETUPS else b["oracle"]
                px_by_key.setdefault(okey, s["px_mid"])
                if s["a_nat"] > 0 and b["risk_tier"] != 1:
                    w = b["aw_maint"]
                    if b["emode_tag"]:
                        w = max(w, rec.get(b["emode_tag"], 0.0))
                    usd = s["a_nat"] * s["px_lo"] * w
                    assets += usd
                    a_by_key[okey] = a_by_key.get(okey, 0.0) + usd
                if s["l_nat"] > 0:
                    usd = s["l_nat"] * s["px_hi"] * b["lw_maint"]
                    liabs += usd
                    l_by_key[okey] = l_by_key.get(okey, 0.0) + usd
            if liabs > 0:
                entry = {
                    "pk": r["pubkey"],
                    "assets": round(assets, 2),
                    "liabs": round(liabs, 2),
                    "health": round((assets - liabs) / liabs, 4),
                }
                if assets > 0 and 0 <= (assets - liabs) / liabs < SHOCK_WATCH_MAX_HEALTH:
                    # shock watch: break-even uniform collateral price drop is
                    # s* = 1 - liabs/assets; per-oracle breakdown lets the
                    # tracker re-estimate health from a single live price move.
                    # health < 0 accounts are excluded — already liquidatable
                    # and handled by the normal hunt path each pass.
                    entry["watch"] = {
                        "a_by_key": {k: round(v, 2) for k, v in a_by_key.items()},
                        "l_by_key": {k: round(v, 2) for k, v in l_by_key.items()},
                        "px_by_key": {k: round(v, 8) for k, v in px_by_key.items()
                                      if k in a_by_key or k in l_by_key},
                        "breakeven_drop_pct": round(100 * (1 - liabs / assets), 2),
                    }
                if assets < liabs:
                    # §366 feasibility: a seize improves health only if
                    # w_asset < (1 - liq_fee - ins_fee) * lw_liab for SOME pair.
                    # Failing every pair = twilight zone (e.g. GPkitqFXLPAM:
                    # kUSDC aw 1.0 vs BTC lw 1.05 @5% fees — never liquidatable
                    # via the standard ix; receivership only).
                    feas = False
                    for sa in slots:
                        if sa["a_nat"] <= 0 or sa["b"]["risk_tier"] == 1:
                            continue
                        wa = sa["b"]["aw_maint"]
                        if sa["b"]["emode_tag"]:
                            wa = max(wa, rec.get(sa["b"]["emode_tag"], 0.0))
                        for sl in liab_slots:
                            fee = sl["b"]["liq_fee"] + sl["b"]["ins_fee"]
                            if wa < (1.0 - fee) * sl["b"]["lw_maint"]:
                                feas = True
                                break
                        if feas:
                            break
                    entry["feasible"] = feas
                material.append(entry)
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
        # §386: watched set must come from the FULL material list — when 20+
        # bad-debt accounts sit at health -1.0 they fill top20 and silently
        # evict every near-zero watch candidate (observed 2026-09-06).
        "watched": [m for m in material if "watch" in m][:25],
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
    # §386: watched comes from the full material list (see health_scan), not
    # top20 — bad-debt saturation of top20 must not blind the shock watch.
    watched = rec.get("watched") or []
    if watched:
        with open(WATCH_LOG_PATH, "a") as f:
            f.write(json.dumps({
                "ts": rec["ts"], "kind": "liq_shock_watch",
                "n": len(watched),
                "accounts": [{"pk": m["pk"], "health": m["health"],
                              "assets": m["assets"], "liabs": m["liabs"],
                              **m["watch"]} for m in watched],
            }) + "\n")
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
