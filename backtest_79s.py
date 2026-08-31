#!/usr/bin/env python3
"""§79s: near-miss abort test.

Peak distribution is bimodal with an empty middle (§79r analysis):
22 trades peak <1.08, ZERO in 1.15-1.29, exactly TWO in 1.30-1.49
(E6gQ 1.386 -> -100%, PFKs 1.387 -> -31.4%), six >=1.5 (all survived).
Hypothesis: approaching but NOT crossing 1.5 is a dump-in-progress
signature. Rule: once r>=1.30 is touched, start a clock; if 1.5 is not
reached within NM_MIN minutes, exit at the next trade (market).

Grid: NM_MIN in {3, 5, 10}. Compare vs baseline h108 stack.
Post-cutoff tape, s60 entry gate, committed accounting.
"""
import json, collections, time, statistics

CUTOFF = 1788060000
FLOOR = 0.125

tr = collections.defaultdict(list)
for line in open("mfg_trades.jsonl"):
    try:
        x = json.loads(line)
    except Exception:
        continue
    if x.get("venue") != "pool" or not x.get("t") or x.get("mcap_sol") is None:
        continue
    tr[x["mint"]].append(x)


def simulate(xs, nm_min=None):
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
        if (bs - ss) >= 60.0 and nb >= 20 and nb / max(ns, 1) >= 2.0:
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
    nm_touch_t = None
    body = xs[ei + 1:]
    for j, x in enumerate(body):
        r = x["mcap_sol"] / emc
        peak = max(peak, r)
        mins = (x["t"] - t0) / 60
        fill = (body[j + 1]["mcap_sol"] / emc) if j + 1 < len(body) else r
        if not fr and r >= 1.5:
            proceeds += 0.75 * fill; pos -= 0.75; fr = True
        if nm_min and not fr:
            if r >= 1.30 and nm_touch_t is None:
                nm_touch_t = x["t"]
            if (nm_touch_t is not None and r < 1.5
                    and (x["t"] - nm_touch_t) >= nm_min * 60 and pos > 0):
                proceeds += pos * fill; pos = 0; reason = "nm_abort"; break
        if not fr and mins >= 15 and r < 1.08 and pos > 0:
            proceeds += pos * fill; pos = 0; reason = "abort15"; break
        if not fr and mins >= 30 and r < 1.15 and pos > 0:
            proceeds += pos * fill; pos = 0; reason = "abort"; break
        if r <= 0.5 * peak and pos > 0:
            proceeds += pos * fill; pos = 0; reason = "trail"; break
        if not fr and mins >= 120:
            proceeds += pos * fill; pos = 0; reason = "timestop"; break
    if pos > 0:
        mins_now = (time.time() - t0) / 60
        def _price_at(d):
            p = emc
            for x in xs[ei + 1:]:
                if x["t"] - t0 > d:
                    break
                p = x["mcap_sol"]
            return p / emc
        if not fr and mins_now >= 15:
            r1 = _price_at(900)
            if r1 < 1.08:
                proceeds += pos * r1; pos = 0; reason = "abort15"
        if pos > 0 and not fr and mins_now >= 30:
            ra = _price_at(1800)
            if ra < 1.15:
                proceeds += pos * ra; pos = 0; reason = "abort"
        if pos > 0 and not fr and mins_now >= 120:
            proceeds += pos * _price_at(7200); pos = 0; reason = "timestop"
    if pos > 0:
        total = proceeds + pos * (xs[-1]["mcap_sol"] / emc)
        status = "open"
    else:
        total = proceeds
        status = "closed"
    return {"mint": xs[0]["mint"][:8], "entry_t": t0, "ret": round(total - 1, 4),
            "status": status, "freerolled": fr, "exit_reason": reason,
            "peak": round(peak, 3)}


for nm in (None, 3, 5, 10):
    rows = []
    for mint, xs in tr.items():
        r = simulate(xs, nm)
        if r and r["entry_t"] >= CUTOFF:
            rows.append(r)
    c = [FLOOR if (r["status"] == "open" and r["freerolled"]) else r["ret"]
         for r in rows if r["status"] == "closed" or (r["status"] == "open" and r["freerolled"])]
    losses = [v for v in c if v < 0]
    bleeders = [v for v in c if v <= -0.5]
    nm_exits = [r for r in rows if r["exit_reason"] == "nm_abort"]
    print(f"nm={str(nm):4s}: n={len(c):3d} exp={100*statistics.mean(c):+6.2f}% "
          f"losses={len(losses)} bleeders={len(bleeders)} nm_exits={len(nm_exits)}")
    for r in nm_exits:
        print(f"    nm_abort: {r['mint']} ret={100*r['ret']:+.1f}% peak={r['peak']:.2f}x")
