"""§77d: confirmed-entry variant — fix the strict-entry late-fill problem.

s60's weakness (oFxvzBiT): net60/nb20 takes minutes to satisfy, so strict
entry fills LATE at a worse mcap — runners become scratches. Alternative:
enter at the LOOSE trigger price (net25/nb10, next-trade fill), then require
the pool to reach STRICT cumulative thresholds (net60/nb20) within W minutes
of entry. No confirmation -> exit at the deadline price (mark-to-deadline).
Confirmed -> ride with frozen h108 exits.

Grid W in {5,10,15,20} min. Same verified conventions. Informational only.
"""
import json, time, collections, pathlib

MON = pathlib.Path("/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor")
TRADES = MON / "mfg_trades.jsonl"
CUTOFF = 1788060000
FREEROLL_FLOOR = 0.125
L_NET, L_NB, L_FLOW = 25.0, 10, 2.0      # loose trigger (entry timing)
S_NET, S_NB = 60.0, 20                    # strict confirmation (keep/kill)
STAGE1, ABORT_MIN, ABORT_R = (15, 1.08), 30, 1.15
TRAIL, TARGET, SELL, TS_MIN = 0.5, 1.5, 0.75, 120

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


def simulate(xs, confirm_min):
    xs = sorted(xs, key=lambda x: x["t"])
    if len(xs) < 50:
        return None
    nb = ns = 0
    bs = ss = 0.0
    ti = None
    for i, x in enumerate(xs):
        if x.get("side") == "buy":
            nb += 1; bs += x.get("sol") or 0
        else:
            ns += 1; ss += x.get("sol") or 0
        if ((bs - ss) >= L_NET and nb >= L_NB
                and nb / max(ns, 1) >= L_FLOW):
            ti = i
            break
    if ti is None or ti + 1 >= len(xs):
        return None
    ei = ti + 1
    emc = xs[ei]["mcap_sol"]
    t0 = xs[ei]["t"]
    if emc <= 0:
        return None

    # confirmation scan: do STRICT cumulative thresholds hit within W min
    # of entry? (counters continue from the loose trigger state)
    confirmed = False
    j = ei
    while j + 1 < len(xs) and (xs[j + 1]["t"] - t0) <= confirm_min * 60:
        j += 1
        x = xs[j]
        if x.get("side") == "buy":
            nb += 1; bs += x.get("sol") or 0
        else:
            ns += 1; ss += x.get("sol") or 0
        if (bs - ss) >= S_NET and nb >= S_NB:
            confirmed = True
            break
    if not confirmed:
        # exit at the confirmation deadline price (last trade at/before)
        p = emc
        for x in xs[ei + 1:]:
            if x["t"] - t0 > confirm_min * 60:
                break
            p = x["mcap_sol"]
        return {"entry_t": t0, "ret": p / emc - 1, "status": "closed",
                "freerolled": False, "reason": "noconfirm"}

    proceeds, pos, peak, fr, reason = 0.0, 1.0, 1.0, False, None
    body = xs[j + 1:]
    for k, x in enumerate(body):
        r = x["mcap_sol"] / emc
        peak = max(peak, r)
        mins = (x["t"] - t0) / 60

        def fill(trig, _k=k):
            return (body[_k + 1]["mcap_sol"] / emc
                    if _k + 1 < len(body) else trig)

        if not fr and r >= TARGET:
            proceeds += SELL * fill(TARGET); pos -= SELL; fr = True
        if (not fr and mins >= STAGE1[0] and r < STAGE1[1] and pos > 0):
            proceeds += pos * fill(r); pos = 0; reason = "abort15"; break
        if not fr and mins >= ABORT_MIN and r < ABORT_R and pos > 0:
            proceeds += pos * fill(r); pos = 0; reason = "abort"; break
        if r <= TRAIL * peak and pos > 0:
            proceeds += pos * fill(r); pos = 0; reason = "trail"; break
        if not fr and mins >= TS_MIN:
            proceeds += pos * fill(r); pos = 0; reason = "timestop"; break
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
                proceeds += pos * r1; pos = 0; reason = "abort15"
        if pos > 0 and not fr and mins_now >= ABORT_MIN:
            ra = _price_at(ABORT_MIN * 60)
            if ra < ABORT_R:
                proceeds += pos * ra; pos = 0; reason = "abort"
        if pos > 0 and not fr and mins_now >= TS_MIN:
            proceeds += pos * _price_at(TS_MIN * 60); pos = 0
            reason = "timestop"
    if pos > 0:
        total = proceeds + pos * (xs[-1]["mcap_sol"] / emc)
        status = "open"
    else:
        total = proceeds
        status = "closed"
    return {"entry_t": t0, "ret": total - 1, "status": status,
            "freerolled": fr, "reason": reason}


def committed(posns):
    vals = []
    for p in posns:
        if p is None or p["entry_t"] < CUTOFF:
            continue
        if p["status"] == "closed":
            vals.append(p["ret"])
        elif p["freerolled"]:
            vals.append(FREEROLL_FLOOR)
    if not vals:
        return 0, 0.0
    return len(vals), sum(vals) / len(vals)


print(f"{'W_min':<7}{'com_n':<7}{'com_exp':<9}{'all_n':<7}{'all_exp':<9}"
      f"{'noconfirm_share':<9}")
for W in (5, 10, 15, 20):
    posns = [simulate(xs, W) for xs in tr.values()]
    posns = [p for p in posns if p]
    cn, cexp = committed(posns)
    allr = [p["ret"] for p in posns if p["status"] == "closed"]
    aexp = sum(allr) / len(allr) if allr else 0.0
    nc = sum(1 for p in posns if p["reason"] == "noconfirm")
    print(f"{W:<7}{cn:<7}{cexp:<+9}{len(allr):<7}{aexp:<+9}"
          f"{nc / len(posns):<9.2f}")
print("\nRefs: frozen gate h108 = -0.1088 (n=21) | s60 strict late-entry "
      "= +0.0838 (n=14)")
