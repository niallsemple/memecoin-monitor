#!/usr/bin/env python3
"""drain_sim.py — §209: replay the live book against proposed blocking
gates before real money depends on them at 2x.

For every closed live position, recomputes crew_wallets(<=120s post-
entry) from mfg_wallet_trades.jsonl + drainer_blocklist.json (the §204
method), then replays the book under candidate gate configs:

  G0  no gate (status quo)
  G1  crew >= 30                       (catches 29H7, JwQb)
  G2  crew >= 30  OR  overhang >= X%   (X swept; adds LUTN coverage)

LUTN's entry-time overhang is unobservable post-drain (screen is
forward-only), so G2 models it as FLAGGED (its killer held pre-pool
tokens — §189) and separately reports the miss case.

Each config is replayed at 1x and 2x stake. A skipped entry avoids both
the loss AND the fees (~0.0019 SOL/trade); a sacrificed green entry
loses its realized pnl. Output: net SOL, worst trade, drains taken.

Usage: python3 drain_sim.py
"""
import json
from collections import defaultdict

EARLY_WINDOW_S = 120
CREW_THRESHOLD = 30
OVERHANG_SWEEP = (20, 30, 40, 50)
FEE_PER_TRADE = 0.00188
# mints whose entry-time overhang we cannot observe but which §189 says
# the overhang screen would have flagged (killer held pre-pool tokens):
OVERHANG_WOULD_FLAG = {"LUTNZsftGW64Zch1mqWp6hoGSHLkHQQ7rsuFy3ppump"}


def load_book():
    pos = json.load(open("live_positions.json"))
    closed = [(m, p) for m, p in pos.items() if not p.get("open")]
    closed.sort(key=lambda kv: kv[1].get("entry_t", 0))
    return closed


def blocklist_set():
    bl = json.load(open("drainer_blocklist.json"))
    w = set()
    for sec in ("masters", "killers", "feeders", "funded_next_gen"):
        w |= set(bl.get(sec, {}).keys())
    return w


def crew_counts(closed, bl):
    """Distinct blocklist wallets trading each mint within 120s of our
    entry, plus total blocklist wallets seen on the mint at any time."""
    early = defaultdict(set)
    total = defaultdict(set)
    windows = {m: (p["entry_t"], p["entry_t"] + EARLY_WINDOW_S)
               for m, p in closed}
    mints = set(windows)
    for l in open("mfg_wallet_trades.jsonl"):
        r = json.loads(l)
        m = r.get("mint")
        if m not in mints:
            continue
        w = r.get("wallet")
        if w not in bl:
            continue
        total[m].add(w)
        a, b = windows[m]
        if a <= r.get("t", 0) <= b:
            early[m].add(w)
    return {m: (len(early[m]), len(total[m])) for m in mints}


def replay(closed, crew, crew_gate=True, overhang_x=None, scale=1.0,
           lutn_flagged=True):
    net = taken = skipped_drain = sacrificed = 0
    net_sol = 0.0
    worst = 0.0
    drains_taken = 0
    for m, p in closed:
        e_n, _t_n = crew.get(m, (0, 0))
        skip = crew_gate and e_n >= CREW_THRESHOLD
        if not skip and overhang_x is not None \
                and m in OVERHANG_WOULD_FLAG and lutn_flagged:
            skip = True                 # overhang screen would fire
        if skip:
            if p["pnl_sol"] < 0:
                skipped_drain += 1
            else:
                sacrificed += 1
            continue
        pnl = p["pnl_sol"] * scale
        # at scale>1 the skipped-fee benefit is unchanged; taken trades
        # pay the same fixed fees (already netted at 1x; add drag)
        pnl -= FEE_PER_TRADE * (scale - 1) * 0.5
        net_sol += pnl
        worst = min(worst, pnl)
        taken += 1
        if p["pnl_sol"] < -0.05:
            drains_taken += 1
    return dict(taken=taken, net=net_sol, worst=worst,
                drains_taken=drains_taken, skipped_drain=skipped_drain,
                sacrificed=sacrificed)


def main():
    closed = load_book()
    bl = blocklist_set()
    crew = crew_counts(closed, bl)
    print("=" * 70)
    print(f"DRAIN SIM — {len(closed)} closes, blocklist {len(bl)} wallets, "
          f"early window {EARLY_WINDOW_S}s, crew gate >= {CREW_THRESHOLD}")
    print("=" * 70)
    print("\nPer-mint crew counts (blocklist wallets <=120s post-entry / total):")
    for m, p in closed:
        e, t = crew.get(m, (0, 0))
        if e or t or p["pnl_sol"] < 0:
            print(f"  {m[:10]:12s} early={e:3d} total={t:3d} "
                  f"pnl={p['pnl_sol']:+.5f} {p.get('closed_reason','')}")
    print(f"\n{'config':34s} {'scale':>5} {'taken':>5} {'net SOL':>10} "
          f"{'worst':>9} {'drains':>6} {'skip_d':>6} {'sac':>4}")
    for scale in (1.0, 2.0):
        configs = [("G0 no gate", dict(crew_gate=False)),
                   ("G1 crew>=30 only", dict(crew_gate=True)),
                   ("G2 crew>=30 OR overhang flags LUTN",
                    dict(crew_gate=True, overhang_x=30)),
                   ("G2 but LUTN overhang MISSES",
                    dict(crew_gate=True, overhang_x=30,
                         lutn_flagged=False))]
        for name, kw in configs:
            r = replay(closed, crew, scale=scale, **kw)
            print(f"{name:34s} {scale:>4}x {r['taken']:>5} "
                  f"{r['net']:+10.5f} {r['worst']:+9.5f} "
                  f"{r['drains_taken']:>6} {r['skipped_drain']:>6} "
                  f"{r['sacrificed']:>4}")
    print("=" * 70)


if __name__ == "__main__":
    main()
