#!/usr/bin/env python3
"""§79p: delayed/confirmed entry test for the s60 gate.

Kill criterion #2 fired (E6gQ, B9tN — both grind-then-harvest rugs that
collapsed minutes-to-an-hour after passing the breadth gate). Fix candidate:
at signal time S (mcap M0), wait D minutes; enter at next trade only if
price >= CONFIRM x M0 (token still alive at/above signal level); else skip.

Grid: D in {0, 5, 10, 15} min x CONFIRM in {1.0}. Exits: frozen h108 stack.
Post-cutoff tape only. Committed accounting: freerolled opens at +12.5% floor.
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


def simulate_delayed(xs, delay_s, confirm=1.0, net_min=60.0, nb_min=20, flow_min=2.0):
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
        if (bs - ss) >= net_min and nb >= nb_min and nb / max(ns, 1) >= flow_min:
            ti = i
            break
    if ti is None or ti + 1 >= len(xs):
        return None
    sig_t = xs[ti]["t"]
    sig_mc = xs[ti]["mcap_sol"]
    if sig_mc <= 0:
        return None
    # delayed confirmation: first trade at/after sig_t + delay_s
    ei = None
    for j in range(ti + 1, len(xs)):
        if xs[j]["t"] - sig_t >= delay_s:
            ei = j
            break
    if ei is None:
        return None
    if xs[ei]["mcap_sol"] < confirm * sig_mc:
        return "SKIP"  # failed confirmation — token weakened/died during delay
    emc = xs[ei]["mcap_sol"]
    t0 = xs[ei]["t"]
    if emc <= 0:
        return None
    proceeds, pos, peak, fr, reason = 0.0, 1.0, 1.0, False, None
    body = xs[ei + 1:]
    for j, x in enumerate(body):
        r = x["mcap_sol"] / emc
        peak = max(peak, r)
        mins = (x["t"] - t0) / 60
        fill = (body[j + 1]["mcap_sol"] / emc) if j + 1 < len(body) else r
        if not fr and r >= 1.5:
            proceeds += 0.75 * fill; pos -= 0.75; fr = True
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


for delay_min in (0, 5, 10, 15):
    rows, skips = [], 0
    for mint, xs in tr.items():
        r = simulate_delayed(xs, delay_min * 60)
        if r == "SKIP":
            skips += 1
            continue
        if r and r["entry_t"] >= CUTOFF:
            rows.append(r)
    c = [FLOOR if (r["status"] == "open" and r["freerolled"]) else r["ret"]
         for r in rows if r["status"] == "closed" or (r["status"] == "open" and r["freerolled"])]
    if not c:
        print(f"D={delay_min:2d}m: no committed")
        continue
    losses = [v for v in c if v < 0]
    bleeders = [v for v in c if v <= -0.5]
    print(f"D={delay_min:2d}m: n={len(c):3d} skips={skips} exp={100*statistics.mean(c):+6.2f}% "
          f"losses={len(losses)} bleeders={len(bleeders)}")
    if delay_min in (0, 10):
        for r in sorted(rows, key=lambda z: z["entry_t"]):
            tag = " <-- BLEEDER" if r["status"] == "closed" and r["ret"] <= -0.5 else ""
            print(f"    {r['mint']} {r['status']:6s} {str(r['exit_reason']):9s} "
                  f"{100*r['ret']:+7.1f}% peak={r['peak']:.2f}x{tag}")
