#!/usr/bin/env python3
"""shadow_ledger.py — §272: paper-trade every fast-path SKIPPED mint.

Answers, in real time: what is the bundle/rug gate saving (or costing)?
For each fast_entry_eval row in mfg_live_trades.jsonl with result
starting "skip", simulate the EXACT live fast_birth stack on the mint's
curve trajectory from curves.jsonl:

  entry  = first marketCapSol at/after the eval decision ts (react-to-
           signal fill, same honesty rule as paper_score §74b)
  exits  = live order (live_trader.py §940-990):
           freeroll >=1.5x (sell 75%) -> trail (freerolled, <=0.5x peak)
           -> panic <0.80 -> nm_abort (1.30 touch, 5 min < 1.5)
           -> fade (peak>=1.15, no nm touch, r<=0.9*peak)
           -> abort15 (>=15m, r<1.08) -> abort30 (>=30m, r<1.15)
           -> birth_cap (>=30m, any r) -> timestop (>=120m)
  clock exits fill at the last trade at/before the deadline (§99).
  §235 floor: exits worth <0.001 SOL are writeoffs (keep dust).

Output: shadow_ledger.jsonl (one row per mint, refreshed in place),
plus a printed summary. Idempotent — re-run any time.
"""
import json, time, collections
from pathlib import Path

MON = Path(__file__).resolve().parent
CURVES = MON / "curves.jsonl"
TRADESLOG = MON / "mfg_live_trades.jsonl"
MFG_TRADES = MON / "mfg_trades.jsonl"   # venue=curve prints (§272 feed)
OUT = MON / "shadow_ledger.jsonl"

SIZE = 0.05            # the SOL we would have staked
P_FR_TARGET, P_FR_SELL = 1.5, 0.75
P_TRAIL_F = 0.5
P_PANIC = 0.80
P_NM_TOUCH, P_NM_MIN = 1.30, 5
P_FADE_PEAK, P_FADE_K = 1.15, 0.90
P_ABORT15, P_ABORT30 = (15, 1.08), (30, 1.15)
P_BIRTH_CAP_MIN = 30.0
P_TIMESTOP_MIN = 120
MIN_PROCEEDS = 0.001   # §235


def load_skips():
    skips = {}
    for line in TRADESLOG.open():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("action") == "fast_entry_eval" and \
                str(r.get("result", "")).startswith("skip"):
            skips[r["mint"]] = {"eval_ts": r["ts"], "birth_t": r["t"],
                                "result": r["result"]}
    return skips


def load_curves(mints):
    """Price prints for skipped mints. Primary: mfg_trades.jsonl
    venue=curve rows (mcap_sol per trade, written by tracker for every
    armed/subscribed mint). Fallback: the create row in curves.jsonl
    gives the birth mcap so a print-less mint still gets an entry mark.
    Returns {mint: [(t, mcap_sol), ...]} sorted by t."""
    ev = collections.defaultdict(list)
    for line in MFG_TRADES.open():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("venue") != "curve":
            continue
        m = r.get("mint")
        if m in mints and r.get("mcap_sol") and r.get("t"):
            ev[m].append((r["t"], r["mcap_sol"]))
    for line in CURVES.open():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("txType") != "create":
            continue
        m = r.get("mint")
        if m in mints and r.get("marketCapSol") and r.get("_ts"):
            ev[m].append((r["_ts"], r["marketCapSol"]))
    for m in ev:
        ev[m] = sorted(set(ev[m]))
    return ev


def simulate(mint, eval_ts, birth_t, events):
    # entry: first print at/after decision time (react-to-signal fill);
    # if the mint went quiet after eval, use the last print before it.
    if len(events) < 2:
        # only the birth create row (or nothing) — no trajectory to
        # replay; pre-§272 skips predate the curve-print subscription.
        return {"mint": mint, "status": "no_data", "ret": None}
    ent = None
    prev = None
    for t, mc in events:
        if mc <= 0:
            continue
        if t >= eval_ts:
            ent = (t, mc)
            break
        prev = (t, mc)
    if ent is None:
        ent = prev
    if ent is None:
        return {"mint": mint, "status": "no_data", "ret": None}
    t0, emc = ent
    body = [(t, mc) for t, mc in events if t > t0 and mc > 0]
    proceeds, pos, peak = 0.0, 1.0, 1.0
    fr, reason, nm_touch_t = False, None, None

    def price_at(deadline_s):
        p = emc
        for t, mc in body:
            if t - t0 > deadline_s:
                break
            p = mc
        return p / emc

    def sellable(frac, r):
        # §235: below floor, write off instead of selling
        return frac * r * SIZE >= MIN_PROCEEDS

    for i, (t, mc) in enumerate(body):
        r = mc / emc
        peak = max(peak, r)
        mins = (t - t0) / 60
        if not fr and r >= P_NM_TOUCH and nm_touch_t is None:
            nm_touch_t = t
        fill = body[i + 1][1] / emc if i + 1 < len(body) else r
        if not fr and r >= P_FR_TARGET:
            proceeds += P_FR_SELL * (fill if sellable(P_FR_SELL, fill) else 0)
            pos -= P_FR_SELL
            fr = True
            continue
        if fr and r <= P_TRAIL_F * peak:
            proceeds += pos * (fill if sellable(pos, fill) else 0)
            pos, reason = 0, "trail"
            break
        if not fr and r < P_PANIC:
            proceeds += pos * (fill if sellable(pos, fill) else 0)
            pos, reason = 0, "panic"
            break
        if not fr and nm_touch_t and (t - nm_touch_t) >= P_NM_MIN * 60 \
                and r < P_FR_TARGET:
            r2 = price_at(nm_touch_t - t0 + P_NM_MIN * 60)
            proceeds += pos * (r2 if sellable(pos, r2) else 0)
            pos, reason = 0, "nm_abort"
            break
        if not fr and nm_touch_t is None and peak >= P_FADE_PEAK \
                and r <= P_FADE_K * peak:
            proceeds += pos * (fill if sellable(pos, fill) else 0)
            pos, reason = 0, "fade"
            break
        if not fr and mins >= P_ABORT15[0] and r < P_ABORT15[1]:
            r2 = price_at(P_ABORT15[0] * 60)
            proceeds += pos * (r2 if sellable(pos, r2) else 0)
            pos, reason = 0, "abort15"
            break
        if not fr and mins >= P_ABORT30[0] and r < P_ABORT30[1]:
            r2 = price_at(P_ABORT30[0] * 60)
            proceeds += pos * (r2 if sellable(pos, r2) else 0)
            pos, reason = 0, "abort30"
            break
        if not fr and mins >= P_BIRTH_CAP_MIN:
            r2 = price_at(P_BIRTH_CAP_MIN * 60)
            proceeds += pos * (r2 if sellable(pos, r2) else 0)
            pos, reason = 0, "birth_cap"
            break
        if not fr and mins >= P_TIMESTOP_MIN:
            r2 = price_at(P_TIMESTOP_MIN * 60)
            proceeds += pos * (r2 if sellable(pos, r2) else 0)
            pos, reason = 0, "timestop"
            break
    if pos > 0:
        # still riding: mark against clock deadlines then last print
        mins_now = (time.time() - t0) / 60
        for deadline, nm in ((P_ABORT15, "abort15"), (P_ABORT30, "abort30"),
                             (P_BIRTH_CAP_MIN, "birth_cap"),
                             (P_TIMESTOP_MIN, "timestop")):
            if not fr and mins_now >= deadline[0] if isinstance(deadline, tuple) else False:
                pass
        if not fr and mins_now >= P_ABORT15[0]:
            r1 = price_at(P_ABORT15[0] * 60)
            if r1 < P_ABORT15[1]:
                proceeds += pos * (r1 if sellable(pos, r1) else 0)
                pos, reason = 0, "abort15"
        if pos > 0 and not fr and mins_now >= P_ABORT30[0]:
            r2 = price_at(P_ABORT30[0] * 60)
            if r2 < P_ABORT30[1]:
                proceeds += pos * (r2 if sellable(pos, r2) else 0)
                pos, reason = 0, "abort30"
        if pos > 0 and not fr and mins_now >= P_BIRTH_CAP_MIN:
            r2 = price_at(P_BIRTH_CAP_MIN * 60)
            proceeds += pos * (r2 if sellable(pos, r2) else 0)
            pos, reason = 0, "birth_cap"
        if pos > 0 and not fr and mins_now >= P_TIMESTOP_MIN:
            r2 = price_at(P_TIMESTOP_MIN * 60)
            proceeds += pos * (r2 if sellable(pos, r2) else 0)
            pos, reason = 0, "timestop"
    if pos > 0:
        last_r = body[-1][1] / emc if body else 1.0
        return {"mint": mint, "status": "open", "eval_ts": eval_ts,
                "entry_t": t0, "entry_mcap": emc, "peak": round(peak, 3),
                "freerolled": fr, "mark": round(proceeds + pos * last_r - 1, 4),
                "ret": None}
    return {"mint": mint, "status": "closed", "eval_ts": eval_ts,
            "entry_t": t0, "entry_mcap": emc, "peak": round(peak, 3),
            "freerolled": fr, "exit_reason": reason,
            "ret": round(proceeds - 1, 4)}


def main():
    skips = load_skips()
    ev = load_curves(set(skips))
    rows = []
    for m, s in skips.items():
        rows.append(simulate(m, s["eval_ts"], s["birth_t"], ev.get(m, [])))
    with OUT.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    closed = [r for r in rows if r["status"] == "closed"]
    open_ = [r for r in rows if r["status"] == "open"]
    nodata = [r for r in rows if r["status"] == "no_data"]
    tot = sum(r["ret"] for r in closed)
    sol = tot * SIZE
    print(f"shadow ledger: {len(rows)} skipped mints | closed {len(closed)} "
          f"| open {len(open_)} | no_data {len(nodata)}")
    if closed:
        wins = sum(1 for r in closed if r["ret"] > 0)
        print(f"closed paper ret: total {tot:+.4f} per-unit = "
              f"{sol:+.4f} SOL at {SIZE} | avg {tot/len(closed):+.4f} "
              f"| win {wins}/{len(closed)}")
        by_reason = collections.Counter(r["exit_reason"] for r in closed)
        print("exit reasons:", dict(by_reason))
        worst = sorted(closed, key=lambda r: r["ret"])[:3]
        best = sorted(closed, key=lambda r: r["ret"])[-3:]
        print("worst:", [(r["mint"][:8], r["ret"]) for r in worst])
        print("best: ", [(r["mint"][:8], r["ret"]) for r in best])
        print(f"gate verdict: skipping SAVED us {-sol:+.4f} SOL"
              if sol < 0 else
              f"gate verdict: skipping COST us {sol:+.4f} SOL")


if __name__ == "__main__":
    main()
