#!/usr/bin/env python3
"""armed_pool_replay.py — honest pool-price-path reconstruction for §120
armed-birth launches (§121 replay).

For each known armed launch, pull every pool transaction signature
(chronological), parse pre/post pool-vault balances out of each tx
(owner == pool PDA), and rebuild the true per-tx price path. Then score
the armed-entry strategy honestly on that path:
  entry  = first reconstructed price (~1x migration seed price)
  exits  = freeroll 75% @ >=1.5x, trail remaining at 50% of peak,
           hard stop -60%, 120-min timestop. Fills at the price of the
           first tx that crosses each level (conservative: no intra-tx
           assumption).

Checkpoints after every tx (armed_pool_replay_state.json +
armed_pool_path_<NAME>.jsonl) so it resumes across invocations.
Usage: python3 armed_pool_replay.py [--budget 240]
"""
import argparse
import json
import time
import urllib.request
from pathlib import Path

MON = Path("/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor")
STATE = MON / "armed_pool_replay_state.json"
WSOL = "So11111111111111111111111111111111111111112"
TOK2022 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
RPCS = ("https://solana-rpc.publicnode.com",
        "https://api.mainnet-beta.solana.com")

CASES = {
    "GROKCAT": {"mint": "2a1hX8xnXMPGt2f6FBvEUQEefk8N7LijnyeLCwehpump",
                "pool": "DKxUUeWw4ad2MCYmXCDvhx4xUTjbTDhhVSUPTcZTbJwq",
                "mig_ts": 1788280371.0},
    "Erin":    {"mint": "GeR3KJHTc1wRp5v5jMv7DcoSM8A5zAGNgknTGbjnpump",
                "pool": "5WGFJqgQb6kjieJALEJV1nXEGiBn88bJFxEaxEtzU1t8",
                "mig_ts": 1788282385.0},
    "GPRO":    {"mint": "GcSgbzMvYhz8RXffYZDjUgLafVtYVv9QG2FUoerNpump",
                "pool": "6cV33vBNaCTsQLLyt7GmGSLj1YZrguipA6LwdTurtToQ",
                "mig_ts": 1788283980.0},
}
MIG_PX = 67.405853768 / 206900000  # SOL per token at pool seeding

_rc = {"i": 0}


def rpc(method, params):
    for attempt in range(2):
        for k in range(len(RPCS)):
            url = RPCS[(_rc["i"] + k) % len(RPCS)]
            try:
                body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                                   "params": params}).encode()
                req = urllib.request.Request(
                    url, data=body, headers={"Content-Type": "application/json"})
                r = json.loads(urllib.request.urlopen(req, timeout=12).read())
                time.sleep(0.5)
                if r.get("result") is not None:
                    return r["result"]
            except Exception:
                continue
    return None


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {}


def save_state(st):
    STATE.write_text(json.dumps(st, indent=1))


def collect_sigs(pool):
    """All signatures, chronological (oldest first)."""
    out, before = [], None
    while True:
        p = {"limit": 1000}
        if before:
            p["before"] = before
        page = rpc("getSignaturesForAddress", [pool, p]) or []
        if not page:
            break
        out = page + out
        if len(page) < 1000:
            break
        before = page[-1]["signature"]
    return out


def vault_deltas(txr, pool, mint):
    """Return (t, post_q_sol, post_b_tokens, dq_sol) or None."""
    meta = txr.get("meta") or {}
    if meta.get("err"):
        return None

    def bal(rows):
        q = b = None
        for tb in rows or []:
            if tb.get("owner") != pool:
                continue
            amt = float(tb["uiTokenAmount"]["uiAmount"] or 0)
            if tb.get("mint") == WSOL:
                q = amt
            elif tb.get("mint") == mint:
                b = amt
        return q, b

    pq, pb = bal(meta.get("preTokenBalances"))
    aq, ab = bal(meta.get("postTokenBalances"))
    if aq is None or ab is None or ab <= 0:
        return None
    dq = (aq - (pq or 0.0))
    return (txr.get("blockTime"), aq, ab, dq)


def score(path, mig_ts):
    """Score the armed-entry stack on a reconstructed path."""
    if not path:
        return None
    entry_px = path[0]["px"]
    peak = 1.0
    banked = 0.0
    stake = 1.0
    freerolled = False
    exit_reason = None
    exit_px = None
    t_entry = path[0]["t"]
    for r in path:
        x = r["px"] / entry_px
        peak = max(peak, x)
        if not freerolled and x >= 1.5:
            banked += 0.75 * 1.5
            stake -= 0.75
            freerolled = True
        if freerolled and x <= 0.5 * peak:
            banked += stake * x
            exit_reason, exit_px = "trail", r["px"]
            break
        if not freerolled and x <= 0.40:
            banked += stake * x
            exit_reason, exit_px = "stop", r["px"]
            break
        if r["t"] - t_entry >= 7200:
            banked += stake * x
            exit_reason, exit_px = "timestop", r["px"]
            break
    if exit_reason is None:
        exit_reason = "open"
        banked += stake * (path[-1]["px"] / entry_px)
    return {"entry_px": entry_px, "entry_t": t_entry,
            "mins_from_migration": round((t_entry - mig_ts) / 60, 1),
            "peak_x": round(peak, 2), "exit": exit_reason,
            "ret": round(banked - 1.0, 4), "n_ticks": len(path),
            "last_t": path[-1]["t"],
            "age_min": round((path[-1]["t"] - t_entry) / 60, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=240)
    args = ap.parse_args()
    t_end = time.time() + args.budget

    st = load_state()
    for name, c in CASES.items():
        if time.time() > t_end:
            break
        cs = st.setdefault(name, {"sigs": [], "parsed": 0, "done_sigs": False})
        path_f = MON / f"armed_pool_path_{name}.jsonl"
        if cs["done_sigs"] and "work" not in cs:
            if cs["sigs"] and isinstance(cs["sigs"][0], str):
                cs["done_sigs"] = False  # legacy: recollect with times
        if not cs["done_sigs"]:
            sigs = collect_sigs(c["pool"])
            if sigs:
                cs["sigs"] = [{"s": s["signature"], "t": s["blockTime"]}
                              for s in sigs]
                cs["done_sigs"] = True
                save_state(st)
                print(f"{name}: {len(sigs)} sigs collected")
        if cs["done_sigs"] and "work" not in cs:
            # decision-relevant window only: birth-2m .. birth+90m;
            # stride caps ~4000 ticks (exit levels survive thinning)
            win = [s["s"] for s in cs["sigs"]
                   if c["mig_ts"] - 120 <= s["t"] <= c["mig_ts"] + 90 * 60]
            stride = max(1, len(win) // 4000)
            cs["work"] = win[::stride]
            cs["parsed"] = 0
            save_state(st)
            print(f"{name}: work {len(cs['work'])} ticks (stride {stride})")
        n_new = 0
        with path_f.open("a") as pf:
            while cs["parsed"] < len(cs.get("work") or []):
                if time.time() > t_end:
                    break
                sig = cs["work"][cs["parsed"]]
                txr = rpc("getTransaction",
                          [sig, {"encoding": "jsonParsed",
                                 "maxSupportedTransactionVersion": 0}])
                if txr is None:
                    cs["parsed"] += 1
                    continue
                vd = vault_deltas(txr, c["pool"], c["mint"])
                if vd:
                    t, aq, ab, dq = vd
                    # skip the pool-seeding state itself — within-slot sig
                    # order is not causal, and the seed row poisons entry_px
                    if abs(aq - 67.405853768) < 0.01 and ab == 206900000.0:
                        cs["parsed"] += 1
                        continue
                    px = aq / ab
                    side = "buy" if dq > 0 else ("sell" if dq < 0 else "flat")
                    pf.write(json.dumps({
                        "t": t, "sig": sig, "pool_sol": round(aq, 4),
                        "pool_tok": round(ab, 0), "px": px,
                        "x_mig": round(px / MIG_PX, 4),
                        "side": side, "dq_sol": round(dq, 4)}) + "\n")
                    n_new += 1
                cs["parsed"] += 1
                if cs["parsed"] % 25 == 0:
                    save_state(st)
                    pf.flush()
        save_state(st)
        print(f"{name}: parsed {cs['parsed']}/{len(cs.get('work') or [])}"
              f" (+{n_new} ticks this run)")

    # score whatever paths exist
    out = {}
    for name, c in CASES.items():
        path_f = MON / f"armed_pool_path_{name}.jsonl"
        if not path_f.exists():
            continue
        path = [json.loads(l) for l in path_f.open()]
        path.sort(key=lambda r: (r["t"], r["sig"]))
        s = score(path, c["mig_ts"])
        if s:
            out[name] = s
            print(f"{name}: entry {s['mins_from_migration']}m post-mig, "
                  f"peak {s['peak_x']}x, exit={s['exit']}, "
                  f"ret={s['ret']:+.2%}, ticks={s['n_ticks']}, "
                  f"age={s['age_min']}m")
    (MON / "armed_pool_score.json").write_text(json.dumps(out, indent=1))
    print("wrote armed_pool_score.json")


if __name__ == "__main__":
    main()
