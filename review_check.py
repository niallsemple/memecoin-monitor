"""§79: Sep 1 review instrument — recompute all scorers from RAW TAPE and
diff against the tracker-written files. Per §78h, stored marks can revise
under RPC backfill; the review must trust the tape, not the files.

Usage: python3 review_check.py
Outputs per-scorer: recomputed committed n/exp, diff vs tracker file,
revision list, and the amendment criteria scoreboard.
"""
import json, time, collections, pathlib

MON = pathlib.Path("/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor")
CUTOFF = 1788060000
FLOOR = 0.125

tr = collections.defaultdict(list)
with (MON / "mfg_trades.jsonl").open() as f:
    for line in f:
        try:
            x = json.loads(line)
        except Exception:
            continue
        if (x.get("venue") != "pool" or not x.get("t")
                or x.get("mcap_sol") is None):
            continue
        tr[x["mint"]].append(x)


def simulate(xs, net_min, nb_min, flow_min, stage1, abort_min):
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
    proceeds, pos, peak, fr, reason = 0.0, 1.0, 1.0, False, None
    body = xs[ei + 1:]
    for j, x in enumerate(body):
        r = x["mcap_sol"] / emc
        peak = max(peak, r)
        mins = (x["t"] - t0) / 60

        def fill(trig, _j=j):
            return (body[_j + 1]["mcap_sol"] / emc
                    if _j + 1 < len(body) else trig)

        if not fr and r >= 1.5:
            proceeds += 0.75 * fill(1.5); pos -= 0.75; fr = True
        if (stage1 and not fr and mins >= stage1[0]
                and r < stage1[1] and pos > 0):
            proceeds += pos * fill(r); pos = 0; reason = "abort15"; break
        if not fr and mins >= abort_min and r < 1.15 and pos > 0:
            proceeds += pos * fill(r); pos = 0; reason = "abort"; break
        if r <= 0.5 * peak and pos > 0:
            proceeds += pos * fill(r); pos = 0; reason = "trail"; break
        if not fr and mins >= 120:
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
            if ra < 1.15:
                proceeds += pos * ra; pos = 0; reason = "abort"
        if pos > 0 and not fr and mins_now >= 120:
            proceeds += pos * _price_at(120 * 60); pos = 0
            reason = "timestop"
    if pos > 0:
        total = proceeds + pos * (xs[-1]["mcap_sol"] / emc)
        status = "open"
    else:
        total = proceeds
        status = "closed"
    return {"mint": xs[0]["mint"], "entry_t": t0, "ret": round(total - 1, 4),
            "status": status, "freerolled": fr, "exit_reason": reason,
            "peak": round(peak, 3)}


SCORERS = {
    "mfg_paper_trades.jsonl": (25.0, 10, 2.0, None, 30),
    "mfg_paper_trades_a15.jsonl": (25.0, 10, 2.0, None, 15),
    "mfg_paper_trades_h108.jsonl": (25.0, 10, 2.0, (15, 1.08), 30),
    "mfg_paper_trades_s60.jsonl": (60.0, 20, 2.0, (15, 1.08), 30),
}

print(f"{'scorer':<32}{'rec_n':<7}{'rec_exp':<9}{'file_n':<8}{'file_exp':<9}{'revisions'}")
for fname, (net, nbk, fl, s1, am) in SCORERS.items():
    recomputed = {}
    for m, xs in tr.items():
        r = simulate(xs, net, nbk, fl, s1, am)
        if r:
            recomputed[m] = r
    # committed metric on recomputed
    vals = []
    for r in recomputed.values():
        if r["entry_t"] <= CUTOFF:
            continue
        if r["status"] == "closed":
            vals.append(r["ret"])
        elif r["freerolled"]:
            vals.append(FLOOR)
    rec_n = len(vals)
    rec_exp = sum(vals) / len(vals) if vals else 0.0
    # tracker file
    fvals = []
    frows = {}
    try:
        for line in (MON / fname).open():
            row = json.loads(line)
            frows[row["mint"]] = row
        for row in frows.values():
            if row["entry_t"] <= CUTOFF:
                continue
            if row["status"] == "closed":
                fvals.append(row["ret"])
            elif row.get("freerolled"):
                fvals.append(FLOOR)
    except FileNotFoundError:
        pass
    file_n = len(fvals)
    file_exp = sum(fvals) / len(fvals) if fvals else 0.0
    # revisions: same mint, different status/ret
    revs = []
    for m, rr in recomputed.items():
        fr_ = frows.get(m)
        if fr_ and rr["entry_t"] > CUTOFF:
            if fr_["status"] != rr["status"] or abs(fr_["ret"] - rr["ret"]) > 0.005:
                revs.append(f'{m[:8]}({fr_["status"][:3]}->{rr["status"][:3]})')
    print(f"{fname:<32}{rec_n:<7}{rec_exp:<+9.4f}{file_n:<8}"
          f"{file_exp:<+9.4f}{len(revs)} {','.join(revs[:5])}")

print("\nAmendment criteria (recomputed from tape):")
s60 = {m: r for m, r in recomputed.items()}  # last loop is s60
post = [r for r in s60.values() if r["entry_t"] > CUTOFF]
postdep = [r for r in post if r["entry_t"] > 1788158000]  # ~shadow deploy
runners = [r for r in post if r["peak"] >= 1.5]
print(f"1. s60 committed: n={rec_n}, exp={rec_exp:+.4f} "
      f"({'MET' if rec_n >= 20 and rec_exp > 0 else 'not met'})")
print(f"2. post-cutoff runners >=1.5x in s60: {len(runners)} "
      f"({', '.join(r['mint'][:8] for r in runners)})")
print(f"   post-deployment entries: {len(postdep)}, "
      f"losses: {sum(1 for r in post if r['status'] == 'closed' and r['ret'] <= 0)}")
