"""dbc_scout.py — §411: post-birth tick capture for birth_watch mints
(Meteora DBC + Raydium LaunchLab). READ-ONLY.

Why: birth_watch SEES births on pump.fun's competitors but nothing tracks
what happens next. H16 asks "+20% within minutes?" for pump.fun seeds;
this asks the same question cross-venue so the entry filter (§410 H16b
candidate bar) can be tested on DBC/LaunchLab births too.

Method: for each mint in birth_watch.jsonl, poll Jupiter lite-api
(1 SOL -> token quote) at fixed ages [60,120,180,300,600,1800]s.
First successful quote = baseline price; later polls log the multiple.
Failed quotes log indexed:false — time-to-index is itself a signal
(pre-index window = the earliest-entry opportunity).

State: dbc_scout_state.json {mint: {birth_t, venue, done:[ages], base}}
Log:   dbc_scout.jsonl {t, mint, venue, age, price_sol, mult, indexed}
"""
import json
import time
import urllib.request
from pathlib import Path

MON = Path(__file__).resolve().parent
STATE = MON / "dbc_scout_state.json"
BIRTHS = MON / "birth_watch.jsonl"
LOG = MON / "dbc_scout.jsonl"

AGES = [60, 120, 180, 300, 600, 1800]      # post-birth poll offsets (s)
WSOL = "So11111111111111111111111111111111111111112"
QUOTE = ("https://lite-api.jup.ag/swap/v1/quote?inputMint=%s&outputMint=%s"
         "&amount=%d&slippageBps=50")
MAX_TRACKED = 40                            # cap concurrent tracked mints


def _load_state():
    try:
        st = json.loads(STATE.read_text())
        if "mints" not in st:                 # legacy flat layout
            st = {"mints": st, "seen": list(st)}
        return st
    except Exception:
        return {"mints": {}, "seen": []}


def _save_state(st):
    STATE.write_text(json.dumps(st))


def _quote_sol_to_token(mint):
    """Return (price SOL per token, impact_pct, amm_label) or (None,...) if
    not indexed / no route. §411d: quotes routing through dust pools
    (priceImpact > 5% for 1 SOL) are lies — AGq2KnxF quoted 581x through a
    $0.43-liq DAMM v2 stub while the active PumpSwap pool sat 3x cheaper."""
    url = QUOTE % (WSOL, mint, 1_000_000_000)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "darwin"})
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read())
        out = int(d.get("outAmount", 0))
        if out <= 0:
            return None, None, None
        impact = float(d.get("priceImpactPct", 0) or 0)
        amms = [s.get("swapInfo", {}).get("label")
                for s in d.get("routePlan", [])]
        return 1e9 / out, impact, ",".join(a for a in amms if a)
    except Exception:
        return None, None, None


def run_pass():
    now = time.time()
    st = _load_state()
    mints, seen = st["mints"], set(st["seen"])

    # register new births (§411c: seen-set is permanent — a finished mint
    # must never re-register, or it re-polls the whole ladder every pass)
    if BIRTHS.exists():
        for line in BIRTHS.read_text().splitlines():
            try:
                b = json.loads(line)
            except Exception:
                continue
            m = b.get("mint")
            if m and m not in seen and len(mints) < MAX_TRACKED:
                mints[m] = {"birth_t": b.get("t", now),
                            "venue": b.get("venue"), "done": [], "base": None}
                seen.add(m)

    out = []
    for mint, s in list(mints.items()):
        age_now = now - s["birth_t"]
        for a in AGES:
            if a in s["done"] or age_now < a:
                continue
            px, impact, amms = _quote_sol_to_token(mint)
            rec = {"t": now, "mint": mint, "venue": s["venue"], "age": a}
            if px is None:
                rec["indexed"] = False
            elif impact is not None and impact > 0.05:
                # dust-pool quote: indexed but untrusted — never baseline
                rec.update({"indexed": True, "dust": True,
                            "impact": round(impact, 4), "amm": amms})
            else:
                if s["base"] is None:
                    s["base"] = px
                rec.update({"indexed": True, "price_sol": px,
                            "mult": round(px / s["base"], 4),
                            "impact": round(impact or 0, 5), "amm": amms})
            out.append(rec)
            s["done"].append(a)
        # retire (but never forget) fully-polled mints older than 2 days
        if len(s["done"]) == len(AGES) and age_now > 2 * 86400:
            del mints[mint]

    st["seen"] = sorted(seen)[-2000:]         # bounded memory
    if out:
        with LOG.open("a") as f:
            for r in out:
                f.write(json.dumps(r) + "\n")
    _save_state(st)


if __name__ == "__main__":
    run_pass()
    print("dbc_scout pass ok")
