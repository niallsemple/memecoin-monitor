#!/usr/bin/env python3
"""§130: curve-phase replay for armed-birth cases.

§129 killed pool-birth entry: GPRO's pool opened already 94.5x the seed
price — the +123x was a CURVE-phase phenomenon. This replay answers the
follow-up: what would a curve-venue entry at armed-birth detection have
done, traded with the live exit stack (abort15/abort30/freeroll/trail/
timestop)?

Method: for each case, walk the bonding-curve PDA's signature history,
reconstruct exact curve price from on-chain deltas:
    px = (r_sol_lamports + 30e9) / (r_tok + 279_900_191)   [SOL/token]
(pump.fun virtual offsets: v_sol0 = 30 SOL, v_tok0 - r_tok0 = 279,900,191).
r_sol comes from meta.pre/postBalances at the curve account index,
r_tok from pre/postTokenBalances (owner == curve, mint == case mint).

Entry = first reconstructed tick at/after the curve's first tx
(= armed-birth detection at birth). Exit stack mirrors exit_watch:
  freeroll  : x >= 1.8  -> bank 60% at 1.8x, keep 40%
  trail     : freerolled and x <= 0.55 * peak -> sell rest
  abort15   : not freerolled, t >= 15m, x < 1.08 -> sell all
  abort30   : not freerolled, t >= 30m, x < 1.25 -> sell all
  timestop  : t >= 120m -> sell all
  migrated  : curve complete (terminal; value carried at last curve px
              — conservative: ignores the post-migration pool wick)
Checkpointed in armed_curve_replay_state.json; paths in
armed_curve_path_<NAME>.jsonl. Run slices: --budget 200.
"""
import argparse, json, struct, time, urllib.request
from pathlib import Path

MON = Path(__file__).resolve().parent
STATE_F = MON / "armed_curve_replay_state.json"
RPCS = ["https://solana-rpc.publicnode.com",
        "https://api.mainnet-beta.solana.com"]

# --- minimal base58 + PDA (same construction as live_trader.py §111) ---
_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
def b58dec(s):
    n = 0
    for ch in s:
        n = n * 58 + _B58.index(ch)
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return b"\x00" * (len(s) - len(s.lstrip("1"))) + b
def b58enc(b):
    n = int.from_bytes(b, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = _B58[r] + out
    return "1" * (len(b) - len(b.lstrip(b"\x00"))) + out
import hashlib
_P = 2**255 - 19
_D = -121665 * pow(121666, _P - 2, _P) % _P
def _on_curve(h):
    y = int.from_bytes(h, "little") & ((1 << 255) - 1)
    if y >= _P:
        return False
    y2 = y * y % _P
    denom = (_D * y2 + 1) % _P
    if denom == 0:
        return False
    x2 = (y2 - 1) * pow(denom, _P - 2, _P) % _P
    return x2 == 0 or pow(x2, (_P - 1) // 2, _P) == 1
def pda(seeds, prog):
    for bump in range(255, -1, -1):
        h = hashlib.sha256()
        for s in seeds:
            h.update(s)
        h.update(bytes([bump])); h.update(prog)
        h.update(b"ProgramDerivedAddress")
        out = h.digest()
        if not _on_curve(out):
            return out
    raise ValueError("no PDA bump")

PUMP_PROG = b58dec("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")

CASES = {
    "GPRO":    {"mint": "GcSgbzMvYhz8RXffYZDjUgLafVtYVv9QG2FUoerNpump",
                "mig_ts": 1788283980.0},
    "Erin":    {"mint": "GeR3KJHTc1wRp5v5jMv7DcoSM8A5zAGNknTGbjnpump",
                "mig_ts": 1788282385.0},
    "GROKCAT": {"mint": "2a1hX8xnXMPGt2f6FBvEUQEefk8N7LijnyeLCwehpump",
                "mig_ts": 1788280371.0},
}
V_SOL0_LAM = 30_000_000_000          # 30 SOL virtual offset
V_TOK_DELTA = 279_900_191            # v_tok - r_tok constant offset

# live exit-stack parameters (mirror live_trader.py)
P_FR_TARGET, P_FR_SELL = 1.8, 0.60
P_TRAIL_F = 0.55
P_ABORT15 = (15.0, 1.08)
P_ABORT30 = (30.0, 1.25)
P_TIMESTOP_MIN = 120.0

_rpc_i = 0
def rpc(method, params, tries=6):
    global _rpc_i
    last = None
    for _ in range(tries):
        url = RPCS[_rpc_i % len(RPCS)]
        _rpc_i += 1
        try:
            req = urllib.request.Request(
                url, data=json.dumps({"jsonrpc": "2.0", "id": 1,
                                      "method": method,
                                      "params": params}).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=25) as r:
                out = json.loads(r.read())
            if "error" in out:
                last = out["error"]
                time.sleep(1.6)
                continue
            time.sleep(1.6)   # public RPC spacing
            return out.get("result")
        except Exception as e:
            last = str(e)
            time.sleep(1.6)
    print(f"  rpc {method} failed: {str(last)[:100]}")
    return None

def load_state():
    if STATE_F.exists():
        return json.loads(STATE_F.read_text())
    return {}
def save_state(st):
    STATE_F.write_text(json.dumps(st))

def collect_sigs(addr):
    out, before = [], None
    while True:
        p = [addr, {"limit": 1000}]
        if before:
            p[1]["before"] = before
        r = rpc("getSignaturesForAddress", p)
        if not r:
            break
        out.extend(r)
        if len(r) < 1000:
            break
        before = r[-1]["signature"]
    return out

def curve_deltas(txr, curve_addr, mint):
    """(blockTime, r_sol_lamports_post, r_tok_post, d_sol_lamports)."""
    if not txr or txr.get("meta", {}).get("err"):
        return None
    meta = txr["meta"]
    keys = [k["pubkey"] if isinstance(k, dict) else k
            for k in txr["transaction"]["message"]["accountKeys"]]
    if curve_addr not in keys:
        return None
    i = keys.index(curve_addr)
    pre_l, post_l = meta["preBalances"][i], meta["postBalances"][i]
    def tok(bals):
        for tb in bals or []:
            if tb.get("owner") == curve_addr and tb.get("mint") == mint:
                return float(tb["uiTokenAmount"]["uiAmount"] or 0)
        return None
    t_pre, t_post = tok(meta.get("preTokenBalances")), tok(meta.get("postTokenBalances"))
    if t_post is None:
        return None
    return (txr.get("blockTime"), post_l, t_post, post_l - pre_l)

def px_of(r_sol_lam, r_tok):
    return (r_sol_lam + V_SOL0_LAM) / 1e9 / (r_tok + V_TOK_DELTA)

def score(path):
    """Live exit stack on a birth-time entry."""
    if not path:
        return None
    entry_px = path[0]["px"]
    t_entry = path[0]["t"]
    peak, banked, stake = 1.0, 0.0, 1.0
    freerolled = False
    exit_reason, exit_px, exit_t = None, None, None
    for r in path:
        x = r["px"] / entry_px
        peak = max(peak, x)
        mins = (r["t"] - t_entry) / 60
        if not freerolled and x >= P_FR_TARGET:
            banked += P_FR_SELL * P_FR_TARGET
            stake -= P_FR_SELL
            freerolled = True
            continue
        if freerolled and x <= P_TRAIL_F * peak:
            banked += stake * x
            exit_reason, exit_px, exit_t = "trail", r["px"], r["t"]
            break
        if not freerolled and mins >= P_ABORT15[0] and x < P_ABORT15[1]:
            banked += stake * x
            exit_reason, exit_px, exit_t = "abort15", r["px"], r["t"]
            break
        if not freerolled and mins >= P_ABORT30[0] and x < P_ABORT30[1]:
            banked += stake * x
            exit_reason, exit_px, exit_t = "abort30", r["px"], r["t"]
            break
        if mins >= P_TIMESTOP_MIN:
            banked += stake * x
            exit_reason, exit_px, exit_t = "timestop", r["px"], r["t"]
            break
    if exit_reason is None:
        exit_reason = "open"
        banked += stake * (path[-1]["px"] / entry_px)
        exit_px, exit_t = path[-1]["px"], path[-1]["t"]
    return {"entry_px": entry_px, "entry_t": t_entry,
            "curve_secs": round(path[-1]["t"] - t_entry, 1),
            "peak_x": round(peak, 2), "exit": exit_reason,
            "exit_min": round((exit_t - t_entry) / 60, 2),
            "ret": round(banked - 1.0, 4), "n_ticks": len(path)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=240)
    args = ap.parse_args()
    t_end = time.time() + args.budget
    st = load_state()
    for name, c in CASES.items():
        if time.time() > t_end:
            break
        mint = c["mint"]
        curve = b58enc(pda([b"bonding-curve", b58dec(mint)], PUMP_PROG))
        c["curve"] = curve
        cs = st.setdefault(name, {"sigs": [], "parsed": 0,
                                  "done_sigs": False})
        if not cs["done_sigs"]:
            sigs = collect_sigs(curve)
            if sigs:
                cs["sigs"] = [{"s": s["signature"], "t": s["blockTime"]}
                              for s in sigs]
                cs["done_sigs"] = True
                save_state(st)
                first_t = min(s["t"] for s in cs["sigs"])
                print(f"{name}: {len(sigs)} curve sigs, "
                      f"span {max(s['t'] for s in cs['sigs']) - first_t:.0f}s, "
                      f"mig - first_tx = {c['mig_ts'] - first_t:.0f}s")
        if cs["done_sigs"] and "work" not in cs:
            win = [s["s"] for s in cs["sigs"]
                   if s["t"] <= c["mig_ts"] + 60]
            stride = max(1, len(win) // 4000)
            cs["work"] = win[::stride]
            cs["parsed"] = 0
            save_state(st)
            print(f"{name}: work {len(cs['work'])} ticks (stride {stride})")
        path_f = MON / f"armed_curve_path_{name}.jsonl"
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
                vd = curve_deltas(txr, curve, mint)
                if vd:
                    t, r_sol, r_tok, dq = vd
                    pf.write(json.dumps({
                        "t": t, "sig": sig,
                        "r_sol": round(r_sol / 1e9, 4),
                        "r_tok": round(r_tok, 0),
                        "px": px_of(r_sol, r_tok),
                        "side": "buy" if dq > 0 else
                                ("sell" if dq < 0 else "flat"),
                        "dq_sol": round(dq / 1e9, 4)}) + "\n")
                    n_new += 1
                cs["parsed"] += 1
                if cs["parsed"] % 25 == 0:
                    save_state(st)
                    pf.flush()
        save_state(st)
        print(f"{name}: parsed {cs['parsed']}/{len(cs.get('work') or [])}"
              f" (+{n_new} ticks this run)")

    out = {}
    for name in CASES:
        path_f = MON / f"armed_curve_path_{name}.jsonl"
        if not path_f.exists():
            continue
        path = [json.loads(l) for l in path_f.open()]
        path.sort(key=lambda r: (r["t"], r["sig"]))
        s = score(path)
        if s:
            out[name] = s
            print(f"{name}: curve {s['curve_secs']}s, peak {s['peak_x']}x, "
                  f"exit={s['exit']}@{s['exit_min']}m, ret={s['ret']:+.2%}, "
                  f"ticks={s['n_ticks']}")
    (MON / "armed_curve_score.json").write_text(json.dumps(out, indent=1))
    print("wrote armed_curve_score.json")

if __name__ == "__main__":
    main()
