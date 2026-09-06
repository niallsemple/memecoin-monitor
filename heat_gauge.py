"""heat_gauge.py — §422: live market-temperature gauge.

Why: §421 showed mom60 heat swings 9% -> 23% on ~hour waves, and the
+6%/trade edge (§418) lives in the hot waves. This gauge tails the same
curves/trades streams on the 90s cadence and keeps a rolling 60-minute
heat reading so live sizing can follow regime, not hope.

Method: seeds (2-10 SOL) born in the last 60min; once a seed is older
than 60s with >=3 window ticks it becomes scorable with mom60 = last/first
tick mcap. hot = mom60 >= 1.0. Heat = hot fraction of scorable seeds.
Bands (from §421): >=20% HOT, 10-20% WARM, <10% COLD; <8 scorable = THIN
(not enough evidence). Log-only.

State: heat_gauge_state.json (byte bookmarks + rolling seed map)
Out:   heat_state.json (latest reading, read by darwin_status)
Log:   heat_log.jsonl (one row per pass when the reading changes band)
"""
import json
import time
from pathlib import Path

MON = Path(__file__).parent
CURVES = MON / "curves.jsonl"
TRADES = MON / "mfg_trades.jsonl"
STATE = MON / "heat_gauge_state.json"
OUT = MON / "heat_state.json"
LOG = MON / "heat_log.jsonl"

SEED_LO, SEED_HI = 2.0, 10.0
WINDOW_MIN = 60          # look-back for the reading
SCORE_AGE = 60           # seed becomes scorable after this many seconds
HOT_BAR = 1.0            # mom60 >= 1.0 = hot seed


def _load():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:
            pass
    return {"off_curves": CURVES.stat().st_size if CURVES.exists() else 0,
            "off_trades": TRADES.stat().st_size if TRADES.exists() else 0,
            "seeds": {}}


def _tail(path, off):
    size = path.stat().st_size
    if off > size:
        off = 0
    with path.open("rb") as f:
        f.seek(off)
        data = f.read()
    return data.decode("utf-8", "ignore").splitlines(), size


def _band(hot_pct, n):
    if n < 8:
        return "THIN"
    if hot_pct >= 20:
        return "HOT"
    if hot_pct >= 10:
        return "WARM"
    return "COLD"


def run_pass():
    st = _load()
    now = time.time()
    seeds = st["seeds"]

    lines, st["off_curves"] = _tail(CURVES, st["off_curves"])
    for ln in lines:
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get("txType") == "create" and d.get("mint"):
            s = d.get("solAmount") or 0
            if SEED_LO <= s < SEED_HI:
                seeds[d["mint"]] = {"t0": d.get("_ts") or now,
                                    "first": None, "last": None, "n": 0,
                                    "mom": None}

    lines, st["off_trades"] = _tail(TRADES, st["off_trades"])
    for ln in lines:
        try:
            d = json.loads(ln)
        except Exception:
            continue
        m = d.get("mint")
        sd = seeds.get(m)
        if sd and d.get("mcap_sol") and d["t"] <= sd["t0"] + SCORE_AGE:
            if sd["first"] is None:
                sd["first"] = d["mcap_sol"]
            sd["last"] = d["mcap_sol"]
            sd["n"] += 1

    # score + expire
    for m in list(seeds):
        sd = seeds[m]
        age = now - sd["t0"]
        if sd["mom"] is None and age >= SCORE_AGE:
            if sd["n"] >= 3 and sd["first"]:
                sd["mom"] = sd["last"] / sd["first"]
            else:
                sd["mom"] = -1          # unscorable
        if age > (WINDOW_MIN + 5) * 60:
            del seeds[m]

    win = [sd for sd in seeds.values()
           if now - sd["t0"] <= WINDOW_MIN * 60 and sd["mom"] is not None]
    scor = [sd for sd in win if sd["mom"] >= 0]
    hot = sum(1 for sd in scor if sd["mom"] >= HOT_BAR)
    pct = round(100 * hot / len(scor), 1) if scor else 0.0
    reading = {"t": now, "seeds": len(win), "scorable": len(scor),
               "hot": hot, "hot_pct": pct, "band": _band(pct, len(scor))}
    OUT.write_text(json.dumps(reading))

    prev_band = st.get("band")
    if prev_band != reading["band"]:
        with LOG.open("a") as f:
            f.write(json.dumps(reading) + "\n")
    st["band"] = reading["band"]
    STATE.write_text(json.dumps(st))
    return reading


if __name__ == "__main__":
    print(run_pass())
