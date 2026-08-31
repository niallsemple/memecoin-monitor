"""Offline preview of patched paper_score (§68 heartbeat close) on current data.
Mirrors the patched function exactly; does not write anything."""
import json, time, collections, pathlib

MON = pathlib.Path("/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor")
TRADES = MON / "mfg_trades.jsonl"
P_TARGET, P_SELL = 1.5, 0.75
P_TRAIL = 0.5
P_TS_MIN = 120
P_ABORT_MIN, P_ABORT_R = 30, 1.15
P_NET_MIN, P_NB_MIN, P_FLOW_MIN = 25.0, 10, 2.0

tr = collections.defaultdict(list)
with TRADES.open() as f:
    for line in f:
        try:
            x = json.loads(line)
        except Exception:
            continue
        if (x.get("venue") != "pool" or not x.get("t")
                or x.get("mcap_sol") is None):
            continue
        tr[x["mint"]].append(x)

positions = []
for m, xs in tr.items():
    if len(xs) < 50:
        continue
    xs.sort(key=lambda x: x["t"])
    nb = ns = 0
    bs = ss = 0.0
    ti = None
    for i, x in enumerate(xs):
        if x.get("side") == "buy":
            nb += 1
            bs += x.get("sol") or 0
        else:
            ns += 1
            ss += x.get("sol") or 0
        if ((bs - ss) >= P_NET_MIN and nb >= P_NB_MIN
                and nb / max(ns, 1) >= P_FLOW_MIN):
            ti = i
            break
    if ti is None:
        continue
    emc = xs[ti]["mcap_sol"]
    t0 = xs[ti]["t"]
    if emc <= 0:
        continue
    proceeds = 0.0
    pos = 1.0
    peak = 1.0
    fr = False
    reason = None
    body = xs[ti + 1:]
    for j, x in enumerate(body):
        r = x["mcap_sol"] / emc
        peak = max(peak, r)
        mins = (x["t"] - t0) / 60

        def fill(trig, _j=j):
            return (body[_j + 1]["mcap_sol"] / emc
                    if _j + 1 < len(body) else trig)

        if not fr and r >= P_TARGET:
            proceeds += P_SELL * fill(P_TARGET)
            pos -= P_SELL
            fr = True
        if not fr and mins >= P_ABORT_MIN and r < P_ABORT_R and pos > 0:
            proceeds += pos * fill(r)
            pos = 0
            reason = "abort"
            break
        if r <= P_TRAIL * peak and pos > 0:
            proceeds += pos * fill(r)
            pos = 0
            reason = "trail"
            break
        if not fr and mins >= P_TS_MIN:
            proceeds += pos * fill(r)
            pos = 0
            reason = "timestop"
            break
    if pos > 0:
        r_last = xs[-1]["mcap_sol"] / emc
        mins_now = (time.time() - t0) / 60
        if not fr and mins_now >= P_ABORT_MIN and r_last < P_ABORT_R:
            proceeds += pos * r_last
            pos = 0
            reason = "abort"
        elif not fr and mins_now >= P_TS_MIN:
            proceeds += pos * r_last
            pos = 0
            reason = "timestop"
    if pos > 0:
        total = proceeds + pos * (xs[-1]["mcap_sol"] / emc)
        status = "open"
    else:
        total = proceeds
        status = "closed"
    positions.append({"mint": m, "entry_t": t0, "status": status,
                      "exit_reason": reason, "ret": round(total - 1, 4),
                      "peak": round(peak, 3)})

CUTOFF = 1788060000
post = [p for p in positions if p["entry_t"] > CUTOFF]
closed = [p for p in post if p["status"] == "closed"]
print(f"POST-CUTOFF positions: {len(post)}  closed: {len(closed)}")
for p in sorted(post, key=lambda p: -p["entry_t"]):
    et = time.strftime("%m-%d %H:%M", time.gmtime(p["entry_t"]))
    print(f"  {et} {p['mint'][:10]}… {p['status']:6} ret={p['ret']:>8} exit={p['exit_reason']} peak={p['peak']}")
if closed:
    rets = [p["ret"] for p in closed]
    print(f"\npost-fix expectancy: {sum(rets)/len(rets):+.4f}  wins: {sum(1 for v in rets if v>0)}/{len(rets)}")
