#!/usr/bin/env python3
"""Behavioural audit stage (stage 3) — the wallet layer (REPORT.md §12).

Contract audits (GoPlus/RugCheck) answer "can the code scam you?". This stage
answers "are the humans about to dump on you?":

  1. fresh_wallet_supply_pct — % of supply in top-20 holder wallets <24h old
     (sybil/bundler pattern; DeFade flags ~35% as extreme risk)
  2. deployer_age_h — age of the creator wallet in hours
     (one-shot deployer wallets are the serial-rugger pattern)
  3. top20_pct — plain concentration

Needs a Helius RPC key (free tier): put it in helius_key.txt next to this
file or export HELIUS_API_KEY. WITHOUT a key it degrades to 'proxy' mode:
a RugCheck summary danger-scan (weak, but free and live now).

Gate (v1 hypothesis): RISK if fresh_wallet_supply_pct > 25
                      or deployer_age_h < 24
                      or top20_pct > 80.
"""
import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
UA = {"User-Agent": "memecoin-monitor/1.0 (research)"}
RUGCHECK_SUMMARY = "https://api.rugcheck.xyz/v1/tokens/{}/report/summary"
RUGCHECK_FULL = "https://api.rugcheck.xyz/v1/tokens/{}/report"

FRESH_WALLET_H = 24.0
MAX_FRESH_PCT = 25.0
MIN_DEPLOYER_AGE_H = 24.0
MAX_TOP20_PCT = 80.0


def get(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"_error": str(e)}


def helius_key():
    k = os.environ.get("HELIUS_API_KEY", "").strip()
    if k:
        return k
    f = ROOT / "helius_key.txt"
    if f.exists():
        return f.read_text().strip()
    return ""


class Helius:
    def __init__(self, key):
        self.url = f"https://mainnet.helius-rpc.com/?api-key={key}"

    def rpc(self, method, params, timeout=25):
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
        req = urllib.request.Request(self.url, data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.loads(r.read().decode())
            if "error" in d:
                return None
            return d.get("result")
        except Exception:
            return None


def wallet_age_h(hx, owner, now_ts):
    """Age of wallet's OLDEST signature in hours. None if unknown.
    Wallets with >=100 txs are treated as established (age = inf)."""
    sigs = hx.rpc("getSignaturesForAddress", [owner, {"limit": 100}])
    time.sleep(0.2)
    if not sigs:
        return None  # no history = brand new -> age 0 handled by caller via 0.0
    if len(sigs) >= 100:
        return 9999.0
    oldest = sigs[-1].get("blockTime")
    if not oldest:
        return None
    return max(0.0, (now_ts - oldest) / 3600)


def assess(mint, creator=None, mode_note=""):
    """Return {'verdict': 'PASS'|'RISK'|'SKIP', 'mode': 'helius'|'proxy', 'metrics': {...}}"""
    now_ts = datetime.now(timezone.utc).timestamp()
    key = helius_key()

    if not key:
        # --- keyless proxy mode: RugCheck danger scan (weak gate, live now) ---
        s = get(RUGCHECK_SUMMARY.format(mint))
        if "_error" in s:
            return {"verdict": "SKIP", "mode": "proxy", "reason": "rugcheck_unavailable", "metrics": {}}
        dangers = [r.get("name", "?") for r in (s.get("risks") or []) if r.get("level") == "danger"]
        return {
            "verdict": "RISK" if dangers else "PASS",
            "mode": "proxy",
            "metrics": {"dangers": dangers, "score_norm": s.get("score_normalised"),
                        "lpLockedPct": s.get("lpLockedPct")},
            "reason": ("danger:" + ",".join(dangers)) if dangers else "no danger risks (proxy mode)",
        }

    # --- full Helius mode ---
    hx = Helius(key)
    metrics = {}

    if not creator:
        full = get(RUGCHECK_FULL.format(mint))
        time.sleep(1.0)
        creator = full.get("creator") if isinstance(full, dict) else None
    metrics["creator"] = creator

    supply = hx.rpc("getTokenSupply", [mint])
    time.sleep(0.2)
    total = None
    if supply and supply.get("value"):
        try:
            total = float(supply["value"]["amount"])
        except (TypeError, ValueError, KeyError):
            total = None

    la = hx.rpc("getTokenLargestAccounts", [mint])
    time.sleep(0.2)
    if not la or not la.get("value") or not total:
        return {"verdict": "SKIP", "mode": "helius", "reason": "holders_unavailable", "metrics": metrics}

    top = la["value"][:20]
    top_amt = sum(float(a["amount"]) for a in top)
    top20_pct = top_amt / total * 100
    metrics["top20_pct"] = round(top20_pct, 1)

    # resolve owners in one batch
    infos = hx.rpc("getMultipleAccounts", [[a["address"] for a in top], {"encoding": "jsonParsed"}])
    time.sleep(0.2)
    owners = []
    if infos and infos.get("value"):
        for a, info in zip(top, infos["value"]):
            owner = None
            try:
                owner = info["data"]["parsed"]["info"]["owner"]
            except (TypeError, KeyError):
                pass
            owners.append((owner, float(a["amount"])))
    else:
        owners = [(None, float(a["amount"])) for a in top]

    fresh_amt = 0.0
    aged = 0
    for owner, amt in owners:
        if not owner:
            continue
        age = wallet_age_h(hx, owner, now_ts)
        aged += 1
        if age is not None and age < FRESH_WALLET_H:
            fresh_amt += amt
        if aged >= 15:  # cap RPC calls
            break
    fresh_pct = fresh_amt / total * 100
    metrics["fresh_wallet_supply_pct"] = round(fresh_pct, 1)
    metrics["wallets_aged"] = aged

    deployer_age = None
    if creator:
        deployer_age = wallet_age_h(hx, creator, now_ts)
    metrics["deployer_age_h"] = round(deployer_age, 1) if deployer_age is not None else None

    reasons = []
    if fresh_pct > MAX_FRESH_PCT:
        reasons.append(f"fresh_wallets={fresh_pct:.0f}%")
    if deployer_age is not None and deployer_age < MIN_DEPLOYER_AGE_H:
        reasons.append(f"deployer_age={deployer_age:.1f}h")
    if top20_pct > MAX_TOP20_PCT:
        reasons.append(f"top20={top20_pct:.0f}%")

    return {
        "verdict": "RISK" if reasons else "PASS",
        "mode": "helius",
        "metrics": metrics,
        "reason": "; ".join(reasons) if reasons else "behaviour clean",
    }


if __name__ == "__main__":
    import sys
    mint = sys.argv[1]
    out = assess(mint)
    print(json.dumps(out, indent=1))
