"""§76: ENTRY-side grid on the verified engine — the last untested lever.
§75 showed exit tuning cannot flip the sign (best -3.1%). Here we grid the
trigger thresholds (net flow / min buys / flow ratio) and time-of-day entry
gating (wave-locked edge: US-morning 12-15 UTC hotspot per §62).

Committed metric identical to the frozen gate. Exit configs: frozen h108
((15,1.08)/0.5/1.5/0.75) and §75-best ((15,1.10)/0.6/1.5/0.75).
Informational only — does not move the gate.
"""
import json, time, collections, pathlib

MON = pathlib.Path("/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor")
TRADES = MON / "mfg_trades.jsonl"
CUTOFF = 1788060000
FREEROLL_FLOOR = 0.125

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


def simulate(xs, net_min, nb_min, flow_min, hours,
             stage1, abort_min, abort_r, trail, target, sell, ts_min):
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
        if ((bs - ss) >= net_min and nb >= nb_min
                and nb / max(ns, 1) >= flow_min):
            ti = i
            break
    if ti is None or ti + 1 >= len(xs):
        return None
    ei = ti + 1
    emc = xs[ei]["mcap_sol"]
    t0 = xs[ei]["t"]
    if emc <= 0:
        return None
    if hours is not None:
        hr = time.gmtime(t0).tm_hour
        if hr not in hours:
            return None
    proceeds, pos, peak, fr, reason = 0.0, 1.0, 1.0, False, None
    body = xs[ei + 1:]
    for j, x in enumerate(body):
        r = x["mcap_sol"] / emc
        peak = max(peak, r)
        mins = (x["t"] - t0) / 60

        def fill(trig, _j=j):
            return (body[_j + 1]["mcap_sol"] / emc
                    if _j + 1 < len(body) else trig)

        if not fr and r >= target:
            proceeds += sell * fill(target); pos -= sell; fr = True
        if (stage1 and not fr and mins >= stage1[0]
                and r < stage1[1] and pos > 0):
            proceeds += pos * fill(r); pos = 0; reason = "abort15"; break
        if not fr and mins >= abort_min and r < abort_r and pos > 0:
            proceeds += pos * fill(r); pos = 0; reason = "abort"; break
        if r <= trail * peak and pos > 0:
            proceeds += pos * fill(r); pos = 0; reason = "trail"; break
        if not fr and mins >= ts_min:
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

        if stage1 and not fr and mins_now >= stage1[0]:
            r1 = _price_at(stage1[0] * 60)
            if r1 < stage1[1]:
                proceeds += pos * r1; pos = 0; reason = "abort15"
        if pos > 0 and not fr and mins_now >= abort_min:
            ra = _price_at(abort_min * 60)
            if ra < abort_r:
                proceeds += pos * ra; pos = 0; reason = "abort"
        if pos > 0 and not fr and mins_now >= ts_min:
            proceeds += pos * _price_at(ts_min * 60); pos = 0; reason = "timestop"
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


EXITS = {
    "h108(frozen)": ((15, 1.08), 0.5, 1.5, 0.75),
    "s75best": ((15, 1.10), 0.6, 1.5, 0.75),
}
NETS = [25.0, 40.0, 60.0]
NBS = [10, 15, 20]
FLOWS = [2.0, 3.0]
HOURS = {"all": None, "usAM(12-15)": {12, 13, 14, 15},
         "waves(0-1,12-15)": {0, 1, 12, 13, 14, 15}}

rows = []
for ename, (s1, trl, tgt, sell) in EXITS.items():
    for net in NETS:
        for nb in NBS:
            for fl in FLOWS:
                for hname, hrs in HOURS.items():
                    posns = [simulate(xs, net, nb, fl, hrs,
                                      s1, 30, 1.15, trl, tgt, sell, 120)
                             for xs in tr.values()]
                    posns = [p for p in posns if p]
                    cn, cexp = committed(posns)
                    allr = [p["ret"] for p in posns if p["status"] == "closed"]
                    aexp = sum(allr) / len(allr) if allr else 0.0
                    rows.append({"exit": ename, "net": net, "nb": nb,
                                 "flow": fl, "hours": hname,
                                 "committed_n": cn,
                                 "committed_exp": round(cexp, 4),
                                 "all_n": len(allr),
                                 "all_exp": round(aexp, 4)})

rows.sort(key=lambda r: -r["committed_exp"])
print(f"{'exit':<13}{'net':<6}{'nb':<4}{'flow':<6}{'hours':<16}"
      f"{'com_n':<7}{'com_exp':<9}{'all_n':<7}{'all_exp':<8}")
for r in rows[:25]:
    print(f"{r['exit']:<13}{r['net']:<6}{r['nb']:<4}{r['flow']:<6}"
          f"{r['hours']:<16}{r['committed_n']:<7}"
          f"{r['committed_exp']:<+9}{r['all_n']:<7}{r['all_exp']:<+8}")
print("...")
pos = [r for r in rows if r["committed_exp"] > 0 and r["committed_n"] >= 10]
print(f"\nPOSITIVE cells with n>=10: {len(pos)}")
for r in pos[:10]:
    print("  ", r)
b = rows[0]
print(f"\nBEST: {b}")
gate = [r for r in rows if r["exit"] == "h108(frozen)" and r["net"] == 25.0
        and r["nb"] == 10 and r["flow"] == 2.0 and r["hours"] == "all"]
if gate:
    print(f"FROZEN GATE cell: {gate[0]['committed_n']} committed, "
          f"exp={gate[0]['committed_exp']:+.4f}, "
          f"rank={rows.index(gate[0]) + 1}/{len(rows)}")
