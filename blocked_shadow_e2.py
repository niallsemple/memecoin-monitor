#!/usr/bin/env python3
"""§449: replay bridge-BLOCKED candidates through the exact live e2 exit stack.

Entry = first tape print at/after the bridge decision ts (react-to-signal).
Rules in live order (live_trader.py exit_watch, §1242-1285):
  abort3_red (first check >=3min, r<1) -> bank12x (r>=1.2, sell ALL)
  -> freeroll (r>=1.5, sell 75%) -> trail (freerolled, r<=0.5*peak)
  -> panic (r<0.80) -> nm_abort (1.30 touch +5min, r<1.5)
  -> fade (peak>=1.15, no nm touch, r<=0.9*peak)
  -> abort15 (>=15m, r<1.08) -> abort30 (>=30m, r<1.15) -> timestop 120m
  (birth_cap skipped: e2_trial entries are not fast_birth kind)
Fill honesty: exits fill at the NEXT print's r (shadow_ledger §99 rule).
§235 writeoff floor: est proceeds <0.001 SOL -> write off at -stake.
"""
import json
import time
import collections
from pathlib import Path

MON = Path(__file__).resolve().parent
SIZE = 0.02
SLIP = 0.02
SLIP_F = (1 - SLIP) / (1 + SLIP)
MIN_PROCEEDS = 0.001

P_BANK12 = 1.2
P_FR_TARGET, P_FR_SELL = 1.5, 0.75
P_TRAIL_F = 0.5
P_PANIC = 0.80
P_NM_TOUCH, P_NM_MIN = 1.30, 5
P_FADE_PEAK, P_FADE_K = 1.15, 0.90
P_ABORT15, P_ABORT30 = (15, 1.08), (30, 1.15)
P_TIMESTOP_MIN = 120


def load_blocked():
    blocked = {}
    for l in (MON / "e2_bridge.jsonl").open():
        try:
            r = json.loads(l)
        except Exception:
            continue
        if r.get("action") == "bridge_blocked":
            blocked[r["mint"]] = r
    return blocked


def load_tape(mints):
    """Chained-multiple series per mint (shadow_ledger.load_curves logic,
    but with substring prefilter for the 669MB tape)."""
    raw = collections.defaultdict(list)
    pats = [m.encode() for m in mints]
    with (MON / "mfg_trades.jsonl").open("rb") as f:
        for line in f:
            hit = None
            for m, p in zip(mints, pats):
                if p in line:
                    hit = m
                    break
            if not hit:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            v, mc = r.get("venue"), r.get("mcap_sol")
            if v in ("curve", "pool") and mc and mc > 0 and r.get("t"):
                raw[hit].append((r["t"], "c" if v == "curve" else "p", mc))
    for line in (MON / "curves.jsonl").open():
        hit = None
        for m in mints:
            if m in line:
                hit = m
                break
        if not hit:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("txType") == "create" and r.get("marketCapSol") and r.get("_ts"):
            raw[hit].append((r["_ts"], "c", r["marketCapSol"]))
    ev = {}
    for m, xs in raw.items():
        xs.sort()
        mult, pv, pmc = 1.0, None, None
        series = []
        for t, v, mc in xs:
            if v == pv and pmc:
                mult *= mc / pmc
            pv, pmc = v, mc
            series.append((t, mult))
        ev[m] = series
    return ev


def simulate_e2(mint, eval_ts, events):
    if len(events) < 2:
        return {"mint": mint, "status": "no_data", "ret": None}
    ent, prev = None, None
    for t, mult in events:
        if t >= eval_ts:
            ent = (t, mult)
            break
        prev = (t, mult)
    if ent is None:
        ent = prev
    if ent is None or ent[1] <= 0:
        return {"mint": mint, "status": "no_data", "ret": None}
    t0, emult = ent
    body = [(t, mult / emult) for t, mult in events if t > t0]
    proceeds, pos, peak = 0.0, 1.0, 1.0
    fr, reason, nm_touch_t, a3r_done = False, None, None, False

    def price_at(deadline_s):
        r = 1.0
        for t, rr in body:
            if t - t0 > deadline_s:
                break
            r = rr
        return r

    def sellable(frac, r):
        return frac * r * SIZE >= MIN_PROCEEDS

    def writeoff(act, t):
        return {"mint": mint, "status": "closed", "eval_ts": eval_ts,
                "entry_t": t0, "exit_t": t, "peak": round(peak, 3),
                "freerolled": fr, "exit_reason": act + "_writeoff",
                "ret": -1.0}

    for i, (t, r) in enumerate(body):
        peak = max(peak, r)
        mins = (t - t0) / 60
        if not fr and r >= P_NM_TOUCH and nm_touch_t is None:
            nm_touch_t = t
        fill = body[i + 1][1] if i + 1 < len(body) else r
        # abort3_red: one-shot clock check
        if not fr and not a3r_done and mins >= 3.0:
            a3r_done = True
            if r < 1.0:
                if not sellable(pos, fill):
                    return writeoff("abort3_red", t)
                proceeds += pos * fill
                pos, reason = 0, "abort3_red"
                break
        if not fr and r >= P_BANK12:
            if not sellable(pos, fill):
                return writeoff("bank12x", t)
            proceeds += pos * fill
            pos, reason = 0, "bank12x"
            break
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
            if not sellable(pos, fill):
                return writeoff("panic", t)
            proceeds += pos * fill
            pos, reason = 0, "panic"
            break
        if not fr and nm_touch_t and (t - nm_touch_t) >= P_NM_MIN * 60 \
                and r < P_FR_TARGET:
            r2 = price_at(nm_touch_t - t0 + P_NM_MIN * 60)
            if not sellable(pos, r2):
                return writeoff("nm_abort", t)
            proceeds += pos * r2
            pos, reason = 0, "nm_abort"
            break
        if not fr and nm_touch_t is None and peak >= P_FADE_PEAK \
                and r <= P_FADE_K * peak:
            if not sellable(pos, fill):
                return writeoff("fade", t)
            proceeds += pos * fill
            pos, reason = 0, "fade"
            break
        if not fr and mins >= P_ABORT15[0] and r < P_ABORT15[1]:
            r2 = price_at(P_ABORT15[0] * 60)
            if not sellable(pos, r2):
                return writeoff("abort15", t)
            proceeds += pos * r2
            pos, reason = 0, "abort15"
            break
        if not fr and mins >= P_ABORT30[0] and r < P_ABORT30[1]:
            r2 = price_at(P_ABORT30[0] * 60)
            if not sellable(pos, r2):
                return writeoff("abort30", t)
            proceeds += pos * r2
            pos, reason = 0, "abort30"
            break
        if not fr and mins >= P_TIMESTOP_MIN:
            r2 = price_at(P_TIMESTOP_MIN * 60)
            if not sellable(pos, r2):
                return writeoff("timestop", t)
            proceeds += pos * r2
            pos, reason = 0, "timestop"
            break
    if pos > 0:
        # force clock exits against the tape end (all these mints are old)
        for label, dl_min, cap in (("abort15", P_ABORT15[0], P_ABORT15[1]),
                                   ("abort30", P_ABORT30[0], P_ABORT30[1])):
            if pos > 0 and not fr:
                r2 = price_at(dl_min * 60)
                if r2 < cap:
                    if not sellable(pos, r2):
                        return writeoff(label, t0 + dl_min * 60)
                    proceeds += pos * r2
                    pos, reason = 0, label
        if pos > 0 and not fr:
            r2 = price_at(P_TIMESTOP_MIN * 60)
            if not sellable(pos, r2):
                return writeoff("timestop", t0 + P_TIMESTOP_MIN * 60)
            proceeds += pos * r2
            pos, reason = 0, "timestop"
    if pos > 0:  # freerolled remnant still riding at tape end
        last_r = body[-1][1] if body else 1.0
        proceeds += pos * (last_r if sellable(pos, last_r) else 0)
        reason = reason or "tape_end"
    return {"mint": mint, "status": "closed", "eval_ts": eval_ts,
            "entry_t": t0, "peak": round(peak, 3), "freerolled": fr,
            "exit_reason": reason,
            "ret": round(proceeds * SLIP_F - 1, 4)}


def main():
    blocked = load_blocked()
    out_f = MON / "blocked_shadow_e2.jsonl"
    prior = {}
    if out_f.exists():
        for l in out_f.open():
            try:
                r = json.loads(l)
            except Exception:
                continue
            if r.get("status") == "closed":
                prior[r["mint"]] = r
    todo = [m for m in blocked if m not in prior]
    print(f"blocked total={len(blocked)} already replayed={len(prior)} new={len(todo)}")
    rows_new = []
    if todo:
        ev = load_tape(todo)
        for m in todo:
            r = simulate_e2(m, blocked[m]["t"], ev.get(m, []))
            r["block_reason"] = blocked[m].get("reason")
            r["seed"] = blocked[m].get("seed")
            rows_new.append(r)
    rows = list(prior.values()) + rows_new
    tot_sol = 0.0
    n_closed = 0
    for r in rows:
        if r["status"] == "closed":
            tot_sol += r["ret"] * SIZE
            n_closed += 1
    for r in rows_new:
        if r["status"] == "closed":
            sol = r["ret"] * SIZE
            print(f"  NEW {r['mint'][:8]} {r['block_reason']:>14} seed={round(r['seed'] or 0,2):>5} "
                  f"peak={r['peak']:>6} exit={r['exit_reason']:>12} ret={r['ret']:+.4f} pnl={sol:+.5f}")
        else:
            print(f"  NEW {r['mint'][:8]} {r['block_reason']:>14} NO TAPE")
    print(f"\ne2-stack shadow PnL on blocked (n={n_closed}): {tot_sol:+.5f} SOL "
          f"({'gates EARN' if tot_sol < 0 else 'gates COST'} {abs(tot_sol):.5f})")
    with out_f.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    main()
