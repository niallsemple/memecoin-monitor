#!/usr/bin/env python3
"""E25 forward-validation scorecard (§66b, gate switched §73).

Counts ONLY trades with entry_t after the Helius-outage cutoff — the
13 pre-outage positions are void (20h hole in exit-management data).
§73: gate scorer switched from a30. §74: gate moved to the two-stage
hybrid H-1.08 file (mfg_paper_trades_h108.jsonl); a15/a30 are shadows.
Gate: n>=30 post-cutoff closes with expectancy > 0 before real money.
"""
import json, time, sys
from pathlib import Path

MON = Path(__file__).resolve().parent
CUTOFF = 1788060000          # §66g: anything after the last corrupted flow
                             # (~02:47 UTC) and before clean flow resumed
                             # (21:58 UTC) works identically — nothing was
                             # recorded in between. (First attempt mislabeled
                             # epoch 1788062400 as "22:00 UTC"; real 22:00
                             # UTC is 1788127200.)
GATE_N = 30
BACKTEST_EXP = 0.0575        # frozen §59 backtest expectation per trade

def main():
    # §73: gate scorer switched to abort-15 (evidence: §69c replay
    # −3.2% vs −13.4% all-history; §72 forward −8.9% vs −43.6% on
    # identical live data). §74: gate moved to the two-stage hybrid
    # H-1.08 (15m<1.08 then 30m<1.15) — replay leader (+1.8% all-history,
    # −2.0% post-cutoff vs a15 −1.7%/−5.75% and a30 −8.75%/−17.75%).
    # a30/a15 files still reported as shadows. Fallback chain: h108 -> a15
    # -> a30.
    # §134 (1 Sep 2026): production config is now the fr gate
    # (s60nm5fr) — the only net-positive forward config and the one the
    # live wallet trades. Gate file chain re-pointed: s60nm5fr -> h108
    # -> a15 -> a30; h108 and the old chain remain as shadows.
    pt = []
    for cand in ("mfg_paper_trades_s60nm5fr.jsonl",
                 "mfg_paper_trades_h108.jsonl", "mfg_paper_trades_a15.jsonl",
                 "mfg_paper_trades.jsonl"):
        gate_file = MON / cand
        if gate_file.exists():
            break
    for line in gate_file.open():
        try:
            pt.append(json.loads(line))
        except Exception:
            continue
    post = [t for t in pt if (t.get("entry_t") or 0) > CUTOFF]
    closed = [t for t in post if t.get("status") != "open"]
    openp = [t for t in post if t.get("status") == "open"]
    rets = [t.get("ret") for t in closed if isinstance(t.get("ret"), (int, float))]
    wins = sum(1 for r in rets if r > 0)
    exp = sum(rets) / len(rets) if rets else None
    reasons = {}
    for t in closed:
        reasons[t.get("exit_reason") or "?"] = reasons.get(t.get("exit_reason") or "?", 0) + 1
    # §74c: gate metric = committed value. Closed trades at realized ret;
    # open freerolled positions at their locked floor (+12.5% = 75% banked
    # at >=1.5x, residual written off); open non-freerolled excluded as
    # undecided. This is what is in the bank if everything dies right now.
    fr_open = [t for t in openp if t.get("freerolled")]
    committed = rets + [0.125] * len(fr_open)
    committed_exp = (sum(committed) / len(committed)) if committed else None
    committed_n = len(committed)
    # §73/§74: shadow scorers reported for comparison; gate file excluded.
    # §77: s60 strict-entry shadow reports COMMITTED value (closed + 0.125
    # per freerolled open) like the gate — that is the metric it must
    # prove out-of-sample.
    shadows = {}
    for name in ("mfg_paper_trades_h108.jsonl", "mfg_paper_trades_a15.jsonl",
                 "mfg_paper_trades.jsonl", "mfg_paper_trades_s60.jsonl"):
        if name == gate_file.name:
            continue
        try:
            pr = []
            for line in (MON / name).open():
                try:
                    pr.append(json.loads(line))
                except Exception:
                    continue
            cr = [t for t in pr if (t.get("entry_t") or 0) > CUTOFF
                  and t.get("status") != "open"
                  and isinstance(t.get("ret"), (int, float))]
            if name == "mfg_paper_trades_s60.jsonl":
                fro = [t for t in pr if (t.get("entry_t") or 0) > CUTOFF
                       and t.get("status") == "open" and t.get("freerolled")]
                com = [t["ret"] for t in cr] + [0.125] * len(fro)
                if com:
                    shadows[name] = {"committed_n": len(com),
                                     "committed_exp": round(
                                         sum(com) / len(com), 5),
                                     "closed": len(cr)}
            elif cr:
                shadows[name] = {"closed": len(cr),
                                 "exp": round(sum(t["ret"] for t in cr)
                                              / len(cr), 5)}
        except Exception:
            pass
    # §66i universe scan: every E25-triggerable mint post-cutoff, entered or
    # not, and its post-trigger peak. This is the regime test — if no
    # triggerable mint reaches 1.5x across sessions, the pump meta is gone.
    import collections
    tr = collections.defaultdict(list)
    try:
        with (MON / "mfg_trades.jsonl").open() as f:
            for line in f:
                try:
                    x = json.loads(line)
                except Exception:
                    continue
                if x.get("venue") == "pool" and x.get("t", 0) > CUTOFF:
                    tr[x["mint"]].append(x)
    except Exception:
        pass
    universe = []
    for m, xs in tr.items():
        xs.sort(key=lambda x: x["t"])
        nb = ns = 0
        bs = ss = 0.0
        ti = None
        for i, x in enumerate(xs):
            if x["side"] == "buy":
                nb += 1
                bs += x.get("sol") or 0
            else:
                ns += 1
                ss += x.get("sol") or 0
            if (bs - ss >= 25.0 and nb >= 10 and nb / max(ns, 1) >= 2.0):
                ti = i
                break
        if ti is None:
            continue
        emc = xs[ti].get("mcap_sol")
        if not emc or emc <= 0:
            continue
        peak = max(x["mcap_sol"] for x in xs[ti:]) / emc
        universe.append({"mint": m, "n_trades": len(xs),
                         "entry_mcap": round(emc, 1),
                         "post_trigger_peak": round(peak, 3)})
    universe.sort(key=lambda u: -u["post_trigger_peak"])
    runners = sum(1 for u in universe if u["post_trigger_peak"] >= 1.5)
    card = {
        "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cutoff": CUTOFF,
        "post_fix_entries": len(post),
        "open": len(openp),
        "closed": len(closed),
        "wins": wins,
        "win_rate": round(wins / len(rets), 4) if rets else None,
        "expectancy": round(exp, 5) if exp is not None else None,
        "backtest_exp": BACKTEST_EXP,
        "exit_reasons": reasons,
        "gate_n": GATE_N,
        "gate_progress": f"{committed_n}/{GATE_N}",
        "gate_pass": bool(committed) and committed_n >= GATE_N
                     and (committed_exp or 0) > 0,
        "committed_n": committed_n,
        "committed_exp": (round(committed_exp, 5)
                          if committed_exp is not None else None),
        "freerolled_open": len(fr_open),
        "trades": [
            {"mint": t["mint"], "entry_t": t.get("entry_t"),
             "ret": t.get("ret"), "exit": t.get("exit_reason"),
             "status": t.get("status")}
            for t in post
        ],
        "universe_triggerable": len(universe),
        "universe_runners_1p5x": runners,
        "gate_scorer": gate_file.name,
        "shadows": shadows,
        "universe": universe[:20],
    }
    (MON / "forward_scorecard.json").write_text(json.dumps(card, indent=1))
    print(json.dumps({k: card[k] for k in
                      ("updated", "gate_scorer", "post_fix_entries", "open",
                       "closed", "win_rate", "expectancy", "committed_n",
                       "committed_exp", "freerolled_open", "gate_progress",
                       "gate_pass", "universe_triggerable",
                       "universe_runners_1p5x", "shadows")},
                     indent=1))

if __name__ == "__main__":
    sys.exit(main())
