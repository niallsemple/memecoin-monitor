"""§69: reconstruct curve-phase flow for post-cutoff paper positions via
public-RPC signature replay (Helius outage window had no curve capture).
Writes rug_replay.json; prints rug/runner/quiet comparison."""
import json, time, pathlib, urllib.request, collections

MON = pathlib.Path("/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor")
RPCS = ["https://api.mainnet-beta.solana.com",
        "https://solana-rpc.publicnode.com",
        "https://solana.drpc.org"]
CUTOFF = 1788060000
_i = {"i": 0, "fails": 0}

def rpc(method, params, tries=4):
    body = json.dumps({"jsonrpc": "2.0", "id": 1,
                       "method": method, "params": params}).encode()
    for _ in range(tries):
        url = RPCS[_i["i"] % len(RPCS)]
        try:
            req = urllib.request.Request(
                url, data=body,
                headers={"Content-Type": "application/json",
                         "User-Agent": "Mozilla/5.0 (mfg-replay/1.0)"})
            r = json.loads(urllib.request.urlopen(req, timeout=25).read())
            if "error" in r:
                raise Exception(str(r["error"])[:80])
            time.sleep(0.22)
            return r.get("result")
        except Exception:
            _i["i"] += 1
            _i["fails"] += 1
            time.sleep(0.6)
    return None

# ---- outcomes from the §68-marked paper file ----
positions = {}
with open(MON / "mfg_paper_trades.jsonl") as f:
    for line in f:
        try:
            x = json.loads(line)
        except Exception:
            continue
        positions[x["mint"]] = x
cohort = {m: p for m, p in positions.items() if p.get("entry_t", 0) > CUTOFF}
print(f"post-cutoff cohort: {len(cohort)}")

# ---- births from curves.jsonl ----
births = {}
with open(MON / "curves.jsonl") as f:
    for line in f:
        try:
            d = json.loads(line)
        except Exception:
            continue
        m = d.get("mint")
        if m in cohort and d.get("txType") == "create":
            births[m] = {"curve": d.get("bondingCurveKey"),
                         "ts": d.get("_ts"), "seed": d.get("solAmount") or 0,
                         "creator": d.get("traderPublicKey"),
                         "symbol": d.get("symbol")}
        if m in cohort and d.get("txType") == "migrate":
            births.setdefault(m, {})["migrated"] = d.get("_ts")
print(f"births found: {len(births)}")

# ---- signature replay per mint (resumable: writes after every mint) ----
out = {}
try:
    out = json.loads((MON / "rug_replay.json").read_text())
    print(f"resuming: {len(out)} mints already replayed")
except Exception:
    pass
for n, (m, b) in enumerate(sorted(births.items(),
                                  key=lambda kv: kv[1].get("ts") or 0)):
    if m in out:
        continue
    curve = b.get("curve")
    if not curve:
        continue
    sigs = rpc("getSignaturesForAddress", [curve, {"limit": 250}]) or []
    trades = []
    for s in sigs:
        sig = s.get("signature")
        if not sig:
            continue
        tx = rpc("getTransaction",
                 [sig, {"encoding": "json",
                        "maxSupportedTransactionVersion": 0}])
        if not tx:
            continue
        try:
            keys = [k if isinstance(k, str) else k["pubkey"]
                    for k in tx["transaction"]["message"]["accountKeys"]]
            idx = keys.index(curve)
            meta = tx["meta"]
            dv = meta["postBalances"][idx] - meta["preBalances"][idx]
            trades.append({"t": tx.get("blockTime") or s.get("blockTime"),
                           "dv": dv / 1e9})
        except Exception:
            continue
    trades = [x for x in trades if x["t"]]
    trades.sort(key=lambda x: x["t"])
    out[m] = {"birth": b, "trades": trades, "n_sigs": len(sigs)}
    (MON / "rug_replay.json").write_text(json.dumps(out))
    print(f"[{n+1}/{len(births)}] {m[:10]}… sigs={len(sigs)} txs={len(trades)}",
          flush=True)

(MON / "rug_replay.json").write_text(json.dumps(out))
print(f"rpc failures: {_i['fails']}")

# ---- features + comparison ----
def feats(m):
    b = out[m]["birth"]
    t0 = b.get("ts") or (out[m]["trades"][0]["t"] if out[m]["trades"] else 0)
    tr = out[m]["trades"]
    f15 = [x for x in tr if x["t"] - t0 <= 900]
    sells = [x for x in tr if x["dv"] < -0.001]
    buys = [x for x in tr if x["dv"] > 0.001]
    s15 = [x for x in f15 if x["dv"] < -0.001]
    return {
        "symbol": b.get("symbol"), "seed": round(b.get("seed") or 0, 1),
        "n_tx": len(tr), "n_buy": len(buys), "n_sell": len(sells),
        "buy_sol": round(sum(x["dv"] for x in buys), 1),
        "sell_sol": round(-sum(x["dv"] for x in sells), 1),
        "first_sell_s": round(sells[0]["t"] - t0) if sells else None,
        "largest_sell": round(max((-x["dv"] for x in sells), default=0), 1),
        "sells_15m": len(s15),
        "sell_sol_15m": round(-sum(x["dv"] for x in s15), 1),
        "grad_min": (round((b.get("migrated") - t0) / 60, 1)
                     if b.get("migrated") else None),
    }

rows = []
for m, p in cohort.items():
    if m not in out:
        continue
    f = feats(m)
    ret, peak = p.get("ret"), p.get("peak") or 0
    cls = "RUG" if ret is not None and ret <= -0.9 else (
        "RUNNER" if peak >= 1.5 else "quiet")
    rows.append((cls, m, p, f))

print("\n=== curve-phase features by outcome class ===")
for cls in ("RUNNER", "quiet", "RUG"):
    grp = [r for r in rows if r[0] == cls]
    print(f"\n--- {cls} ({len(grp)}) ---")
    for _, m, p, f in sorted(grp, key=lambda r: -(r[2].get("peak") or 0)):
        print(f"  {f['symbol'] or m[:8]:<14} seed={f['seed']:>6} "
              f"tx={f['n_tx']:>4} sells={f['n_sell']:>3} "
              f"1st_sell={str(f['first_sell_s']):>6}s "
              f"big_sell={f['largest_sell']:>7} sells15m={f['sells_15m']:>3} "
              f"sellSOL15m={f['sell_sol_15m']:>7} grad={f['grad_min']}min "
              f"peak={p.get('peak')} ret={p.get('ret')}")

# creator overlap
creators = collections.Counter()
for m, p in cohort.items():
    c = births.get(m, {}).get("creator")
    if c:
        creators[c] += 1
print("\ncreator counts:", dict(creators))
