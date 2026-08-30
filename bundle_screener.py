#!/usr/bin/env python3
"""Bundle screener (BIG_BOYS_PLAYBOOK play #2): insider-launch forensics.

Question: does the BIRTH-BUNDLE fingerprint separate winners from losers?
For each token's earliest buyers (cached in rotation_scan.json /
losers_scan.json), fetch each buyer's wallet history from Helius and compute:

  per wallet:
    - age_h: wallet age in hours at time of its buy (None if >3 pages deep)
    - funder: who sent the wallet its first SOL (None if not found)
    - sold_early: did it sell the mint within 45 min of token birth
  per token:
    - fresh_share: fraction of checked buyers with wallet age < 6h
    - top_funder_share: largest fraction of fresh buyers sharing one funder
    - hold_rate: fraction of fresh buyers NOT selling within 45 min
    - bundle_score = fresh_share * top_funder_share  (1.0 = fully bundled
      by one source and they bought at birth)

Run is checkpointed to bundle_scan.json after every token — safe to re-run
until 'done' tokens cover both cohorts. ~1-3 Helius calls per buyer.
"""
import json, time, urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent
KEY = (ROOT / "helius_key.txt").read_text().strip()
WALLET_TXS = "https://api.helius.xyz/v0/addresses/{}/transactions?api-key={}&limit=100"
OUT = ROOT / "bundle_scan.json"
FRESH_H = 6.0
SELL_WINDOW_M = 45
MAX_PAGES = 3
TOP_BUYERS = 10

state = json.loads((ROOT / "state.json").read_text())["seen"]

def birth_ts(mint):
    v = state.get(f"solana:{mint}") or {}
    pc = (v.get("detect") or {}).get("pair_created")
    return pc / 1000 if pc else None

def wallet_hist(addr):
    """Return (txs_oldest_first, reached_birth)."""
    txs, before = [], None
    for _ in range(MAX_PAGES):
        u = WALLET_TXS.format(addr, KEY) + (f"&before={before}" if before else "")
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "bundle-screener/1.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                page = json.loads(r.read().decode())
        except Exception:
            break
        if not page:
            return txs, True
        txs.extend(page)
        before = page[-1].get("signature")
        time.sleep(0.7)
        if len(page) < 100:
            return txs, True
    return txs, False

def analyze_wallet(addr, mint, born):
    txs, reached = wallet_hist(addr)
    if not txs:
        return {"wallet": addr, "age_h": None, "funder": None, "sold_early": None}
    txs.sort(key=lambda t: t.get("timestamp", 0))
    age_h = None
    if reached and born:
        age_h = round((born - txs[0].get("timestamp", born)) / 3600, 2)
    funder = None
    if reached:
        for tx in txs[:3]:  # funding is in the wallet's first txs
            for nt in (tx.get("nativeTransfers") or []):
                if nt.get("toUserAccount") == addr and (nt.get("amount") or 0) > 0:
                    funder = nt.get("fromUserAccount"); break
            if funder: break
            fp = tx.get("feePayer")
            if fp and fp != addr:
                funder = fp; break
    sold_early = None
    if born:
        sold_early = False
        for tx in txs:
            t = tx.get("timestamp", 0)
            if t < born or t > born + SELL_WINDOW_M * 60:
                continue
            sw = (tx.get("events") or {}).get("swap") or {}
            legs = [sw] + list(sw.get("innerSwaps") or [])
            for leg in legs:
                ins = [x.get("mint") for x in (leg.get("tokenInputs") or [])]
                if mint in ins and tx.get("feePayer") == addr:
                    sold_early = True; break
            if sold_early: break
    return {"wallet": addr, "age_h": age_h, "funder": funder, "sold_early": sold_early}

def token_metrics(buyers, mint, born):
    recs = []
    for b in buyers[:TOP_BUYERS]:
        recs.append(analyze_wallet(b, mint, born))
    fresh = [r for r in recs if r["age_h"] is not None and r["age_h"] < FRESH_H]
    n = len(recs)
    fresh_share = len(fresh) / n if n else 0
    funders = Counter(r["funder"] for r in fresh if r["funder"])
    top_funder_share = (funders.most_common(1)[0][1] / len(fresh)) if len(fresh) >= 2 and funders else 0
    sells = [r["sold_early"] for r in fresh if r["sold_early"] is not None]
    hold_rate = (sells.count(False) / len(sells)) if sells else None
    return {
        "n_checked": n, "n_fresh": len(fresh), "fresh_share": round(fresh_share, 2),
        "top_funder_share": round(top_funder_share, 2), "hold_rate": hold_rate,
        "bundle_score": round(fresh_share * top_funder_share, 3),
        "wallets": recs,
    }

def main():
    done = json.loads(OUT.read_text()) if OUT.exists() else {}
    cohorts = []
    for x in json.loads((ROOT / "rotation_scan.json").read_text()):
        if x["id"].startswith("solana:") and x.get("buyers"):
            cohorts.append(("W", x["id"].split(":", 1)[1], x["buyers"], x.get("peak_x")))
    for x in json.loads((ROOT / "losers_scan.json").read_text()):
        if x["id"].startswith("solana:") and x.get("buyers"):
            cohorts.append(("L", x["id"].split(":", 1)[1], x["buyers"], None))
    todo = [c for c in cohorts if c[1] not in done]
    print(f"cohorts: {sum(1 for c in cohorts if c[0]=='W')}W / {sum(1 for c in cohorts if c[0]=='L')}L, remaining: {len(todo)}")
    t0 = time.time()
    for label, mint, buyers, peak in todo:
        if time.time() - t0 > 240:
            print("time budget hit — re-run to continue"); break
        born = birth_ts(mint)
        m = token_metrics(buyers, mint, born)
        m.update({"label": label, "peak_x": peak, "born": born})
        done[mint] = m
        OUT.write_text(json.dumps(done, indent=1))
        print(f"{label} {mint[:8]} fresh={m['n_fresh']}/{m['n_checked']} "
              f"topFunder={m['top_funder_share']} hold={m['hold_rate']} score={m['bundle_score']}")
    if all(c[1] in done for c in cohorts):
        print("\n== COHORT COMPARISON ==")
        for lab in ("W", "L"):
            rows = [v for v in done.values() if v["label"] == lab]
            fs = sorted(r["fresh_share"] for r in rows)
            tf = sorted(r["top_funder_share"] for r in rows)
            bs = sorted(r["bundle_score"] for r in rows)
            hr = [r["hold_rate"] for r in rows if r["hold_rate"] is not None]
            med = lambda a: a[len(a)//2] if a else 0
            hr_s = f"{sum(hr)/len(hr):.2f}" if hr else "NA"
            print(f"{lab} n={len(rows)}: fresh_share med={med(fs)} | "
                  f"top_funder med={med(tf)} | bundle_score med={med(bs)} "
                  f"mean={sum(bs)/len(bs):.3f} | hold_rate mean={hr_s}")
        print("saved ->", OUT)

if __name__ == "__main__":
    main()
