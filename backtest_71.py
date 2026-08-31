"""§71: burst-scout gate backtest. Waves are operator-driven: the first
triggers of a wave can't be predicted, so scout them; continue only when
the wave proves itself (an earlier burst member hits 1.3x within 60 min).
Baseline: a15 mark-to-deadline (from §69c), enter every trigger.
Scout-gated: first 2 entries of each burst always; entries 3+ only if a
prior burst member reached 1.3x within 60 min of its own entry.
Burst = triggers separated by >2h gaps."""
import json, time, collections, pathlib

MON = pathlib.Path("/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor")
P_TARGET, P_SELL = 1.5, 0.75
P_TRAIL = 0.5
P_TS_MIN = 120
P_ABORT_MIN, P_ABORT_R = 15, 1.15
P_NET_MIN, P_NB_MIN, P_FLOW_MIN = 25.0, 10, 2.0

tr = collections.defaultdict(list)
with open(MON / "mfg_trades.jsonl") as f:
    for line in f:
        try:
            x = json.loads(line)
        except Exception:
            continue
        if (x.get("venue") != "pool" or not x.get("t")
                or x.get("mcap_sol") is None):
            continue
        tr[x["mint"]].append(x)


def simulate(xs):
    """a15 mark-to-deadline; returns dict or None."""
    if len(xs) < 50:
        return None
    xs = sorted(xs, key=lambda x: x["t"])
    nb = ns = 0
    bs = ss = 0.0
    ti = None
    for i, x in enumerate(xs):
        if x["side"] == "buy":
            nb += 1; bs += x.get("sol") or 0
        else:
            ns += 1; ss += x.get("sol") or 0
        if (bs - ss >= P_NET_MIN and nb >= P_NB_MIN
                and nb / max(ns, 1) >= P_FLOW_MIN):
            ti = i
            break
    if ti is None or ti + 1 >= len(xs):
        return None
    ei = ti + 1
    emc = xs[ei]["mcap_sol"]
    if emc <= 0:
        return None
    t0 = xs[ei]["t"]
    proceeds, pos, peak, fr, reason = 0.0, 1.0, 1.0, False, None
    peak60 = 1.0  # peak within 60 min of entry (observable scout evidence)

    def price_at(deadline_s):
        p = emc
        for x in xs[ei + 1:]:
            if x["t"] - t0 > deadline_s:
                break
            p = x["mcap_sol"]
        return p / emc

    body = xs[ei + 1:]
    for j, x in enumerate(body):
        r = x["mcap_sol"] / emc
        peak = max(peak, r)
        if x["t"] - t0 <= 3600:
            peak60 = max(peak60, r)
        mins = (x["t"] - t0) / 60
        fill = (body[j + 1]["mcap_sol"] / emc if j + 1 < len(body) else r)
        if not fr and r >= P_TARGET:
            proceeds += P_SELL * fill; pos -= P_SELL; fr = True
        if r <= P_TRAIL * peak and pos > 0:
            proceeds += pos * fill; pos = 0; reason = "trail"; break
        if not fr and mins >= P_ABORT_MIN and r < P_ABORT_R and pos > 0:
            proceeds += pos * fill; pos = 0; reason = "abort"; break
        if not fr and mins >= P_TS_MIN:
            proceeds += pos * fill; pos = 0; reason = "timestop"; break
    if pos > 0 and not fr:
        mins_now = (time.time() - t0) / 60
        if mins_now >= P_ABORT_MIN:
            r_a = price_at(P_ABORT_MIN * 60)
            if r_a < P_ABORT_R:
                proceeds += pos * r_a; pos = 0; reason = "abort"
        if pos > 0 and mins_now >= P_TS_MIN:
            proceeds += pos * price_at(P_TS_MIN * 60); pos = 0
            reason = "timestop"
    if pos > 0:
        total = proceeds + pos * (xs[-1]["mcap_sol"] / emc)
    else:
        total = proceeds
    return {"ret": total - 1, "peak": peak, "peak60": peak60,
            "entry_t": t0, "reason": reason or "open"}


sims = []
for m, xs in tr.items():
    r = simulate(xs)
    if r:
        r["mint"] = m
        sims.append(r)
sims.sort(key=lambda r: r["entry_t"])

# burst grouping: gap >2h
bursts = []
for r in sims:
    if bursts and r["entry_t"] - bursts[-1][-1]["entry_t"] <= 7200:
        bursts[-1].append(r)
    else:
        bursts.append([r])

print(f"{len(sims)} simulated entries in {len(bursts)} bursts\n")
base_all, gate_all = [], []
for bi, b in enumerate(bursts):
    t0 = time.strftime("%m-%d %H:%M", time.gmtime(b[0]["entry_t"]))
    runners = sum(1 for r in b if r["peak"] >= 1.5)
    base = [r["ret"] for r in b]
    # scout gate: first 2 always; 3+ only if a prior member hit 1.3x in 60m
    gated = []
    for k, r in enumerate(b):
        if k < 2 or any(p["peak60"] >= 1.3 for p in b[:k]):
            gated.append(r["ret"])
    base_all += base
    gate_all += gated
    print(f"burst {bi+1} @{t0} UTC: n={len(b)} runners={runners} "
          f"base_exp={sum(base)/len(base):+.3f} "
          f"gate_n={len(gated)} gate_exp="
          f"{(sum(gated)/len(gated)):+.3f}" if gated else "gate_n=0")

print(f"\nTOTAL baseline: n={len(base_all)} "
      f"exp={sum(base_all)/len(base_all):+.4f} "
      f"wins={sum(1 for v in base_all if v > 0)}/{len(base_all)}")
print(f"TOTAL scout-gated: n={len(gate_all)} "
      f"exp={sum(gate_all)/len(gate_all):+.4f} "
      f"wins={sum(1 for v in gate_all if v > 0)}/{len(gate_all)}")
