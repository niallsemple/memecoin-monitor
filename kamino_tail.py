#!/usr/bin/env python3
"""Kamino obligation radar via crank-tail (no getProgramAccounts — Helius blocks
gPA on KLend). Cranks refresh the RISKY obligations; we tail refresh_obligation
txs, harvest obligation pubkeys, then batch getAccountInfo and decode the stored
health fields (borrow_factor_adjusted_debt vs unhealthy_borrow_value, u128 /2^60).
"""
import json, base64, time, sys
from pathlib import Path
import urllib.request

MON = Path(__file__).resolve().parent
KEY = (MON / "helius_key.txt").read_text().strip()
RPC = f"https://mainnet.helius-rpc.com/?api-key={KEY}"
KLEND = "KLend2g3cP87fffoy8q1mQqGKjrxjC8boSyAYavgmjD"
ALPH = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

REFRESH_DISC = bytes([33, 132, 147, 228, 151, 192, 72, 89])
SF60 = float(2 ** 60)
OFF_ADJ_DEBT, OFF_UNHEALTHY = 2208, 2256
OFF_SLOT, OFF_OWNER = 16, 64

def b58decode(s: str) -> bytes:
    n = 0
    for c in s:
        n = n * 58 + ALPH.index(c)
    b = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\0" * (len(s) - len(s.lstrip("1"))) + b

def b58encode(b: bytes) -> str:
    n = int.from_bytes(b, "big"); s = ""
    while n:
        n, r = divmod(n, 58); s = ALPH[r] + s
    return "1" * (len(b) - len(b.lstrip(b"\0"))) + (s or "")

def rpc(method, params, timeout=60):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params}).encode()
    req = urllib.request.Request(RPC, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def u128le(raw, off):
    return int.from_bytes(raw[off:off+16], "little")

def harvest_obligations(limit=100, verbose=True):
    """Return (obligation_pubkeys set, sig_span_seconds)."""
    sigs = rpc("getSignaturesForAddress", [KLEND, {"limit": limit}]).get("result") or []
    if not sigs:
        return set(), 0
    span = sigs[0]["blockTime"] - sigs[-1]["blockTime"] if sigs[0].get("blockTime") and sigs[-1].get("blockTime") else 0
    obs = set()
    n_tx = 0
    for s in sigs:
        tx = rpc("getTransaction", [s["signature"], {
            "encoding": "jsonParsed", "maxSupportedTransactionVersion": 0,
            "commitment": "confirmed"}]).get("result")
        if not tx:
            continue
        n_tx += 1
        ixs = list(tx["transaction"]["message"].get("instructions", []))
        for inner in (tx.get("meta") or {}).get("innerInstructions") or []:
            ixs += inner.get("instructions", [])
        for ix in ixs:
            if not isinstance(ix, dict) or ix.get("programId") != KLEND:
                continue
            data = ix.get("data")
            if not data:
                continue
            try:
                raw = b58decode(data)
            except Exception:
                continue
            if raw[:8] == REFRESH_DISC and len(ix.get("accounts", [])) >= 2:
                obs.add(ix["accounts"][1])
        time.sleep(0.02)
    if verbose:
        print(f"  {len(sigs)} sigs spanning {span}s → {n_tx} txs parsed → {len(obs)} unique obligations refreshed")
    return obs, span

def health_check(obs: list) -> list:
    """Batch fetch + decode. Returns sorted [(margin, adj, unhealthy, slot, owner, pk)]."""
    rows = []
    for i in range(0, len(obs), 100):
        batch = obs[i:i+100]
        res = rpc("getMultipleAccounts", [batch, {"encoding": "base64"}]).get("result")
        slot_now = rpc("getSlot", []).get("result", 0)
        for pk, acc in zip(batch, res.get("value", [])):
            if not acc:
                continue
            raw = base64.b64decode(acc["data"][0])
            if len(raw) < 2272:
                continue
            adj = u128le(raw, OFF_ADJ_DEBT) / SF60
            unh = u128le(raw, OFF_UNHEALTHY) / SF60
            if adj <= 0:
                continue
            slot = int.from_bytes(raw[OFF_SLOT:OFF_SLOT+8], "little")
            owner = b58encode(raw[OFF_OWNER:OFF_OWNER+32])
            rows.append((unh - adj, adj, unh, slot_now - slot, owner, pk))
        time.sleep(0.1)
    rows.sort()
    return rows

ALERT_PCT = 0.05  # flag when margin < 5% of adjusted debt (or negative)

# §465 auto-fire settings
MIN_FIRE_DEBT_USD = 50.0     # below this the gas/rent eats the bonus
FIRE_COOLDOWN_S = 600        # one attempt per obligation per 10 min
_FIRED = {}
_WALLET = None

def _wallet_addr():
    global _WALLET
    if _WALLET is None:
        _WALLET = json.loads((MON / "live_wallet.json").read_text())["address"]
    return _WALLET

def _try_fire(ob_pk: str, margin: float, adj_debt: float):
    """Simulate the full bundle; fire only if the sim fully succeeds.
    Everything logged to kamino_fires.jsonl. Never raises."""
    rec = {"ts": time.time(), "ob": ob_pk, "margin": margin,
           "adj_debt": adj_debt, "result": "pending"}
    try:
        import importlib.util as _il
        _s = _il.spec_from_file_location("kamino_hunt", str(MON / "kamino_hunt.py"))
        _kh = _il.module_from_spec(_s)
        _s.loader.exec_module(_kh)
        out = _kh.simulate_fire(ob_pk, _wallet_addr())
        sim = out.get("sim") or {}
        val = sim.get("value", {}) if isinstance(sim, dict) else {}
        rec["sim_err"] = val.get("err")
        rec["est_seize"] = (out.get("meta") or {}).get("swap", {}).get("est_seize")
        if val.get("err") is None and val.get("logs"):
            # sim clean → fire for real
            ixs, meta = _kh.build_fire_bundle(ob_pk, _wallet_addr())
            r = meta["resolve"]
            est = _kh.estimate_seize(r)
            sw, _sm = _kh.build_swap_leg(r["withdraw"]["liq_mint"],
                                         r["repay"]["liq_mint"], est,
                                         _wallet_addr())
            if sw:
                ixs = ixs[:-1] + sw + [ixs[-1]]
            _kh.ensure_alt(_wallet_addr(), [b58encode(p) for p, a, _ in ixs] +
                           [b58encode(k) for _, a, _ in ixs for k, _, _ in a])
            tx = _kh.compile_fire_tx(ixs, _wallet_addr())
            resp = rpc("sendTransaction", [tx, {"encoding": "base64"}])
            rec["fire_sig"] = resp.get("result")
            rec["fire_err"] = resp.get("error")
            rec["result"] = "fired" if resp.get("result") else "fire_rejected"
        else:
            rec["result"] = "sim_failed_skip"
    except Exception as e:
        rec["result"] = f"error: {e}"[:200]
    try:
        with open(MON / "kamino_fires.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass


def run_pass():
    """Single radar sweep for the tracker kamino_loop thread. Appends
    near-line / liquidatable rows to kamino_alerts.jsonl; always refreshes
    kamino_tail_latest.json. Never raises."""
    try:
        obs, span = harvest_obligations(limit=60, verbose=False)
        if not obs:
            (MON / "kamino_tail_latest.json").write_text(
                json.dumps({"ts": time.time(), "rows": []}))
            return
        rows = health_check(sorted(obs))
        out = {"ts": time.time(), "rows": [{"pubkey": pk, "owner": ow,
               "adj_debt": a, "unhealthy": u, "margin": m, "slot_age": sa}
               for m, a, u, sa, ow, pk in rows]}
        (MON / "kamino_tail_latest.json").write_text(json.dumps(out, indent=1))
        hits = [r for r in rows if r[0] < max(0.0, ALERT_PCT * r[1])]
        if hits:
            with open(MON / "kamino_alerts.jsonl", "a") as f:
                for m, a, u, sa, ow, pk in hits:
                    f.write(json.dumps({
                        "ts": time.time(), "pubkey": pk, "owner": ow,
                        "adj_debt": a, "unhealthy": u, "margin": m,
                        "slot_age": sa,
                        "kind": "liquidatable" if m < 0 else "near_line"}) + "\n")
        # §465 auto-fire: liquidatable rows only, sim-gated, zero-capital flash
        for m, a, u, sa, ow, pk in rows:
            if m >= 0 or a < MIN_FIRE_DEBT_USD:
                continue
            if time.time() - _FIRED.get(pk, 0) < FIRE_COOLDOWN_S:
                continue
            _FIRED[pk] = time.time()
            _try_fire(pk, m, a)
    except Exception:
        pass


def main():
    t0 = time.time()
    print("harvesting crank-refreshed obligations...")
    obs, span = harvest_obligations(limit=100)
    if not obs:
        print("no refreshed obligations in window"); return
    rows = health_check(sorted(obs))
    print(f"\n{len(rows)} obligations with debt (fetched in {time.time()-t0:.0f}s):")
    for margin, adj, unh, age, owner, pk in rows[:20]:
        flag = "LIQUIDATABLE" if margin < 0 else ("NEAR" if margin < 0.05 * adj else "ok")
        print(f"  [{flag:12s}] {pk[:12]}.. adj=${adj:,.0f} unh=${unh:,.0f} "
              f"margin=${margin:,.0f} slot_age={age} owner={owner[:8]}..")
    out = {"ts": time.time(), "rows": [{"pubkey": pk, "owner": ow,
           "adj_debt": a, "unhealthy": u, "margin": m, "slot_age": sa}
           for m, a, u, sa, ow, pk in rows]}
    (MON / "kamino_tail_latest.json").write_text(json.dumps(out, indent=1))
    print(f"\nwrote {len(out['rows'])} rows to kamino_tail_latest.json")

if __name__ == "__main__":
    main()
