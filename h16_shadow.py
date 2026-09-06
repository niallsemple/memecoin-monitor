#!/usr/bin/env python3
"""H16 shadow forward test — zero-risk OOS evidence for the mom+dd combo.

Each tracker pass (invoked from live_trader.exit_watch tail, importlib
live-loaded):
  1. tail curves.jsonl (byte bookmark) -> new creates with 2 <= seed < 10 SOL
     become PENDING
  2. tail mfg_trades.jsonl (byte bookmark) -> ticks for pending/open mints
  3. pending aged >=180s -> score mom/dd/buyfrac vs §397 tercile thresholds;
     combo pass -> shadow OPEN at last-tick mcap; else REJECTED
  4. open positions: +20% -> WIN (bank), -8% -> LOSS (cut), 1h -> TIMEOUT at last
All results appended to h16_shadow.jsonl. No orders, no wallet touches.
"""
import json, time
from pathlib import Path

MON = Path(__file__).parent
CURVES = MON / "curves.jsonl"
TRADES = MON / "mfg_trades.jsonl"
STATE = MON / "h16_shadow_state.json"
LOG = MON / "h16_shadow.jsonl"

SEED_LO, SEED_HI = 2.0, 10.0
ENTRY_DELAY = 180
HORIZON = 3600
UP, DN = 1.20, 0.92
MOM_Q67, DD_Q67, BF_Q67 = 1.1027, 0.5896, 0.5762  # §397 tercile cuts
MAX_PENDING_AGE = 600  # no ticks by +10m -> dead, drop


def _load():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:
            pass
    # first run: prime bookmarks at EOF — forward test only, no backfill
    return {"off_curves": CURVES.stat().st_size,
            "off_trades": TRADES.stat().st_size, "pending": {}, "open": {}}


def _tail(path, off):
    size = path.stat().st_size
    if off > size:  # rotated/truncated
        off = 0
    with path.open("rb") as f:
        f.seek(off)
        data = f.read()
    lines = data.decode("utf-8", "ignore").splitlines()
    return lines, size


def run_pass():
    st = _load()
    now = time.time()
    ticks = {}

    lines, st["off_curves"] = _tail(CURVES, st["off_curves"])
    for ln in lines:
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get("txType") == "create" and d.get("mint"):
            s = d.get("solAmount") or 0
            if SEED_LO <= s < SEED_HI:
                st["pending"][d["mint"]] = {"t0": d.get("_ts") or now,
                                            "seed": s, "ticks": []}

    lines, st["off_trades"] = _tail(TRADES, st["off_trades"])
    for ln in lines:
        try:
            d = json.loads(ln)
        except Exception:
            continue
        m = d.get("mint")
        if m in st["pending"]:
            if d.get("mcap_sol"):
                st["pending"][m]["ticks"].append(
                    (d["t"], d.get("side") or "", d.get("sol") or 0.0,
                     d["mcap_sol"]))
                if len(st["pending"][m]["ticks"]) > 3000:
                    st["pending"][m]["ticks"] = st["pending"][m]["ticks"][-3000:]
        elif m in st["open"]:
            if d.get("mcap_sol"):
                ticks.setdefault(m, []).append((d["t"], d.get("side") or "",
                                                d.get("sol") or 0.0,
                                                d["mcap_sol"]))

    with LOG.open("a") as lg:
        # score pending
        for mint in list(st["pending"]):
            p = st["pending"][mint]
            age = now - p["t0"]
            if age < ENTRY_DELAY:
                continue
            ts = sorted(p["ticks"])
            if not ts:
                # ticks may predate this pass's bookmark window; keep waiting
                if age > MAX_PENDING_AGE:
                    st["pending"].pop(mint)
                    lg.write(json.dumps({"action": "h16_drop", "mint": mint,
                                         "reason": "no ticks", "t": now}) + "\n")
                continue
            m0 = ts[0][3]
            pre = [x for x in ts if x[0] <= p["t0"] + ENTRY_DELAY]
            if len(pre) < 3 or not m0:
                st["pending"].pop(mint)
                continue
            mom = pre[-1][3] / m0
            peak = max(x[3] for x in pre)
            dd = min(x[3] for x in pre) / peak if peak else 0
            buys = [x for x in pre if x[1] == "buy"]
            bf = len(buys) / len(pre)
            st["pending"].pop(mint)
            if mom >= MOM_Q67 and dd >= DD_Q67 and bf >= BF_Q67:
                st["open"][mint] = {"entry_t": pre[-1][0], "entry_mcap": pre[-1][3],
                                    "seed": p["seed"], "mom": round(mom, 3),
                                    "dd": round(dd, 3), "bf": round(bf, 3),
                                    "ticks": [(x[0], x[3]) for x in ts if x[0] > pre[-1][0]]}
                lg.write(json.dumps({"action": "h16_open", "mint": mint, "t": now,
                                     "entry_mcap": pre[-1][3], "mom": round(mom, 3),
                                     "dd": round(dd, 3), "bf": round(bf, 3),
                                     "seed": p["seed"]}) + "\n")
            else:
                lg.write(json.dumps({"action": "h16_reject", "mint": mint, "t": now,
                                     "mom": round(mom, 3), "dd": round(dd, 3),
                                     "bf": round(bf, 3), "seed": p["seed"]}) + "\n")

        # manage open shadow positions
        for mint in list(st["open"]):
            o = st["open"][mint]
            o["ticks"].extend((x[0], x[3]) for x in ticks.get(mint, []))
            o["ticks"] = sorted(o["ticks"])[-5000:]
            r = [x[1] / o["entry_mcap"] for x in o["ticks"] if x[1] > 0]
            close = None
            for x in o["ticks"]:
                if x[1] <= 0:
                    continue
                rr = x[1] / o["entry_mcap"]
                if rr >= UP:
                    close = ("win", UP, x[0]); break
                if rr <= DN:
                    close = ("loss", DN, x[0]); break
            if close is None and now - o["entry_t"] > HORIZON:
                close = ("timeout", r[-1] if r else 1.0, now)
            if close:
                outcome, mult, ct = close
                st["open"].pop(mint)
                lg.write(json.dumps({"action": "h16_close", "mint": mint, "t": ct,
                                     "outcome": outcome, "mult": round(mult, 4),
                                     "mins": round((ct - o["entry_t"]) / 60, 1),
                                     "mom": o["mom"], "dd": o["dd"], "bf": o["bf"],
                                     "seed": o["seed"]}) + "\n")

    STATE.write_text(json.dumps(st))
    return {"pending": len(st["pending"]), "open": len(st["open"])}


if __name__ == "__main__":
    print(run_pass())
