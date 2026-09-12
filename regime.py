"""Regime score — rolling prot-fee flow density across all snapshotted pools.

Rationale (REGIME_RULEBOOK.md): entry-side filters are exhausted; the only
remaining discriminator is market-wide fee-flow regime. Morning 09-12 (fat):
GBR alone ran 8.3-9.6 protSOL/hr and wins were +0.0084-class. Evening (thin):
total across all pools ~3.8 protSOL/hr, everything scratched or struck.

Score = sum of per-pool prot_fee_y deltas over trailing window, SOL/hr.
Logged every call to regime_log.jsonl so we can backtest arming thresholds
against historical win/strike windows.
"""
import json, os, time, collections

MON = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(MON, "bin_snapshots.jsonl")
LOG = os.path.join(MON, "regime_log.jsonl")
WINDOW = 3600  # 60 min trailing

def score(now=None, window=WINDOW, log=True):
    now = now or time.time()
    byp = collections.defaultdict(list)
    with open(SNAP) as f:
        for l in f:
            try: r = json.loads(l)
            except: continue
            if r.get("prot_fee_y") is None: continue
            if now - window <= r["t"] <= now:
                byp[r["pool"]].append((r["t"], r["prot_fee_y"]))
    total = 0.0
    per = {}
    for p, v in byp.items():
        v.sort()
        if len(v) < 2: continue
        dt = v[-1][0] - v[0][0]
        dpf = v[-1][1] - v[0][1]
        if dt < 600 or dpf < 0: continue
        f = dpf / 1e9 / (dt / 3600)
        per[p[:8]] = round(f, 4)
        total += f
    rec = {"t": now, "flow_hr": round(total, 4), "pools": len(per), "top": dict(sorted(per.items(), key=lambda x: -x[1])[:4])}
    if log:
        with open(LOG, "a") as f: f.write(json.dumps(rec) + "\n")
    return rec

if __name__ == "__main__":
    r = score()
    print(f"regime: {r['flow_hr']:.3f} protSOL/hr across {r['pools']} pools | top: {r['top']}")
