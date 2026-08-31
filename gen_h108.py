"""One-shot: generate mfg_paper_trades_h108.jsonl so the §74 gate switch is
effective immediately. Duplicates the tracker's paper_score logic with
stage1=(15, 1.08); the tracker overwrites this file every run thereafter."""
import json, time, collections, pathlib

MON = pathlib.Path("/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor")
TRADES = MON / "mfg_trades.jsonl"
OUT = MON / "mfg_paper_trades_h108.jsonl"
P_TARGET, P_SELL = 1.5, 0.75
P_TRAIL = 0.5
P_TS_MIN = 120
P_ABORT_MIN, P_ABORT_R = 30, 1.15
STAGE1 = (15, 1.08)
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
            nb += 1; bs += x.get("sol") or 0
        else:
            ns += 1; ss += x.get("sol") or 0
        if ((bs - ss) >= P_NET_MIN and nb >= P_NB_MIN
                and nb / max(ns, 1) >= P_FLOW_MIN):
            ti = i
            break
    if ti is None:
        continue
    # §74b: realistic fill — entry at the NEXT trade after the trigger
    # (you react to the signal, you can't buy the trade that made it)
    if ti + 1 >= len(xs):
        continue
    ei = ti + 1
    emc = xs[ei]["mcap_sol"]
    t0 = xs[ei]["t"]
    if emc <= 0:
        continue
    proceeds, pos, peak, fr, reason = 0.0, 1.0, 1.0, False, None
    body = xs[ei + 1:]
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
        if (not fr and mins >= STAGE1[0] and r < STAGE1[1] and pos > 0):
            proceeds += pos * fill(r)
            pos = 0
            reason = "abort15"
            break
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
        mins_now = (time.time() - t0) / 60

        def _price_at(deadline_s):
            p = emc
            for x in xs[ei + 1:]:
                if x["t"] - t0 > deadline_s:
                    break
                p = x["mcap_sol"]
            return p / emc

        if not fr and mins_now >= STAGE1[0]:
            r1 = _price_at(STAGE1[0] * 60)
            if r1 < STAGE1[1]:
                proceeds += pos * r1
                pos = 0
                reason = "abort15"
        if pos > 0 and not fr and mins_now >= P_ABORT_MIN:
            r_a = _price_at(P_ABORT_MIN * 60)
            if r_a < P_ABORT_R:
                proceeds += pos * r_a
                pos = 0
                reason = "abort"
        if pos > 0 and not fr and mins_now >= P_TS_MIN:
            proceeds += pos * _price_at(P_TS_MIN * 60)
            pos = 0
            reason = "timestop"
    if pos > 0:
        total = proceeds + pos * (xs[-1]["mcap_sol"] / emc)
        status = "open"
    else:
        total = proceeds
        status = "closed"
    positions.append({"mint": m, "entry_t": t0, "entry_mcap": emc,
                      "freerolled": fr, "peak": round(peak, 3),
                      "status": status, "exit_reason": reason,
                      "ret": round(total - 1, 4),
                      "last_t": xs[-1]["t"], "n_trades": len(xs)})

with OUT.open("w") as f:
    for r in positions:
        f.write(json.dumps(r) + "\n")
closed = [r["ret"] for r in positions if r["status"] == "closed"]
print(f"h108 file written: {len(positions)} positions, "
      f"{len(closed)} closed, all-history exp="
      f"{sum(closed)/len(closed):+.4f}")
