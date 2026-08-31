"""§69b: delayed-entry + cliff-sell-veto backtest on pool trades.
Baseline = E25 (enter next trade after trigger). Variants wait D minutes,
then enter only if the veto rule sees no rug signature in the wait window.
Same §56e exit stack for all. Universe = all mints with >=50 pool trades."""
import json, time, collections, pathlib

MON = pathlib.Path("/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor")
P_TARGET, P_SELL = 1.5, 0.75
P_TRAIL = 0.5
P_TS_MIN = 120
P_ABORT_MIN, P_ABORT_R = 30, 1.15
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


def simulate(xs, delay_min=0, veto=None):
    """Return dict(ret, peak, entered, reason, entry_t) or None."""
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
    if ti is None:
        return None
    trig = xs[ti]
    ei = None
    for j in range(ti + 1, len(xs)):
        if (xs[j]["t"] - trig["t"]) / 60 < delay_min:
            continue
        w = xs[ti + 1:j + 1]  # wait window incl. candidate entry trade
        sells = [x for x in w if x["side"] == "sell"]
        buys_sol = sum(x.get("sol") or 0 for x in w if x["side"] == "buy")
        if veto == "bigsell25" and any((x.get("sol") or 0) > 25
                                       for x in sells):
            continue
        if veto == "flow30":
            ss_w = sum(x.get("sol") or 0 for x in sells)
            if ss_w > 0.3 * max(buys_sol, 1e-9):
                continue
        if veto == "decay10" and xs[j]["mcap_sol"] < 0.9 * trig["mcap_sol"]:
            continue
        ei = j
        break
    if ei is None:
        return {"ret": 0.0, "peak": 1.0, "entered": False,
                "reason": "vetoed", "entry_t": trig["t"]}
    emc = xs[ei]["mcap_sol"]
    if emc <= 0:
        return None
    t0 = xs[ei]["t"]
    proceeds, pos, peak, fr, reason = 0.0, 1.0, 1.0, False, None
    body = xs[ei + 1:]
    for j, x in enumerate(body):
        r = x["mcap_sol"] / emc
        peak = max(peak, r)
        mins = (x["t"] - t0) / 60
        fill = (body[j + 1]["mcap_sol"] / emc if j + 1 < len(body) else r)
        if not fr and r >= P_TARGET:
            proceeds += P_SELL * fill
            pos -= P_SELL
            fr = True
        if not fr and mins >= P_ABORT_MIN and r < P_ABORT_R and pos > 0:
            proceeds += pos * fill; pos = 0; reason = "abort"; break
        if r <= P_TRAIL * peak and pos > 0:
            proceeds += pos * fill; pos = 0; reason = "trail"; break
        if not fr and mins >= P_TS_MIN:
            proceeds += pos * fill; pos = 0; reason = "timestop"; break
    if pos > 0:
        r_last = xs[-1]["mcap_sol"] / emc
        mins_now = (time.time() - t0) / 60
        if not fr and mins_now >= P_ABORT_MIN and r_last < P_ABORT_R:
            proceeds += pos * r_last; pos = 0; reason = "abort"
        elif not fr and mins_now >= P_TS_MIN:
            proceeds += pos * r_last; pos = 0; reason = "timestop"
    if pos > 0:
        total = proceeds + pos * (xs[-1]["mcap_sol"] / emc)
    else:
        total = proceeds
    return {"ret": total - 1, "peak": peak, "entered": True,
            "reason": reason or "open", "entry_t": t0}


variants = [("E25 baseline", 0, None),
            ("D5+bigsell25", 5, "bigsell25"),
            ("D5+flow30", 5, "flow30"),
            ("D5+decay10", 5, "decay10"),
            ("D10+bigsell25", 10, "bigsell25"),
            ("D10+flow30", 10, "flow30"),
            ("D10+decay10", 10, "decay10")]

for label, use_cutoff in (("POST-CUTOFF (outage-era, honest marks)", True),
                          ("ALL HISTORY (incl. Helius era)", False)):
    print(f"\n{'=' * 76}\n{label}\n{'=' * 76}")
    print(f"{'variant':<16} {'n':>3} {'exp':>9} {'wins':>7} {'rugs':>5} "
          f"{'vetoed':>7} {'avgRunnerPeak':>13}")
    for name, d, v in variants:
        rets, wins, rugs, vetoed, peaks = [], 0, 0, 0, []
        for m, xs in tr.items():
            r = simulate(xs, d, v)
            if r is None:
                continue
            if use_cutoff and r["entry_t"] <= CUTOFF:
                continue
            if not r["entered"]:
                vetoed += 1
                continue
            rets.append(r["ret"])
            if r["ret"] > 0:
                wins += 1
            if r["ret"] <= -0.9:
                rugs += 1
            if r["peak"] >= 1.5:
                peaks.append(r["peak"])
        exp = sum(rets) / len(rets) if rets else 0.0
        w = f"{wins}/{len(rets)}" if rets else "-"
        pk = round(sum(peaks) / len(peaks), 2) if peaks else "-"
        print(f"{name:<16} {len(rets):>3} {exp:>+9.4f} {w:>7} {rugs:>5} "
              f"{vetoed:>7} {pk!s:>13}")
