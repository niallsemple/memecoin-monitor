"""MFG tracker (§56+§56b): capture manufactured launches birth → graduation
→ post-graduation runner/husk.

Runs as the curve-collector automation (~19-min window, every 20 min).

Data path (all verified live 2026-08-29):
- ws1 PumpPortal: subscribeNewToken + subscribeMigration (births/graduations,
  logged raw to curves.jsonl).
- ws2 Helius accountSubscribe. PumpPortal subscribeTokenTrade is PAYWALLED —
  do not use. Two account kinds per token:
  1. PRE-GRAD: bonding-curve account (from create event's bondingCurveKey).
     151 bytes: virtualTokenReserves u64 @8, virtualSolReserves u64 @16,
     complete bool @48, creator 32B @49. vSol delta = buy/sell flow;
     mcap = vSol_lamports * 1e6 / vTok_raw.
  2. POST-GRAD: PumpSwap pool token accounts. Pool discovered via
     getProgramAccounts on AMM pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA
     with memcmp offset 43 = mint (layout: bump@8, index@9, creator@11,
     baseMint@43, quoteMint@75, lpMint@107, poolBaseTA@139, poolQuoteTA@171,
     lpSupply u64 @203). Both token accounts subscribed; SPL amount u64 @64.
     Quote (WSOL) delta = buy(+)/sell(-) flow; pool mcap = q_lamports*1e6/b_raw.
     (The curve account FREEZES at graduation — post-grad runner/husk is only
     measurable on the pool. That was the §56b blind spot.)

LOST vs the paywalled trade feed (honest limits): trader identity (no unique
buyers, no dev-sell flags) — flow is aggregate only. Slot batching can merge
several trades into one notification (accepted approximation).

Snapshots to mfg_tokens.jsonl at +5m/+15m/+60m (all tokens) and +4h/+12h/+24h
(graduated tokens, pool fields); derived trades to mfg_trades.jsonl;
state in mfg_state.json (survives the 1-min inter-run gap).
"""
import base64
import json
import struct
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

MON = Path("/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor")
CURVES = MON / "curves.jsonl"
TRADES = MON / "mfg_trades.jsonl"
SNAPS = MON / "mfg_tokens.jsonl"
STATE = MON / "mfg_state.json"
KEYFILE = MON / "helius_key.txt"
PUMP_WSS = "wss://pumpportal.fun/data-api/real-time"
WINDOW_S = 19 * 60
SEED_MIN = 5.0
MAX_TRACK = 40                          # concurrent curve subscriptions (§66: quota)
MAX_POOL_TRACK = 30                     # graduated tokens pool-tracked (2 subs each)
POOL_QUIET_S = 2 * 3600                 # §56g: recycle pool slots after 2h silence
SNAP_AGES = (300, 900, 3600)            # +5m, +15m, +60m
GRAD_SNAP_AGES = (14400, 43200, 86400)  # +4h, +12h, +24h (graduated only)
TRACK_MAX_AGE = 3600                    # unsubscribe curve after 1h
AMM_PROG = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
WSOL = "So11111111111111111111111111111111111111112"
# §66 fallback: public RPCs when Helius quota is exhausted (429)
PUB_RPCS = ("https://api.mainnet-beta.solana.com",
            "https://solana-rpc.publicnode.com",
            "https://solana.drpc.org")
RPC_KEYS = MON / "rpc_keys.json"  # §79w: owner drops extra keyed endpoints here


def _keyed_rpcs():
    """§79w: extra keyed RPC endpoints (Helius/QuickNode/Alchemy free
    tiers) from rpc_keys.json — {"endpoints": [url, ...]}. Read fresh
    each call so newly dropped keys apply with no restart. Keyed
    endpoints are tried FIRST (they can serve indexed calls like
    getTokenLargestAccounts that public RPCs gate)."""
    try:
        d = json.loads(RPC_KEYS.read_text())
        return [u for u in d.get("endpoints", [])
                if isinstance(u, str) and u.startswith("http")]
    except Exception:
        return []
ALERTS = MON / "mfg_alerts.jsonl"
ALERT_LIQ_MIN = 100.0     # SOL of quote liquidity = deep-pool campaign
ALERT_FLOW_MIN = 3.0      # pool buy/sell SOL ratio
ALERT_BUY_MIN = 20.0      # SOL of pool buy volume (activity floor)
ALERT_BUYS_MIN = 30       # trade-count floor (kicks dust noise out)
ALERT_MAX_AGE = 4 * 3600  # only fresh campaigns ping

# §56e free-roll paper-trader (paper only — no real orders)
PAPER = MON / "mfg_paper_trades.jsonl"
PAPER_A15 = MON / "mfg_paper_trades_a15.jsonl"  # §72: abort-15 shadow
PAPER_H108 = MON / "mfg_paper_trades_h108.jsonl"  # §74: hybrid shadow
PAPER_S = MON / "mfg_paper_trades_s60.jsonl"  # §77: strict-entry shadow (net60/nb20)
PAPER_SNM = MON / "mfg_paper_trades_s60nm5.jsonl"  # §79s: s60 + near-miss abort (5m)
PAPER_SMB = MON / "mfg_paper_trades_s60nm5mb.jsonl"  # §79u: s60nm5 + dust-buy filter (med>=0.25) SHADOW
PAPER_STS = MON / "mfg_paper_trades_s60nm5ts180.jsonl"  # §86a: s60nm5 + 3-min hard time-stop SHADOW
PAPER_SFR = MON / "mfg_paper_trades_s60nm5fr.jsonl"  # §98a: s60nm5 + funded-wallet reject SHADOW
HOLDERS = MON / "mfg_holders.jsonl"  # §79j: top-holder snapshot at each s60 signal
HOLDERS_SEEN = MON / "mfg_holders_seen.json"
P_TARGET, P_SELL = 1.5, 0.75    # free-roll: sell 75% at 1.5x entry
P_TRAIL = 0.5                   # trailing stop: exit below 50% of post-entry peak
P_TS_MIN = 120                  # time-stop: dump unpumped campaign after 120 min
P_ABORT_MIN, P_ABORT_R = 30, 1.15   # §59: abort if below 1.15x after 30 min
P_NET_MIN, P_NB_MIN, P_FLOW_MIN = 25.0, 10, 2.0   # E25 early entry trigger


def paper_score(abort_min=None, out_path=None, stage1=None,
                net_min=None, nb_min=None, flow_min=None, nm_min=None,
                med_min=None, ts_min=None, funded_reject=False):
    """Replay pool trades with the §56e exit stack; write paper file.
    Fully self-contained and fail-safe: returns {} on any error.
    §72: abort_min/out_path allow shadow variants (a15) alongside the
    pre-registered a30 gate. §74: stage1=(minute, threshold) adds a
    two-stage abort — dead campaigns out early, slow grinders keep the
    full window. §77: net_min/nb_min/flow_min allow strict-entry shadow
    variants (net60/nb20 = the §76 positive-expectancy region).
    §79s: nm_min adds a near-miss abort — once 1.30x is touched without
    freerolling, exit at next trade if 1.5x is not reached in nm_min
    minutes (dump-in-progress signature, §79r bimodal peak gap).
    §79u: med_min skips entries whose median buy size at the trigger is
    below it — dust-buy fake breadth (grind-rug signature, B9tN 0.248
    SOL vs runners >=1.36). SHADOW only, not an amendment.
    §86a: ts_min overrides P_TS_MIN — bleeder dumps land at entry
    +3.6-13.8m on positions that never freeroll; forward-test whether a
    3-min hard stop captures the honest +1.0%/trade backtest."""
    import collections
    am = abort_min if abort_min is not None else P_ABORT_MIN
    out = out_path or PAPER
    net_min = net_min if net_min is not None else P_NET_MIN
    nb_min = nb_min if nb_min is not None else P_NB_MIN
    flow_min = flow_min if flow_min is not None else P_FLOW_MIN
    tsm = ts_min if ts_min is not None else P_TS_MIN
    tr = collections.defaultdict(list)
    try:
        with TRADES.open() as f:
            for line in f:
                try:
                    x = json.loads(line)
                except Exception:
                    continue
                if (x.get("venue") != "pool" or not x.get("t")
                        or x.get("mcap_sol") is None):
                    continue
                tr[x["mint"]].append(x)
    except Exception:
        return {}
    if funded_reject:
        # §98a: skip entries whose CREATOR is a tripwire-flagged funded
        # wallet (mfg_funding.jsonl fresh_wallet set). The only known
        # entry-time bleeder signal; §85/§89/§93 proved tape can't. The
        # skip is evaluated with the funding data available NOW — the
        # forward sample stays honest because alerts accrue before the
        # funded wallet's first launch reaches the gate.
        try:
            # §100: reject set = funding recipients UNION the chain
            # wallets themselves — 9awYaD's creator IS the ELON seeder
            # (FLPen3) and 84X4w5's creator IS the capital holder
            # (6fy6iH). 2 of 4 forward bleeders were tree-member launches.
            funded = set(CHAIN_WATCH)
            if FUNDING.exists():
                for line in FUNDING.open():
                    try:
                        fw = json.loads(line).get("fresh_wallet")
                        if fw:
                            funded.add(fw)
                    except Exception:
                        continue
            creators = {}
            if SNAPS.exists():
                for line in SNAPS.open():
                    try:
                        s = json.loads(line)
                        if s.get("mint") and s.get("creator"):
                            creators.setdefault(s["mint"], s["creator"])
                    except Exception:
                        continue
            # §105: self-blacklist — creators of past closed bleeders
            # (ret <= -30%) join the reject set. Timestamped: a creator
            # only rejects mints whose FIRST trade is after the
            # blacklist entry, so historical rows stay lookahead-free.
            bl = {}
            if BLACKLIST.exists():
                for line in BLACKLIST.open():
                    try:
                        b = json.loads(line)
                        c, t = b.get("creator"), b.get("t")
                        if c and t:
                            bl[c] = min(t, bl.get(c, t))
                    except Exception:
                        continue
            for m in list(tr.keys()):
                c = creators.get(m)
                if c in funded:
                    del tr[m]
                elif c in bl and tr[m] and bl[c] < min(x["t"] for x in tr[m]):
                    del tr[m]
        except Exception:
            pass
    positions = []
    for m, xs in tr.items():
        if len(xs) < 50:
            continue
        xs.sort(key=lambda x: x["t"])
        nb = ns = 0
        bs = ss = 0.0
        ti = None
        for i, x in enumerate(xs):
            if x.get("side") == "buy":
                nb += 1
                bs += x.get("sol") or 0
            else:
                ns += 1
                ss += x.get("sol") or 0
            if ((bs - ss) >= net_min and nb >= nb_min
                    and nb / max(ns, 1) >= flow_min):
                ti = i
                break
        if ti is None:
            continue
        if med_min is not None:
            # §79u: dust-buy filter — median buy SOL up to the trigger;
            # grind-rugs fake breadth with hundreds of tiny sybil buys
            # (B9tN med 0.248 vs runners >=1.36). Skip dust entries.
            import statistics as _st
            _buys = [y.get("sol") or 0 for y in xs[:ti + 1]
                     if y.get("side") == "buy"]
            if not _buys or _st.median(_buys) < med_min:
                continue
        # §74b: realistic fill — enter at the next trade after the trigger
        # (you react to the signal; you can't buy the trade that made it).
        if ti + 1 >= len(xs):
            continue
        emc = xs[ti + 1]["mcap_sol"]
        t0 = xs[ti + 1]["t"]
        if emc <= 0:
            continue
        # §59: realistic next-trade fills + abort rule (<1.15x after 30 min)
        proceeds = 0.0
        pos = 1.0
        peak = 1.0
        fr = False
        reason = None
        nm_touch_t = None
        body = xs[ti + 2:]

        def _price_at(deadline_s):
            # §99: honest clock-based fill — last trade at/before the
            # deadline (a live poller marks every ~15s even on quiet pools)
            p = emc
            for y in body:
                if y["t"] - t0 > deadline_s:
                    break
                p = y["mcap_sol"]
            return p / emc

        for j, x in enumerate(body):
            r = x["mcap_sol"] / emc
            peak = max(peak, r)
            mins = (x["t"] - t0) / 60

            def fill(trig, _j=j):
                return (body[_j + 1]["mcap_sol"] / emc
                        if _j + 1 < len(body) else trig)

            if not fr and r >= P_TARGET:
                proceeds += P_SELL * fill(P_TARGET)
                pos -= P_SELL
                fr = True
            if nm_min and not fr:
                if r >= 1.30 and nm_touch_t is None:
                    nm_touch_t = x["t"]
                if (nm_touch_t is not None and r < P_TARGET
                        and (x["t"] - nm_touch_t) >= nm_min * 60
                        and pos > 0):
                    # §106: clock exits fill at the price AT the deadline
                    proceeds += pos * _price_at(nm_touch_t - t0 + nm_min * 60)
                    pos = 0
                    reason = "nm_abort"
                    break
            if (stage1 and not fr and mins >= stage1[0]
                    and r < stage1[1] and pos > 0):
                proceeds += pos * _price_at(stage1[0] * 60)
                pos = 0
                reason = "abort15"
                break
            if not fr and mins >= am and r < P_ABORT_R and pos > 0:
                proceeds += pos * _price_at(am * 60)
                pos = 0
                reason = "abort"
                break
            if r <= P_TRAIL * peak and pos > 0:
                proceeds += pos * fill(r)
                pos = 0
                reason = "trail"
                break
            if not fr and mins >= tsm:
                # §99: fill at the price AT the deadline, not the next
                # print — on quiet pools the next print can be a
                # post-collapse zero (9orw5y bled 30 min after going quiet)
                proceeds += pos * _price_at(tsm * 60)
                pos = 0
                reason = "timestop"
                break
        if pos > 0:
            # §70: mark-to-deadline — a live poller sees balance-derived
            # mcap every ~15s even on quiet pools, so deadline exits fill
            # at the price observed AT the deadline (last trade at/before
            # it), not at the final mark of a pool that rugged later.
            mins_now = (time.time() - t0) / 60

            if stage1 and not fr and mins_now >= stage1[0]:
                r1 = _price_at(stage1[0] * 60)
                if r1 < stage1[1]:
                    proceeds += pos * r1
                    pos = 0
                    reason = "abort15"
            if pos > 0 and not fr and mins_now >= am:
                r_a = _price_at(am * 60)
                if r_a < P_ABORT_R:
                    proceeds += pos * r_a
                    pos = 0
                    reason = "abort"
            if pos > 0 and not fr and mins_now >= tsm:
                r_t = _price_at(tsm * 60)
                proceeds += pos * r_t
                pos = 0
                reason = "timestop"
        if pos > 0:
            total = proceeds + pos * (xs[-1]["mcap_sol"] / emc)
            status = "open"
        else:
            total = proceeds
            status = "closed"
        positions.append({"mint": m, "entry_t": t0, "entry_mcap": emc,
                          "freerolled": fr, "peak": round(peak, 3),
                          "status": status, "exit_reason": reason,
                          "ret": round(total - 1, 4),
                          "last_t": xs[-1]["t"], "n_trades": len(xs)})
    try:
        with out.open("w") as f:
            for r in positions:
                f.write(json.dumps(r) + "\n")
    except Exception:
        pass
    closed = [r["ret"] for r in positions if r["status"] == "closed"]
    return {"paper_positions": len(positions),
            "paper_closed": len(closed),
            "paper_open": len(positions) - len(closed),
            "paper_exp": round(sum(closed) / len(closed), 4) if closed else None,
            "paper_wins": sum(1 for v in closed if v > 0)}


def holder_snapshots(rpc_fn):
    """§79j: snapshot getTokenLargestAccounts for fresh s60 entries so
    forward rugs/winners teach the holder-concentration discriminator
    (supported tokens distribute the 74% pre-load; harvest tokens keep
    it concentrated). Fail-safe; appends to HOLDERS, tracks done mints."""
    try:
        seen = set()
        if HOLDERS_SEEN.exists():
            seen = set(json.loads(HOLDERS_SEEN.read_text()))
        now = time.time()
        fresh = []
        with PAPER_S.open() as f:
            for line in f:
                r = json.loads(line)
                if (r.get("mint") and r["mint"] not in seen
                        and now - r.get("entry_t", 0) < 5400):
                    fresh.append(r)
        for r in fresh[:4]:
            res = rpc_fn("getTokenLargestAccounts", [r["mint"]]).get("result")
            vals = (res or {}).get("value") or []
            if not vals:
                continue  # §79k2: RPC starved — retry next run, don't mark seen
            with HOLDERS.open("a") as f:
                f.write(json.dumps({
                    "t": now, "mint": r["mint"], "entry_t": r["entry_t"],
                    "holders": [{"a": v.get("address"),
                                 "amt": v.get("uiAmount")}
                                for v in vals[:20]]}) + "\n")
            seen.add(r["mint"])
        HOLDERS_SEEN.write_text(json.dumps(sorted(seen)))
    except Exception:
        pass


SIGNERS = MON / "mfg_signers.jsonl"      # §81b: entry-window signer concentration
SIGNERS_SEEN = MON / "mfg_signers_seen.json"
FUNDING = MON / "mfg_funding.jsonl"      # §89: treasury-chain seed funding alerts
FUNDING_SEEN = MON / "mfg_funding_seen.json"
BLACKLIST = MON / "mfg_creator_blacklist.jsonl"  # §105: bleeder creators
CHAIN_WATCH = (  # §89 layering chain — campaigns are funded from here
    "CmdxEBCubitREoJTwZxB6jsPR6mawJPcva9aYfFpAEMk",   # treasury
    "AdiJ1C5PHNYoZc8JZ8GvEXFbWRrQvzsUc6niUWRTYXcB",   # layer-1 hop
    "9GQvBGZqM7Du4gAjQQiGRyzL8GpFCiJCGpE2cucFZayh",   # layer-2 hop
    # §96: second tree (9awYaD/ELON bleeder) — seeder, hop, staging
    "FLPen3FKHgjW9UHB7ERxPe5FQYAud49oVTwFviWLoa2F",   # ELON seeder (emptied; may be reused)
    "5ARipQXUFP13QzHau8moMxpvLzXwMLgLgpzjpbsrUzTa",   # distribution hub
    "6fy6iHxyPuB4DsMHCRkZCtZEN7LWX7XbEeAqQBrEuj7R",   # current capital holder (626.6 SOL)
    "2CBKgWWBFtF2R4vyZdFV6MDdZS3Rt4CoyAz2aXDGALiu",   # staging
    "F7FKWVcSsWcBSTkjrz9drwy9QM9D15cPcztj9gQj1cd9",   # staging
    "4Lr8dectLMbyfWAAqMwdAEa8Zc3jHnevKTcm6NC72ytK",   # staging (210 SOL)
    "3CFkWSsx5zpaxGhbmjZsn2ScYKjfkgdnCS3nFzjMWMDx",   # staging (70 SOL)
)


def signer_snapshots(rpc_fn, tokens):
    """§81b: for fresh s60nm5 entries, reconstruct WHO traded the bonding
    curve around entry — the tape-native insider metric after §81 showed
    snapshot aggregates can't separate the mega-dump class and the mfg
    ingest derives trades from balance deltas (no trader identity).

    Per new scorer entry: getSignaturesForAddress(curve) (page back once
    toward birth), getTransaction each sig (jsonParsed), attribute
    |feePayer balance delta| as that signer's size. Appends one row per
    mint: unique signers, top-1/top-5 share of moved SOL. Holder-gate
    proxy until keyed RPC unlocks getTokenLargestAccounts (§79x).
    Fail-safe; capped 2 mints/run, 40 txs each; retries unmarked mints."""
    try:
        seen = set()
        if SIGNERS_SEEN.exists():
            seen = set(json.loads(SIGNERS_SEEN.read_text()))
        now = time.time()
        fresh = []
        with PAPER_SNM.open() as f:
            for line in f:
                r = json.loads(line)
                if (r.get("mint") and r["mint"] not in seen
                        and now - r.get("entry_t", 0) < 7200):
                    fresh.append(r)
        for r in fresh[:2]:
            mint = r["mint"]
            t = tokens.get(mint) or {}
            curve = t.get("curve")
            if not curve:
                continue  # state may have aged out; retry next run
            sigs = []
            res = rpc_fn("getSignaturesForAddress",
                         [curve, {"limit": 80}]).get("result") or []
            sigs = [s.get("signature") for s in res if s.get("signature")]
            if len(res) == 80 and sigs:
                res2 = rpc_fn("getSignaturesForAddress",
                              [curve, {"limit": 80,
                                       "before": sigs[-1]}]).get("result") or []
                sigs += [s.get("signature") for s in res2
                         if s.get("signature")]
            sigs = sigs[-24:]  # oldest end = birth window (§84: 40 429'd)
            moved = {}
            parsed = 0
            for sig in sigs:
                tx = rpc_fn("getTransaction",
                            [sig, {"encoding": "jsonParsed",
                                   "maxSupportedTransactionVersion": 0}]
                            ).get("result")
                time.sleep(0.8)  # §84: free-tier getTransaction rate limit
                if not tx:
                    continue
                try:
                    msg = tx["transaction"]["message"]
                    keys = msg.get("accountKeys") or []
                    k0 = keys[0]
                    signer = k0.get("pubkey") if isinstance(k0, dict) else k0
                    meta = tx.get("meta") or {}
                    pre = (meta.get("preBalances") or [0])[0]
                    post = (meta.get("postBalances") or [0])[0]
                    sol = abs(post - pre) / 1e9
                    if signer and sol > 0.001:
                        moved[signer] = moved.get(signer, 0.0) + sol
                        parsed += 1
                except Exception:
                    continue
            if not parsed:
                continue  # RPC starved — retry next run, don't mark seen
            tot = sum(moved.values()) or 1.0
            top = sorted(moved.items(), key=lambda kv: -kv[1])
            with SIGNERS.open("a") as f:
                f.write(json.dumps({
                    "t": now, "mint": mint, "entry_t": r["entry_t"],
                    "n_tx": len(sigs), "parsed": parsed,
                    "unique_signers": len(moved),
                    "top1_sol": round(top[0][1], 3),
                    "top1_share": round(top[0][1] / tot, 4),
                    "top1": top[0][0],
                    "top5_share": round(sum(v for _, v in top[:5]) / tot, 4),
                    "moved_sol": round(tot, 3)}) + "\n")
            seen.add(mint)
            time.sleep(1)  # be polite to free RPC tiers
        SIGNERS_SEEN.write_text(json.dumps(sorted(seen)))
    except Exception:
        pass


def treasury_watch(rpc_fn):
    """§89: bleeder campaigns are FUNDED from the layering chain. Watch
    CHAIN_WATCH wallets for outbound seed-sized transfers (80-95 SOL —
    the §85 instant-fill amount) to fresh wallets; a recipient's next
    launch is bleeder-class BEFORE it reaches any gate. Appends
    {t, chain, fresh_wallet, sol, sig} to FUNDING; per-wallet last-seen
    sig in FUNDING_SEEN. Fail-safe; caps parse at 4 txs/wallet/run."""
    try:
        seen = {}
        if FUNDING_SEEN.exists():
            seen = json.loads(FUNDING_SEEN.read_text())
        for w in CHAIN_WATCH:
            last = seen.get(w)
            res = rpc_fn("getSignaturesForAddress",
                         [w, {"limit": 12}]).get("result") or []
            new = []
            for s in res:
                if s.get("signature") and s["signature"] == last:
                    break
                new.append(s)
            for s in list(reversed(new))[:4]:  # oldest first, parse-capped
                sig = s.get("signature")
                if not sig:
                    continue
                tx = rpc_fn("getTransaction",
                            [sig, {"encoding": "jsonParsed",
                                   "maxSupportedTransactionVersion": 0}]
                            ).get("result")
                time.sleep(0.8)  # §84a: free-tier rate limit
                if not tx:
                    continue
                meta = tx.get("meta") or {}
                msg = (tx.get("transaction") or {}).get("message") or {}
                keys = msg.get("accountKeys") or []
                pre = meta.get("preBalances") or []
                post = meta.get("postBalances") or []
                for i in range(min(len(pre), len(post), len(keys))):
                    d = (post[i] - pre[i]) / 1e9
                    k = keys[i]
                    k = k.get("pubkey") if isinstance(k, dict) else k
                    # §96: band widened 60-700 — second tree arms via
                    # staging splits (70/210/334) before the 86 SOL edge
                    if k and k not in CHAIN_WATCH and 60.0 <= d <= 700.0:
                        with FUNDING.open("a") as f:
                            f.write(json.dumps({
                                "t": s.get("blockTime") or time.time(),
                                "chain": w, "fresh_wallet": k,
                                "sol": round(d, 3), "sig": sig}) + "\n")
            if res and res[0].get("signature"):
                seen[w] = res[0]["signature"]
        FUNDING_SEEN.write_text(json.dumps(seen))
    except Exception:
        pass


def _load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:
            pass
    return {}


def _save_state(tokens):
    now = time.time()
    keep = {}
    for m, t in tokens.items():
        done = len(set(t["snapped"]) & set(SNAP_AGES)) >= len(SNAP_AGES) and (
            not t.get("grad_ts")
            or len(set(t["snapped"]) & set(GRAD_SNAP_AGES)) >= len(GRAD_SNAP_AGES))
        if now - t["birth_ts"] < 26 * 3600 or not done:
            keep[m] = t
    STATE.write_text(json.dumps(keep))
    return keep


def _decode_curve(b64):
    """Return (vTok_raw, vSol_lamports, complete) or None."""
    try:
        raw = base64.b64decode(b64)
        if len(raw) < 49:
            return None
        vtok, vsol = struct.unpack("<QQ", raw[8:24])
        return vtok, vsol, raw[48] != 0
    except Exception:
        return None


def _decode_spl_amount(b64):
    """SPL token account: amount u64 @64. Return raw amount or None."""
    try:
        raw = base64.b64decode(b64)
        if len(raw) < 72:
            return None
        return struct.unpack("<Q", raw[64:72])[0]
    except Exception:
        return None


def _b58e(b):
    al = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = int.from_bytes(b, "big")
    s = ""
    while n:
        n, m = divmod(n, 58)
        s = al[m] + s
    return "1" * (len(b) - len(b.lstrip(b"\x00"))) + s


def run(ctx):
    import websocket
    helius_key = KEYFILE.read_text().strip()
    helius_wss = f"wss://mainnet.helius-rpc.com/?api-key={helius_key}"
    helius_rpc = f"https://mainnet.helius-rpc.com/?api-key={helius_key}"

    rpc_state = {"i": 0}

    def rpc(method, params):
        """Helius first; on any failure rotate through PUB_RPCS (§66b).
        Returns {'result': None} when every endpoint is down — callers
        already tolerate that via r.get('result') and try/except."""
        body = json.dumps({"jsonrpc": "2.0", "id": 1,
                           "method": method, "params": params}).encode()
        hdrs = {"Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Macintosh; mfg/1.0)"}
        urls = _keyed_rpcs() + [helius_rpc] + list(PUB_RPCS)
        for k in range(len(urls)):
            url = urls[0] if k == 0 else urls[1:][(rpc_state["i"] + k - 1)
                                                  % (len(urls) - 1)]
            try:
                req = urllib.request.Request(url, data=body, headers=hdrs)
                return json.loads(urllib.request.urlopen(req, timeout=15).read())
            except Exception:
                if k > 0:
                    rpc_state["i"] += 1
        return {"result": None}

    def discover_pool(mint):
        """Return {'pool','pbt','pqt'} for the mint's WSOL pool, else None.

        §66: GT-first (free) to avoid getProgramAccounts credit burn that
        exhausted the Helius quota (429 'max usage reached', 2026-08-30).
        GT gives the pumpswap pool address; ONE getAccountInfo parses the
        vaults (layout: quoteMint@75, poolBaseTA@139, poolQuoteTA@171).
        Falls back to the getProgramAccounts scan if GT is blind.
        """
        try:
            url = ("https://api.geckoterminal.com/api/v2/networks/solana/"
                   f"tokens/{mint}/pools")
            req = urllib.request.Request(url, headers={"User-Agent": "mfg/1.0"})
            d = json.loads(urllib.request.urlopen(req, timeout=15).read())
            addr = None
            for p in d.get("data") or []:
                dex = (p.get("relationships") or {}).get("dex", {}).get("data", {}).get("id")
                if dex == "pumpswap":
                    addr = (p.get("attributes") or {}).get("address")
                    break
            if addr:
                r = rpc("getAccountInfo", [addr, {"encoding": "base64"}])
                v = (r.get("result") or {}).get("value")
                if v:
                    raw = base64.b64decode(v["data"][0])
                    if len(raw) >= 203 and _b58e(raw[75:107]) == WSOL:
                        return {"pool": addr,
                                "pbt": _b58e(raw[139:171]),
                                "pqt": _b58e(raw[171:203])}
        except Exception:
            pass
        try:
            r = rpc("getProgramAccounts", [AMM_PROG, {
                "encoding": "base64",
                "filters": [{"memcmp": {"offset": 43, "bytes": mint}}]}])
            for a in r.get("result") or []:
                raw = base64.b64decode(a["account"]["data"][0])
                if len(raw) < 203 or _b58e(raw[75:107]) != WSOL:
                    continue
                return {"pool": a["pubkey"],
                        "pbt": _b58e(raw[139:171]),
                        "pqt": _b58e(raw[171:203])}
        except Exception:
            pass
        return None

    def _liq_update(t):
        if t.get("pool_last_q") is None:
            return
        liq = round(t["pool_last_q"] / 1e9, 4)
        t["pool_liq_sol"] = liq
        t["pool_liq_min"] = liq if t.get("pool_liq_min") is None else min(t["pool_liq_min"], liq)
        t["pool_liq_max"] = liq if t.get("pool_liq_max") is None else max(t["pool_liq_max"], liq)

    now0 = time.time()
    deadline = now0 + WINDOW_S
    tokens = _load_state()
    # migrate legacy state entries forward
    for t in tokens.values():
        t.setdefault("curve", None)
        t.setdefault("notifs", 0)
        t.setdefault("last_vsol", None)
        t.setdefault("last_mcap_sol", None)
        t.setdefault("snapped", [])
        t.setdefault("pool", None)          # {'pool','pbt','pqt'} once found
        t.setdefault("pool_try_ts", 0)      # last discovery attempt
        t.setdefault("pool_buys", 0)
        t.setdefault("pool_sells", 0)
        t.setdefault("pool_buy_sol", 0.0)
        t.setdefault("pool_sell_sol", 0.0)
        t.setdefault("pool_notifs", 0)
        t.setdefault("pool_last_q", None)   # quote (WSOL) lamports
        t.setdefault("pool_last_b", None)   # base raw units
        t.setdefault("pool_mcap", None)
        t.setdefault("pool_liq_sol", None)  # quote balance in SOL (pool depth)
        t.setdefault("pool_liq_min", None)  # drain detection: min/max since grad
        t.setdefault("pool_liq_max", None)
    stats = {"births": 0, "big_seeds": 0, "new_tracks": 0, "trades": 0,
             "migrations": 0, "complete_flags": 0, "snaps": 0,
             "curve_subs": 0, "helius_err": 0, "unsubs": 0,
             "pools_found": 0, "pool_subs": 0, "pool_trades": 0, "alerts": 0}
    alerted = set()
    if ALERTS.exists():
        for line in ALERTS.read_text().splitlines():
            try:
                alerted.add(json.loads(line)["mint"])
            except Exception:
                pass
    LK = threading.Lock()
    stop = threading.Event()

    # ---- Helius subscription bookkeeping ----
    hws_ref = {"ws": None, "open": False}
    req_seq = {"n": 0}
    pending = {}          # req_id -> (mint, kind, address)
    subs = {}             # sub_id -> (mint, kind)
    mint_sub = {}         # mint -> {kind: sub_id}
    sub_queue = []        # (mint, kind, address, rid) waiting for ws open

    def helius_send(obj):
        ws = hws_ref["ws"]
        if ws and hws_ref["open"]:
            try:
                ws.send(json.dumps(obj))
                return True
            except Exception:
                return False
        return False

    def subscribe_account(mint, kind, address):
        if not address:
            return
        with LK:
            if kind in mint_sub.get(mint, {}):
                return
            req_seq["n"] += 1
            rid = req_seq["n"]
            pending[rid] = (mint, kind, address)
        req = {"jsonrpc": "2.0", "id": rid, "method": "accountSubscribe",
               "params": [address, {"encoding": "base64",
                                    "commitment": "processed"}]}
        if not helius_send(req):
            with LK:
                sub_queue.append((mint, kind, address, rid))

    def unsubscribe_mint(mint, kinds=("curve", "pool_q", "pool_b")):
        with LK:
            entry = mint_sub.get(mint, {})
            sids = [(k, entry.pop(k, None)) for k in kinds]
            if not entry:
                mint_sub.pop(mint, None)
            for k, sid in sids:
                if sid is not None:
                    subs.pop(sid, None)
        for k, sid in sids:
            if sid is not None:
                req_seq["n"] += 1
                helius_send({"jsonrpc": "2.0", "id": req_seq["n"],
                             "method": "accountUnsubscribe", "params": [sid]})
                stats["unsubs"] += 1

    # ---- token bookkeeping ----
    def new_token(mint, d):
        tokens[mint] = {
            "birth_ts": d.get("_ts") or time.time(),
            "seed": d.get("solAmount") or 0,
            "creator": d.get("traderPublicKey"),
            "name": d.get("name"), "symbol": d.get("symbol"),
            "curve": d.get("bondingCurveKey"),
            "mcap_birth_sol": d.get("marketCapSol"),
            "grad_ts": None, "buys": 0, "sells": 0,
            "buy_sol": 0.0, "sell_sol": 0.0, "notifs": 0,
            "last_vsol": None, "last_mcap_sol": None, "snapped": [],
            "pool": None, "pool_try_ts": 0,
            "pool_buys": 0, "pool_sells": 0,
            "pool_buy_sol": 0.0, "pool_sell_sol": 0.0, "pool_notifs": 0,
            "pool_last_q": None, "pool_last_b": None, "pool_mcap": None,
            "pool_liq_sol": None, "pool_liq_min": None, "pool_liq_max": None,
        }

    def subscribe_pool(mint, t):
        p = t.get("pool")
        if p:
            subscribe_account(mint, "pool_q", p["pqt"])
            subscribe_account(mint, "pool_b", p["pbt"])

    # ---- Helius ws thread ----
    def helius_on_open(ws):
        hws_ref["open"] = True
        with LK:
            queued = list(sub_queue)
            sub_queue.clear()
            warm_c = [(m, t["curve"]) for m, t in tokens.items()
                      if t.get("curve") and "curve" not in mint_sub.get(m, {})
                      and time.time() - t["birth_ts"] < TRACK_MAX_AGE]
            warm_p = [(m, t) for m, t in tokens.items()
                      if t.get("pool") and not t.get("pool_done")
                      and time.time() - t["birth_ts"] < 26 * 3600]
        for mint, kind, address, rid in queued:
            helius_send({"jsonrpc": "2.0", "id": rid, "method": "accountSubscribe",
                         "params": [address, {"encoding": "base64",
                                              "commitment": "processed"}]})
        for mint, curve in warm_c[:MAX_TRACK]:
            subscribe_account(mint, "curve", curve)
        for mint, t in warm_p[:MAX_POOL_TRACK]:
            subscribe_pool(mint, t)

    def helius_on_message(ws, msg):
        try:
            d = json.loads(msg)
        except Exception:
            return
        if "error" in d:
            stats["helius_err"] += 1
            with LK:
                pending.pop(d.get("id"), None)
            return
        rid = d.get("id")
        if rid is not None and "result" in d:
            with LK:
                got = pending.pop(rid, None)
                if got:
                    mint, kind, _addr = got
                    subs[d["result"]] = (mint, kind)
                    mint_sub.setdefault(mint, {})[kind] = d["result"]
                    stats["curve_subs" if kind == "curve" else "pool_subs"] += 1
            return
        if d.get("method") != "accountNotification":
            return
        try:
            sid = d["params"]["subscription"]
            val = d["params"]["result"]["value"]
            data = val.get("data")
            b64 = data[0] if isinstance(data, list) else data
        except Exception:
            return
        with LK:
            got = subs.get(sid)
            if not got or got[0] not in tokens:
                return
            mint, kind = got
            t = tokens[mint]
            now = time.time()

            if kind == "curve":
                dec = _decode_curve(b64)
                if dec is None:
                    return
                vtok, vsol, complete = dec
                t["notifs"] += 1
                if vtok:
                    t["last_mcap_sol"] = round(vsol * 1e6 / vtok, 4)
                if complete and not t["grad_ts"]:
                    t["grad_ts"] = now
                    stats["complete_flags"] += 1
                if t["last_vsol"] is None:
                    t["last_vsol"] = vsol
                    return
                dv = vsol - t["last_vsol"]
                t["last_vsol"] = vsol
                if dv == 0:
                    return
                sol = abs(dv) / 1e9
                side = "buy" if dv > 0 else "sell"
                if dv > 0:
                    t["buys"] += 1
                    t["buy_sol"] += sol
                else:
                    t["sells"] += 1
                    t["sell_sol"] += sol
                stats["trades"] += 1
                rec = {"t": now, "mint": mint, "venue": "curve", "side": side,
                       "sol": round(sol, 6), "mcap_sol": t["last_mcap_sol"]}

            else:  # pool token accounts (SPL amount @64)
                amt = _decode_spl_amount(b64)
                if amt is None:
                    return
                t["pool_notifs"] += 1
                t["pool_last_ts"] = now
                if kind == "pool_b":
                    t["pool_last_b"] = amt
                else:
                    prev = t["pool_last_q"]
                    t["pool_last_q"] = amt
                    _liq_update(t)
                if t["pool_last_b"] and t["pool_last_q"] is not None:
                    t["pool_mcap"] = round(t["pool_last_q"] * 1e6
                                           / t["pool_last_b"], 4)
                if kind == "pool_b" or prev is None:
                    return  # trades counted on quote (WSOL) leg only
                dv = amt - prev
                if dv == 0:
                    return
                sol = abs(dv) / 1e9
                side = "buy" if dv > 0 else "sell"  # WSOL in = buy, out = sell
                if dv > 0:
                    t["pool_buys"] += 1
                    t["pool_buy_sol"] += sol
                else:
                    t["pool_sells"] += 1
                    t["pool_sell_sol"] += sol
                stats["pool_trades"] += 1
                rec = {"t": now, "mint": mint, "venue": "pool", "side": side,
                       "sol": round(sol, 6), "mcap_sol": t["pool_mcap"]}
        with TRADES.open("a") as f:
            f.write(json.dumps(rec) + "\n")

    def helius_loop():
        fails = {"n": 0}
        while not stop.is_set():
            ws = websocket.WebSocketApp(
                helius_wss, on_open=helius_on_open,
                on_message=helius_on_message,
                on_error=lambda w, e: _helius_err(e),
                on_close=lambda w, *a: hws_ref.update(open=False))
            hws_ref["ws"] = ws
            try:
                ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception:
                pass
            hws_ref["open"] = False
            if not stop.is_set():
                # §66: exponential backoff — a 429 handshake means quota
                # exhaustion; hammering every 3s for 19 min made it worse.
                fails["n"] += 1
                time.sleep(min(300, 3 * 2 ** min(fails["n"], 7)))

    def _helius_err(e):
        stats["helius_err"] += 1
        print(f"helius ws error: {str(e)[:120]}")

    # ---- PumpPortal ws (births + migrations) ----
    def pump_on_message(ws, msg):
        try:
            d = json.loads(msg)
        except Exception:
            return
        if not isinstance(d, dict):
            return
        d["_ts"] = time.time()
        tt = d.get("txType") or ""
        mint = d.get("mint")
        if tt == "create":
            stats["births"] += 1
            with CURVES.open("a") as f:
                f.write(json.dumps(d) + "\n")
            seed = d.get("solAmount") or 0
            if seed >= SEED_MIN and mint:
                with LK:
                    fresh = mint not in tokens
                    n_open = sum(1 for t in tokens.values()
                                 if time.time() - t["birth_ts"] < TRACK_MAX_AGE)
                    if fresh and n_open < MAX_TRACK:
                        new_token(mint, d)
                        stats["big_seeds"] += 1
                        stats["new_tracks"] += 1
                        curve = d.get("bondingCurveKey")
                    else:
                        curve = None
                if curve:
                    subscribe_account(mint, "curve", curve)
                    if not hws_ref["open"]:
                        # §67: Helius down — get curve trades from pumpportal
                        try:
                            ws.send(json.dumps({"method": "subscribeTokenTrade",
                                                "keys": [mint]}))
                        except Exception:
                            pass
        elif tt == "migrate":
            stats["migrations"] += 1
            with CURVES.open("a") as f:
                f.write(json.dumps(d) + "\n")
            with LK:
                if mint in tokens and not tokens[mint]["grad_ts"]:
                    tokens[mint]["grad_ts"] = d["_ts"]
        elif tt in ("buy", "sell") and mint and not hws_ref["open"]:
            # §67: Helius down — pumpportal trade feed replaces curve deltas
            try:
                sol = float(d.get("solAmount") or 0)
            except Exception:
                sol = 0.0
            try:
                mc = float(d.get("marketCapSol") or 0)
            except Exception:
                mc = 0.0
            rec = None
            with LK:
                t = tokens.get(mint)
                if t and time.time() - t["birth_ts"] < TRACK_MAX_AGE:
                    t["notifs"] += 1
                    if mc:
                        t["last_mcap_sol"] = mc
                    if tt == "buy":
                        t["buys"] += 1
                        t["buy_sol"] += sol
                    else:
                        t["sells"] += 1
                        t["sell_sol"] += sol
                    stats["trades"] += 1
                    rec = {"t": d["_ts"], "mint": mint, "venue": "curve",
                           "side": tt, "sol": round(sol, 6),
                           "mcap_sol": t["last_mcap_sol"]}
            if rec:
                with TRADES.open("a") as f:
                    f.write(json.dumps(rec) + "\n")
        if time.time() > deadline:
            try:
                ws.close()
            except Exception:
                pass

    def pump_on_open(ws):
        ws.send(json.dumps({"method": "subscribeNewToken"}))
        ws.send(json.dumps({"method": "subscribeMigration"}))
        if not hws_ref["open"]:
            # §67: re-arm curve-trade fallback for live tracked mints
            with LK:
                keys = [m for m, t in tokens.items()
                        if time.time() - t["birth_ts"] < TRACK_MAX_AGE]
            if keys:
                try:
                    ws.send(json.dumps({"method": "subscribeTokenTrade",
                                        "keys": keys}))
                except Exception:
                    pass

    # ---- snapshot / pool-discovery / unsubscriber thread ----
    def snapshot_loop():
        while not stop.is_set():
            now = time.time()
            # 1) pool discovery for freshly graduated tokens (HTTP, ~1s)
            with LK:
                need = [(m, t) for m, t in tokens.items()
                        if t.get("grad_ts") and not t.get("pool")
                        and now - t.get("pool_try_ts", 0) > 60
                        and now - t["birth_ts"] < 26 * 3600]
                # §66b: youngest first — stale backlog must not eat slots
                need.sort(key=lambda x: -x[1]["birth_ts"])
            n_pool_tracked = sum(1 for t in tokens.values()
                                 if t.get("pool") and not t.get("pool_done"))
            for m, t in need[:5]:
                with LK:
                    t["pool_try_ts"] = now
                if n_pool_tracked >= MAX_POOL_TRACK:
                    break
                p = discover_pool(m)
                if p:
                    # seed baseline balances so dead pools still get an mcap
                    for k, addr in (("pool_last_b", p["pbt"]),
                                    ("pool_last_q", p["pqt"])):
                        try:
                            r2 = rpc("getAccountInfo",
                                     [addr, {"encoding": "base64"}])
                            v2 = (r2.get("result") or {}).get("value")
                            if v2:
                                amt = _decode_spl_amount(v2["data"][0])
                                with LK:
                                    t[k] = amt
                        except Exception:
                            pass
                    with LK:
                        if t.get("pool_last_b") and t.get("pool_last_q") is not None:
                            t["pool_mcap"] = round(t["pool_last_q"] * 1e6
                                                   / t["pool_last_b"], 4)
                        _liq_update(t)
                        t["pool"] = p
                        t["pool_last_ts"] = now
                        n_pool_tracked += 1
                        stats["pools_found"] += 1
                    subscribe_pool(m, t)
            # 1b) §66b: poll pool vaults over HTTP while Helius ws is down
            if not hws_ref["open"]:
                # §66f: open paper positions must never age out of the
                # poll window — exit management depends on their flow.
                open_mints = set()
                try:
                    for line in PAPER.open():
                        x = json.loads(line)
                        if x.get("status") == "open":
                            open_mints.add(x.get("mint"))
                except Exception:
                    pass
                with LK:
                    poll = [(m, t) for m, t in tokens.items()
                            if t.get("pool") and not t.get("pool_done")
                            and t.get("pool_last_q") is not None
                            and now - t["birth_ts"] < 6 * 3600]
                    # §66b: youngest first — E25 lives in the first hour
                    poll.sort(key=lambda x: -x[1]["birth_ts"])
                    prot = [x for x in poll if x[0] in open_mints]
                    rest = [x for x in poll if x[0] not in open_mints]
                    poll = (prot + rest)[:12]
                for m, t in poll:
                    p = t["pool"]
                    amts = {}
                    for k, addr in (("b", p["pbt"]), ("q", p["pqt"])):
                        r3 = rpc("getAccountInfo",
                                 [addr, {"encoding": "base64"}])
                        v3 = (r3.get("result") or {}).get("value")
                        if not v3:
                            amts = None
                            break
                        amts[k] = _decode_spl_amount(v3["data"][0])
                    if not amts or amts["b"] is None or amts["q"] is None:
                        continue
                    rec = None
                    with LK:
                        prev = t["pool_last_q"]
                        t["pool_last_b"] = amts["b"]
                        t["pool_last_q"] = amts["q"]
                        _liq_update(t)
                        t["pool_mcap"] = round(amts["q"] * 1e6
                                               / amts["b"], 4)
                        t["pool_notifs"] += 1
                        t["pool_last_ts"] = now
                        dv = amts["q"] - prev
                        if dv != 0:
                            sol = abs(dv) / 1e9
                            side = "buy" if dv > 0 else "sell"
                            if dv > 0:
                                t["pool_buys"] += 1
                                t["pool_buy_sol"] += sol
                            else:
                                t["pool_sells"] += 1
                                t["pool_sell_sol"] += sol
                            stats["pool_trades"] += 1
                            rec = {"t": now, "mint": m, "venue": "pool",
                                   "side": side, "sol": round(sol, 6),
                                   "mcap_sol": t["pool_mcap"]}
                    if rec:
                        with TRADES.open("a") as f:
                            f.write(json.dumps(rec) + "\n")
                    time.sleep(0.4)
            # 1c) §67b: batched curve polling while Helius ws is down.
            # (§67a pumpportal trade feed is paywalled — needs funded key.)
            # One getMultipleAccounts call covers every live curve; the
            # shared last_vsol baseline keeps accounting consistent with
            # the Helius path if it returns mid-run.
            if not hws_ref["open"]:
                with LK:
                    curve_poll = [(m, t["curve"]) for m, t in tokens.items()
                                  if t.get("curve")
                                  and now - t["birth_ts"] < TRACK_MAX_AGE]
                if curve_poll:
                    try:
                        r4 = rpc("getMultipleAccounts",
                                 [[a for _, a in curve_poll[:100]],
                                  {"encoding": "base64"}])
                        vals = (r4.get("result") or {}).get("value") or []
                    except Exception:
                        vals = []
                    recs = []
                    with LK:
                        for (m, _a), v4 in zip(curve_poll, vals):
                            t = tokens.get(m)
                            if not t or not v4:
                                continue
                            try:
                                d4 = v4.get("data")
                                b64 = d4[0] if isinstance(d4, list) else d4
                                dec = _decode_curve(b64)
                            except Exception:
                                continue
                            if dec is None:
                                continue
                            vtok, vsol, complete = dec
                            t["notifs"] += 1
                            if vtok:
                                t["last_mcap_sol"] = round(vsol * 1e6
                                                           / vtok, 4)
                            if complete and not t["grad_ts"]:
                                t["grad_ts"] = now
                                stats["complete_flags"] += 1
                            if t["last_vsol"] is None:
                                t["last_vsol"] = vsol
                                continue
                            dv = vsol - t["last_vsol"]
                            t["last_vsol"] = vsol
                            if dv == 0:
                                continue
                            sol = abs(dv) / 1e9
                            side = "buy" if dv > 0 else "sell"
                            if dv > 0:
                                t["buys"] += 1
                                t["buy_sol"] += sol
                            else:
                                t["sells"] += 1
                                t["sell_sol"] += sol
                            stats["trades"] += 1
                            recs.append({"t": now, "mint": m,
                                         "venue": "curve", "side": side,
                                         "sol": round(sol, 6),
                                         "mcap_sol": t["last_mcap_sol"]})
                    if recs:
                        with TRADES.open("a") as f:
                            for rec in recs:
                                f.write(json.dumps(rec) + "\n")
            # 2) snapshots
            with LK:
                items = list(tokens.items())
            for m, t in items:
                age = now - t["birth_ts"]
                ages = list(SNAP_AGES)
                if t.get("grad_ts"):
                    ages += list(GRAD_SNAP_AGES)
                for a in ages:
                    if age >= a and a not in t["snapped"]:
                        with LK:
                            t["snapped"].append(a)
                        rec = {"t": now, "mint": m, "age_s": a,
                               "seed": t["seed"], "creator": t["creator"],
                               "symbol": t["symbol"],
                               "grad": bool(t["grad_ts"]),
                               "grad_lag_s": (t["grad_ts"] - t["birth_ts"])
                               if t["grad_ts"] else None,
                               "buys": t["buys"], "sells": t["sells"],
                               "bs_ratio": round(t["buys"] / max(t["sells"], 1), 2),
                               "buy_sol": round(t["buy_sol"], 2),
                               "sell_sol": round(t["sell_sol"], 2),
                               "flow_ratio": round(t["buy_sol"]
                                                   / max(t["sell_sol"], 1e-9), 2),
                               "notifs": t["notifs"],
                               "mcap_sol": t["last_mcap_sol"],
                               "pool_found": bool(t.get("pool")),
                               "pool_buys": t["pool_buys"],
                               "pool_sells": t["pool_sells"],
                               "pool_buy_sol": round(t["pool_buy_sol"], 2),
                               "pool_sell_sol": round(t["pool_sell_sol"], 2),
                               "pool_flow_ratio": round(
                                   t["pool_buy_sol"]
                                   / max(t["pool_sell_sol"], 1e-9), 2),
                               "pool_mcap_sol": t["pool_mcap"],
                               "pool_liq_sol": t.get("pool_liq_sol"),
                               "pool_liq_min": t.get("pool_liq_min"),
                               "pool_liq_max": t.get("pool_liq_max")}
                        with SNAPS.open("a") as f:
                            f.write(json.dumps(rec) + "\n")
                        stats["snaps"] += 1
                # 2b) §56g: recycle pool slots — unsub pools quiet > 2h
                if t.get("pool") and not t.get("pool_done"):
                    last_pt = t.get("pool_last_ts")
                    if last_pt is None:
                        t["pool_last_ts"] = now  # 2h grace for legacy state
                    elif (now - last_pt > POOL_QUIET_S
                          or (age > 6 * 3600 and not t.get("pool_notifs"))):
                        # §66b: E25 window is ~1h post-grad; a silent pool
                        # older than 6h is dead weight — free the slot.
                        unsubscribe_mint(m, kinds=("pool_q", "pool_b"))
                        t["pool_done"] = True
                        stats["pool_pruned"] = stats.get("pool_pruned", 0) + 1
                # 3) curve unsub only (pool subs live until token prunes)
                if age > TRACK_MAX_AGE or (t["grad_ts"] and age > 900):
                    unsubscribe_mint(m, kinds=("curve",))
                # 4) runner alert: deep pool + buy-dominant flow on a fresh grad
                if (m not in alerted and t.get("grad_ts") and t.get("pool")
                        and age <= ALERT_MAX_AGE
                        and (t.get("pool_liq_sol") or 0) >= ALERT_LIQ_MIN
                        and t["pool_buy_sol"] >= ALERT_BUY_MIN
                        and t["pool_buys"] >= ALERT_BUYS_MIN
                        and (t["pool_buy_sol"] / max(t["pool_sell_sol"], 1e-9))
                            >= ALERT_FLOW_MIN):
                    alerted.add(m)
                    stats["alerts"] += 1
                    arec = {"t": now, "mint": m, "symbol": t.get("symbol"),
                            "seed": t["seed"],
                            "pool_liq_sol": t.get("pool_liq_sol"),
                            "pool_flow_ratio": round(
                                t["pool_buy_sol"]
                                / max(t["pool_sell_sol"], 1e-9), 2),
                            "pool_buy_sol": round(t["pool_buy_sol"], 1),
                            "pool_buys": t["pool_buys"],
                            "pool_sells": t["pool_sells"],
                            "pool_mcap": t.get("pool_mcap")}
                    with ALERTS.open("a") as f:
                        f.write(json.dumps(arec) + "\n")
                    try:
                        subprocess.run(
                            ["osascript", "-e",
                             f'display notification "liq {arec["pool_liq_sol"]} SOL · '
                             f'flow {arec["pool_flow_ratio"]} · '
                             f'buys {arec["pool_buys"]}" '
                             f'with title "MFG RUNNER: {arec["symbol"] or m[:8]}"'],
                            capture_output=True, timeout=10)
                    except Exception:
                        pass
            stop.wait(10)

    def killer():
        time.sleep(WINDOW_S + 30)
        stop.set()
        for ref in (hws_ref["ws"], pump_ref["ws"]):
            try:
                ref.close()
            except Exception:
                pass

    pump_ref = {"ws": None}
    threading.Thread(target=killer, daemon=True).start()
    threading.Thread(target=helius_loop, daemon=True).start()
    threading.Thread(target=snapshot_loop, daemon=True).start()

    ws = websocket.WebSocketApp(PUMP_WSS, on_open=pump_on_open,
                                on_message=pump_on_message,
                                on_error=lambda w, e: None,
                                on_close=lambda w, *a: None)
    pump_ref["ws"] = ws
    ws.run_forever(ping_interval=20, ping_timeout=10)
    stop.set()

    tokens = _save_state(tokens)
    tracked = sum(1 for t in tokens.values()
                  if time.time() - t["birth_ts"] < 26 * 3600)
    # compact per-token table for the dashboard widget (most active first)
    now = time.time()
    board = []
    for m, t in tokens.items():
        age = now - t["birth_ts"]
        grad = bool(t.get("grad_ts"))
        if age > 2 * 3600 or not (t.get("notifs") or t.get("pool_notifs")):
            continue
        if grad and t.get("pool"):
            buy, sell = t["pool_buy_sol"], t["pool_sell_sol"]
            flow = (buy / sell) if sell > 0 else (99.0 if buy > 0 else 0.0)
            mcap = t.get("pool_mcap")
            buys, sells = t["pool_buys"], t["pool_sells"]
            act = t.get("pool_notifs", 0)
        else:
            buy, sell = t["buy_sol"], t["sell_sol"]
            flow = (buy / sell) if sell > 0 else (99.0 if buy > 0 else 0.0)
            mcap = t.get("last_mcap_sol")
            buys, sells = t["buys"], t["sells"]
            act = t.get("notifs", 0)
        board.append({
            "symbol": (t.get("symbol") or m[:6])[:18],
            "mint": m,
            "seed": round(t["seed"], 2),
            "age_min": round(age / 60, 1),
            "buys": buys, "sells": sells,
            "buy_sol": round(buy, 1), "sell_sol": round(sell, 1),
            "flow_ratio": round(flow, 2),
            "mcap_sol": mcap,
            "grad": grad,
            "pool": bool(t.get("pool")),
            "liq_sol": t.get("pool_liq_sol") if grad else None,
            "notifs": act,
        })
    board.sort(key=lambda r: -(r["buy_sol"] + r["sell_sol"]))
    try:
        paper = paper_score()
    except Exception:
        paper = {}
    try:
        # §105: accrue the self-blacklist — creators of positions that
        # CLOSED at <= -30% in the baseline replay are recorded with
        # their close time. Repeat operators get rejected on their next
        # launch (costs one loss per operator, caps repeat exposure).
        if BLACKLIST.exists():
            bl_seen = set()
            for line in BLACKLIST.open():
                try:
                    bl_seen.add(json.loads(line).get("mint"))
                except Exception:
                    continue
        else:
            bl_seen = set()
        cre = {}
        if SNAPS.exists():
            for line in SNAPS.open():
                try:
                    s = json.loads(line)
                    if s.get("mint") and s.get("creator"):
                        cre.setdefault(s["mint"], s["creator"])
                except Exception:
                    continue
        if PAPER.exists():
            with BLACKLIST.open("a") as f:
                for line in PAPER.open():
                    try:
                        r = json.loads(line)
                        if (r.get("status") == "closed"
                                and r.get("ret", 0) <= -0.30
                                and r.get("mint") not in bl_seen
                                and cre.get(r.get("mint"))):
                            f.write(json.dumps({
                                "t": r.get("last_t"),
                                "creator": cre[r["mint"]],
                                "mint": r["mint"],
                                "ret": r.get("ret")}) + "\n")
                            bl_seen.add(r["mint"])
                    except Exception:
                        continue
    except Exception:
        pass
    try:
        # §72: abort-15 shadow — pre-registered a30 gate untouched; the
        # a15 variant accrues forward evidence on identical live data.
        p15 = paper_score(abort_min=15, out_path=PAPER_A15)
        if p15:
            paper["paper_a15_exp"] = p15.get("paper_exp")
            paper["paper_a15_closed"] = p15.get("paper_closed")
            paper["paper_a15_wins"] = p15.get("paper_wins")
    except Exception:
        pass
    try:
        # §74: two-stage abort hybrid (15m<1.08 then 30m<1.15) — replay
        # leader (+1.8% all-history, §74); accrues forward marks.
        ph = paper_score(out_path=PAPER_H108, stage1=(15, 1.08))
        if ph:
            paper["paper_h108_exp"] = ph.get("paper_exp")
            paper["paper_h108_closed"] = ph.get("paper_closed")
            paper["paper_h108_wins"] = ph.get("paper_wins")
    except Exception:
        pass
    try:
        # §77: strict-entry shadow (net>=60 SOL AND nb>=20 — the §76
        # positive-expectancy region) with frozen h108 exits. Accrues
        # OUT-OF-SAMPLE committed closes; gate stays frozen until this
        # proves itself forward.
        ps = paper_score(out_path=PAPER_S, stage1=(15, 1.08),
                         net_min=60.0, nb_min=20)
        if ps:
            paper["paper_s60_exp"] = ps.get("paper_exp")
            paper["paper_s60_closed"] = ps.get("paper_closed")
            paper["paper_s60_wins"] = ps.get("paper_wins")
    except Exception:
        pass
    try:
        # §79s: AMENDED strategy shadow — s60 entry + h108 exits +
        # near-miss abort (touch 1.30x, fail to reach 1.5x in 5m ->
        # exit at next trade). First non-falsified fix (in-sample
        # +0.08% -> +8.03%, bleeders 2->1); amendment.json re-zeroes
        # the gate; accrues fresh committed closes from amendment_ts.
        pn = paper_score(out_path=PAPER_SNM, stage1=(15, 1.08),
                         net_min=60.0, nb_min=20, nm_min=5)
        if pn:
            paper["paper_s60nm5_exp"] = pn.get("paper_exp")
            paper["paper_s60nm5_closed"] = pn.get("paper_closed")
            paper["paper_s60nm5_wins"] = pn.get("paper_wins")
    except Exception:
        pass
    try:
        # §79u: dust-buy filter SHADOW — s60nm5 + median buy >= 0.25 SOL
        # at the trigger (grind-rug fake-breadth signature). Fitted on
        # n=1 bleeder; accrues forward; amendment #2 only if it beats
        # s60nm5 over the same fresh-close window. Gate unchanged.
        pm = paper_score(out_path=PAPER_SMB, stage1=(15, 1.08),
                         net_min=60.0, nb_min=20, nm_min=5, med_min=0.25)
        if pm:
            paper["paper_s60nm5mb_exp"] = pm.get("paper_exp")
            paper["paper_s60nm5mb_closed"] = pm.get("paper_closed")
            paper["paper_s60nm5mb_wins"] = pm.get("paper_wins")
    except Exception:
        pass
    try:
        # §98a: funded-reject SHADOW — s60nm5 but skip any entry whose
        # creator was tripwire-flagged (funded from a bleeder tree).
        # The prospective test of the §98 pre-launch signal. Gate
        # unchanged; accrues forward from deployment.
        pf = paper_score(out_path=PAPER_SFR, stage1=(15, 1.08),
                         net_min=60.0, nb_min=20, nm_min=5,
                         funded_reject=True)
        if pf:
            paper["paper_s60nm5fr_exp"] = pf.get("paper_exp")
            paper["paper_s60nm5fr_closed"] = pf.get("paper_closed")
            paper["paper_s60nm5fr_wins"] = pf.get("paper_wins")
    except Exception:
        pass
    try:
        # §112: live hook — fr-gated entries go to live_trader in
        # dry-run (nothing submits until the owner's manual_signoff.json
        # exists; STOP_LIVE_TRADING halts instantly). Entries whose
        # entry_t is fresh (this run's window) and not yet signaled
        # trigger a curve_buy; the ledger shows exactly what live WOULD
        # do. Exits need the tighter loop (§113) — not wired here.
        import importlib.util as _ilu
        _spec = _ilu.spec_from_file_location(
            "live_trader", str(MON / "live_trader.py"))
        _lt = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_lt)
        _st_f = MON / "live_signal_state.json"
        _sent = json.loads(_st_f.read_text()) if _st_f.exists() else {}
        _now = time.time()
        if PAPER_SFR.exists():
            for line in PAPER_SFR.open():
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if (r.get("status") == "open"
                        and r.get("mint") not in _sent
                        and _now - r.get("entry_t", 0) < 1200):
                    _ok, _why = _lt.live_enabled()
                    _size = 0.01
                    if _ok:
                        _size, _bal = _lt.position_size_sol(
                            json.loads(_lt.WALLET_F.read_text())["address"])
                    _row = _lt.curve_buy(r["mint"], _size,
                                         reason="s60nm5fr signal (hook)")
                    _sent[r["mint"]] = {"t": _now,
                                        "result": _row.get("result")}
        _st_f.write_text(json.dumps(_sent))
        paper["live_hook"] = sum(1 for v in _sent.values()
                                 if _now - v.get("t", 0) < 1200)
    except Exception:
        pass
    try:
        # §86a: 3-min time-stop SHADOW — dump unpumped campaigns early;
        # §99: honest deadline fill. Insurance against slow bleeds on
        # positions that never freeroll. Honest backtest +1.0%/trade
        # (n=27, fragile 36s margin on GsM2Nq). Forward validation only;
        # gate unchanged. Amendment #4 only if forward exp >= +1.5%.
        pt = paper_score(out_path=PAPER_STS, stage1=(15, 1.08),
                         net_min=60.0, nb_min=20, nm_min=5, ts_min=3)
        if pt:
            paper["paper_s60nm5ts180_exp"] = pt.get("paper_exp")
            paper["paper_s60nm5ts180_closed"] = pt.get("paper_closed")
            paper["paper_s60nm5ts180_wins"] = pt.get("paper_wins")
    except Exception:
        pass
    try:
        # §79j: top-holder concentration snapshot at each fresh s60
        # signal — forward data for the distribute-vs-harvest tell.
        holder_snapshots(rpc)
    except Exception:
        pass
    try:
        # §82: entry-time SIGNER snapshot — feePayer SOL deltas over the
        # first ~40 txs give a tape-native insider-concentration metric
        # (top1_share) without keyed RPC. Forward test: does top1_share
        # separate future bleeders from winners at entry time?
        signer_snapshots(rpc, tokens)
    except Exception:
        pass
    try:
        # §89: watch the bleeder operator's treasury/layering chain for
        # outbound 80-95 SOL transfers to fresh wallets — the instant-fill
        # seed funding a future bleeder launch. Pre-launch warning list
        # in mfg_funding.jsonl; cross-ref against new births at read time.
        treasury_watch(rpc)
    except Exception:
        pass
    return {"artifact": {
        "summary": (f"births={stats['births']} big_seeds={stats['big_seeds']} "
                    f"tracked={tracked} trades={stats['trades']} "
                    f"pool_trades={stats['pool_trades']} pools={stats['pools_found']} "
                    f"snaps={stats['snaps']} alerts={stats['alerts']} "
                    f"helius_err={stats['helius_err']} "
                    f"paper={paper.get('paper_positions', 0)}pos/"
                    f"{paper.get('paper_closed', 0)}closed "
                    f"exp={paper.get('paper_exp')}"),
        **stats, "tracked_open": tracked, **paper,
        "tokens": board[:12],
        "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }}
