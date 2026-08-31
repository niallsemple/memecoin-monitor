"""§75: shadow exit-variant grid on the VERIFIED engine (post-§74d parity).
Same conventions as gen_h108.py: next-trade entry, mark-to-deadline,
zero-mcap records kept. Frozen gate (h108 committed) is NOT moved by this;
output is informational — which exit rule, if any, is already expectancy-
positive on identical fills.

Axes: stage1 (fast rug-kill) x trail x freeroll target. Committed metric:
post-cutoff closed rets + 0.125 per freerolled open; plain opens excluded.
"""
import json, time, collections, pathlib

MON = pathlib.Path("/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor")
TRADES = MON / "mfg_trades.jsonl"
P_NET_MIN, P_NB_MIN, P_FLOW_MIN = 25.0, 10, 2.0
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


def simulate(xs, stage1, abort_min, abort_r, trail, target, sell, ts_min):
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
        if ((bs - ss) >= P_NET_MIN and nb >= P_NB_MIN
                and nb / max(ns, 1) >= P_FLOW_MIN):
            ti = i
            break
    if ti is None or ti + 1 >= len(xs):
        return None
    ei = ti + 1
    emc = xs[ei]["mcap_sol"]
    t0 = xs[ei]["t"]
    if emc <= 0:
        return None
    proceeds, pos, peak, fr, reason = 0.0, 1.0, 1.0, False, None
    body = xs[ei + 1:]
    closed = False
    for j, x in enumerate(body):
        r = x["mcap_sol"] / emc
        peak = max(peak, r)
        mins = (x["t"] - t0) / 60

        def fill(trig, _j=j):
            return (body[_j + 1]["mcap_sol"] / emc
                    if _j + 1 < len(body) else trig)

        if not fr and r >= target:
            proceeds += sell * fill(target)
            pos -= sell
            fr = True
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
    """Post-cutoff committed value: closed rets + floor per freerolled open."""
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


STAGE1S = [None, (15, 1.05), (15, 1.08), (15, 1.10), (20, 1.08)]
TRAILS = [0.4, 0.5, 0.6]
TARGETS = [(1.5, 0.75), (1.4, 0.75), (1.6, 0.6)]

rows = []
for s1 in STAGE1S:
    for trl in TRAILS:
        for tgt, sell in TARGETS:
            posns = [simulate(xs, s1, 30, 1.15, trl, tgt, sell, 120)
                     for xs in tr.values()]
            posns = [p for p in posns if p]
            cn, cexp = committed(posns)
            allr = [p["ret"] for p in posns if p["status"] == "closed"]
            aexp = sum(allr) / len(allr) if allr else 0.0
            rows.append({"stage1": s1, "trail": trl, "target": tgt,
                         "sell": sell, "committed_n": cn,
                         "committed_exp": round(cexp, 4),
                         "all_closed_n": len(allr),
                         "all_exp": round(aexp, 4)})

rows.sort(key=lambda r: -r["committed_exp"])
print(f"{'stage1':<12}{'trail':<7}{'target':<8}{'sell':<6}"
      f"{'com_n':<7}{'com_exp':<9}{'all_n':<7}{'all_exp':<8}")
for r in rows:
    print(f"{str(r['stage1']):<12}{r['trail']:<7}{r['target']:<8}"
          f"{r['sell']:<6}{r['committed_n']:<7}{r['committed_exp']:<+9}"
          f"{r['all_closed_n']:<7}{r['all_exp']:<+8}")
best = rows[0]
print(f"\nBEST committed: stage1={best['stage1']} trail={best['trail']} "
      f"target={best['target']} sell={best['sell']} -> "
      f"{best['committed_n']} committed, exp={best['committed_exp']:+.4f}")
gate = [r for r in rows if r["stage1"] == (15, 1.08) and r["trail"] == 0.5
        and r["target"] == 1.5 and r["sell"] == 0.75]
if gate:
    g = gate[0]
    print(f"FROZEN GATE (h108): {g['committed_n']} committed, "
          f"exp={g['committed_exp']:+.4f}  rank="
          f"{rows.index(g) + 1}/{len(rows)}")
