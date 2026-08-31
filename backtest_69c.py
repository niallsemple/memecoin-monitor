"""§69c: mark-to-deadline replay — what a LIVE poller actually gets.
Balances are polled every ~15s even when no trades print, so abort and
time-stop exits fill at the price observed AT the deadline (last trade at
or before it), not at the final mark of a dead pool. Rugs that collapsed
BEFORE the deadline still book -100%; rugs after the deadline don't exist
for us because we already exited.
Grid: veto variants x abort_min {15, 30}. Same entry trigger and 1.5x
freeroll / 0.5 trail stack throughout."""
import json, time, collections, pathlib

MON = pathlib.Path("/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor")
P_TARGET, P_SELL = 1.5, 0.75
P_TRAIL = 0.5
P_TS_MIN = 120
P_NET_MIN, P_NB_MIN, P_FLOW_MIN = 25.0, 10, 2.0
P_ABORT_R = 1.15
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


def simulate(xs, delay_min=0, veto=None, abort_min=30):
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
        w = xs[ti + 1:j + 1]
        sells = [x for x in w if x["side"] == "sell"]
        buys_sol = sum(x.get("sol") or 0 for x in w if x["side"] == "buy")
        if veto == "bigsell25" and any((x.get("sol") or 0) > 25
                                       for x in sells):
            continue
        if veto == "decay10" and xs[j]["mcap_sol"] < 0.9 * trig["mcap_sol"]:
            continue
        ei = j
        break
    if ei is None:
        return {"ret": 0.0, "entered": False, "entry_t": trig["t"],
                "peak": 1.0}
    emc = xs[ei]["mcap_sol"]
    if emc <= 0:
        return None
    t0 = xs[ei]["t"]
    proceeds, pos, peak, fr, reason = 0.0, 1.0, 1.0, False, None

    def price_at(deadline_s):
        """mcap a live poller saw at the deadline: last trade <= deadline."""
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
            proceeds += P_SELL * fill
            pos -= P_SELL
            fr = True
        if r <= P_TRAIL * peak and pos > 0:
            proceeds += pos * fill; pos = 0; reason = "trail"; break
        if not fr and mins >= abort_min and r < P_ABORT_R and pos > 0:
            proceeds += pos * fill; pos = 0; reason = "abort"; break
        if not fr and mins >= P_TS_MIN:
            proceeds += pos * fill; pos = 0; reason = "timestop"; break
    if pos > 0 and not fr:
        # deadline passed without a trade to evaluate: live poller fills
        # at the price observed AT the deadline (mark-to-deadline)
        mins_now = (time.time() - t0) / 60
        if mins_now >= abort_min:
            r_a = price_at(abort_min * 60)
            if r_a < P_ABORT_R:
                proceeds += pos * r_a; pos = 0; reason = "abort"
        if pos > 0 and mins_now >= P_TS_MIN:
            r_t = price_at(P_TS_MIN * 60)
            proceeds += pos * r_t; pos = 0; reason = "timestop"
    if pos > 0:
        total = proceeds + pos * (xs[-1]["mcap_sol"] / emc)
    else:
        total = proceeds
    return {"ret": total - 1, "peak": peak, "entered": True,
            "reason": reason or "open", "entry_t": t0}


variants = []
for am in (15, 30):
    variants += [(f"E25 a{am}", 0, None, am),
                 (f"D10+bigsell25 a{am}", 10, "bigsell25", am),
                 (f"D10+decay10 a{am}", 10, "decay10", am)]

for label, use_cutoff in (("POST-CUTOFF (outage era)", True),
                          ("ALL HISTORY", False)):
    print(f"\n{'=' * 70}\n{label} — mark-to-deadline fills\n{'=' * 70}")
    print(f"{'variant':<20} {'n':>3} {'exp':>9} {'wins':>7} {'rugs':>5} "
          f"{'vetoed':>7} {'exits'}")
    for name, d, v, am in variants:
        rets, wins, rugs, vetoed = [], 0, 0, 0
        reasons = collections.Counter()
        for m, xs in tr.items():
            r = simulate(xs, d, v, am)
            if r is None:
                continue
            if use_cutoff and r["entry_t"] <= CUTOFF:
                continue
            if not r["entered"]:
                vetoed += 1
                continue
            rets.append(r["ret"])
            reasons[r["reason"]] += 1
            if r["ret"] > 0:
                wins += 1
            if r["ret"] <= -0.9:
                rugs += 1
        exp = sum(rets) / len(rets) if rets else 0.0
        w = f"{wins}/{len(rets)}" if rets else "-"
        ex = " ".join(f"{k}:{v}" for k, v in reasons.most_common())
        print(f"{name:<20} {len(rets):>3} {exp:>+9.4f} {w:>7} {rugs:>5} "
              f"{vetoed:>7} {ex}")
