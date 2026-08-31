"""§74: two-stage abort hybrid replay.
a15 kills fast-dead campaigns but also kills slow runners (2oFG/jCPN were
<1.10x at minute 15, then ran to 3x). a30 keeps runners but eats fast rugs.
Hybrid: at 15 min exit only if truly dead (r < R1); at 30 min exit if
r < 1.15 (unchanged a30 rule). Freeroll/trail/timestop identical.
Grid R1 in {1.03, 1.05, 1.08} vs pure a15/a30. Honest mark-to-deadline."""
import json, time, collections, pathlib

MON = pathlib.Path("/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor")
P_TARGET, P_SELL = 1.5, 0.75
P_TRAIL = 0.5
P_TS_MIN = 120
P_ABORT_R = 1.15
P_NET_MIN, P_NB_MIN, P_FLOW_MIN = 25.0, 10, 2.0
CUTOFF = 1788060000

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


def simulate(xs, stage1=None):
    """stage1 = (minute, threshold) or None. Returns dict or None."""
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
        mins = (x["t"] - t0) / 60
        fill = (body[j + 1]["mcap_sol"] / emc if j + 1 < len(body) else r)
        if not fr and r >= P_TARGET:
            proceeds += P_SELL * fill; pos -= P_SELL; fr = True
        if r <= P_TRAIL * peak and pos > 0:
            proceeds += pos * fill; pos = 0; reason = "trail"; break
        if stage1 and not fr and mins >= stage1[0] and r < stage1[1] and pos > 0:
            proceeds += pos * fill; pos = 0; reason = "abort15"; break
        if not fr and mins >= 30 and r < P_ABORT_R and pos > 0:
            proceeds += pos * fill; pos = 0; reason = "abort"; break
        if not fr and mins >= P_TS_MIN:
            proceeds += pos * fill; pos = 0; reason = "timestop"; break
    if pos > 0 and not fr:
        mins_now = (time.time() - t0) / 60
        if stage1 and mins_now >= stage1[0]:
            r1 = price_at(stage1[0] * 60)
            if r1 < stage1[1]:
                proceeds += pos * r1; pos = 0; reason = "abort15"
        if pos > 0 and mins_now >= 30:
            r_a = price_at(30 * 60)
            if r_a < P_ABORT_R:
                proceeds += pos * r_a; pos = 0; reason = "abort"
        if pos > 0 and mins_now >= P_TS_MIN:
            proceeds += pos * price_at(P_TS_MIN * 60); pos = 0
            reason = "timestop"
    if pos > 0:
        total = proceeds + pos * (xs[-1]["mcap_sol"] / emc)
        status = "open"
    else:
        total = proceeds
        status = "closed"
    return {"ret": total - 1, "peak": peak, "entry_t": t0,
            "reason": reason or "open", "status": status, "fr": fr}


variants = [("a30 (gate legacy)", None),
            ("a15 pure", (15, 1.15)),
            ("H 15m<1.03", (15, 1.03)),
            ("H 15m<1.05", (15, 1.05)),
            ("H 15m<1.08", (15, 1.08))]

for label, use_cutoff in (("ALL HISTORY", False), ("POST-CUTOFF", True)):
    print(f"\n{'=' * 72}\n{label}\n{'=' * 72}")
    print(f"{'variant':<18} {'n':>3} {'exp':>9} {'wins':>7} {'rugs':>5} "
          f"{'fr_runners':>10} {'runner_ret_sum':>14}")
    for name, s1 in variants:
        rets, wins, rugs, frs, fr_ret = [], 0, 0, 0, 0.0
        for m, xs in tr.items():
            r = simulate(xs, s1)
            if r is None:
                continue
            if use_cutoff and r["entry_t"] <= CUTOFF:
                continue
            rets.append(r["ret"])
            if r["ret"] > 0:
                wins += 1
            if r["ret"] <= -0.85:
                rugs += 1
            if r["fr"]:
                frs += 1
                fr_ret += r["ret"]
        exp = sum(rets) / len(rets) if rets else 0.0
        print(f"{name:<18} {len(rets):>3} {exp:>+9.4f} "
              f"{wins:>3}/{len(rets):<3} {rugs:>5} {frs:>10} "
              f"{fr_ret:>+14.3f}")
