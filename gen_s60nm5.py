"""One-shot: generate mfg_paper_trades_s60nm5.jsonl with the exact patched
paper_score logic (s60 entry, h108 exits, nm_min=5 near-miss abort) so the
amended gate has a file before the next tracker cycle overwrites it.
Mirrors automation.py paper_score verbatim, including mark-to-deadline."""
import json, time, collections, pathlib

MON = pathlib.Path("/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor")
TRADES = MON / "mfg_trades.jsonl"
OUT = MON / "mfg_paper_trades_s60nm5.jsonl"
P_TARGET, P_SELL = 1.5, 0.75
P_TRAIL = 0.5
P_TS_MIN = 120
P_ABORT_MIN, P_ABORT_R = 30, 1.15
STAGE1 = (15, 1.08)
NET_MIN, NB_MIN, FLOW_MIN = 60.0, 20, 2.0
NM_MIN = 5

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
        if ((bs - ss) >= NET_MIN and nb >= NB_MIN
                and nb / max(ns, 1) >= FLOW_MIN):
            ti = i
            break
    if ti is None or ti + 1 >= len(xs):
        continue
    emc = xs[ti + 1]["mcap_sol"]
    t0 = xs[ti + 1]["t"]
    if emc <= 0:
        continue
    proceeds, pos, peak, fr, reason = 0.0, 1.0, 1.0, False, None
    nm_touch_t = None
    body = xs[ti + 2:]
    for j, x in enumerate(body):
        r = x["mcap_sol"] / emc
        peak = max(peak, r)
        mins = (x["t"] - t0) / 60
        fill = (body[j + 1]["mcap_sol"] / emc if j + 1 < len(body) else r)
        if not fr and r >= P_TARGET:
            proceeds += P_SELL * fill; pos -= P_SELL; fr = True
        if NM_MIN and not fr:
            if r >= 1.30 and nm_touch_t is None:
                nm_touch_t = x["t"]
            if (nm_touch_t is not None and r < P_TARGET
                    and (x["t"] - nm_touch_t) >= NM_MIN * 60 and pos > 0):
                proceeds += pos * fill; pos = 0; reason = "nm_abort"; break
        if (not fr and mins >= STAGE1[0] and r < STAGE1[1] and pos > 0):
            proceeds += pos * fill; pos = 0; reason = "abort15"; break
        if not fr and mins >= P_ABORT_MIN and r < P_ABORT_R and pos > 0:
            proceeds += pos * fill; pos = 0; reason = "abort"; break
        if r <= P_TRAIL * peak and pos > 0:
            proceeds += pos * fill; pos = 0; reason = "trail"; break
        if not fr and mins >= P_TS_MIN:
            proceeds += pos * fill; pos = 0; reason = "timestop"; break
    if pos > 0:
        mins_now = (time.time() - t0) / 60
        def _price_at(deadline_s):
            p = emc
            for x in xs[ti + 2:]:
                if x["t"] - t0 > deadline_s:
                    break
                p = x["mcap_sol"]
            return p / emc
        if not fr and mins_now >= STAGE1[0]:
            r1 = _price_at(STAGE1[0] * 60)
            if r1 < STAGE1[1]:
                proceeds += pos * r1; pos = 0; reason = "abort15"
        if pos > 0 and not fr and mins_now >= P_ABORT_MIN:
            ra = _price_at(P_ABORT_MIN * 60)
            if ra < P_ABORT_R:
                proceeds += pos * ra; pos = 0; reason = "abort"
        if pos > 0 and not fr and mins_now >= P_TS_MIN:
            proceeds += pos * _price_at(P_TS_MIN * 60); pos = 0
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
print(f"wrote {len(positions)} rows -> {OUT.name}")
