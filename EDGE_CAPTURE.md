# EDGE CAPTURE LAYER — research → running code

Built 2026-09-18. Turns `memecoin-research/05-synthesis.md` into capture
infrastructure on top of the existing memecoin-monitor data plane.
Read the campaign README first: detection was never the bottleneck —
this layer exists to make detection *systematic* and to capture the
information classes the research says actually matter.

## Components

### 1. `edge_screen.py` — the pre-entry checklist as one verdict
The "60-second drill" automated. Given a mint (+ optional deployer,
live mcap, age), it runs seven checks and emits PASS / WATCH / AVOID
with per-check reasons, logged to `edge_screen_log.jsonl`:

| check | source research | AVOID threshold |
|---|---|---|
| creator blacklist / denylists | P3 serial deployers | listed |
| birth-window bundle share (`bundle_share.py`) | P3 bundles | ≥20% |
| insider overhang (`insider_screen_v2.py`) | P3 clusters | ≥30% |
| mintable/freezable authority | P2 contract check | either set |
| top1/top5 concentration | P3 Bubblemaps tiers | ≥30% / ≥50% |
| holder count | P1 cheat sheet | <7 |
| age / mcap floors | P1 cheat sheet | <40min / <150 SOL |

CAVEAT (by design, inherited from insider_screen_v2): verdicts are only
valid at ENTRY time. Retrospective runs on old mints misread closed ATAs
as concentration. Smoke test on a 20-day-old mint correctly demonstrated
this failure mode (top1=99.5% post-collapse).

### 2. `wallet_vetter.py` → `smart_wallets.json` — the wallet DB
Streams `mfg_wallet_trades.jsonl` (2.1M trades, 186,103 wallets) and
applies the research gates: reject <2min median hold (sniper bots),
<30 round trips (wash risk), >80% win rate (insider/bot flag);
COPYABLE needs 40–75% win, positive roi_proxy, ≥14d span, 5–20
trades/day.

First full run: **31 vetted of 186,103** — 11 WATCH, 20 REJECT
(7 sniper bots, 13 too-good-to-be-true), **zero COPYABLE**. This is an
honest finding, not a bug: every ≥30-trip wallet in the ledger has a
negative roi_proxy (−31% to −82%), because the ledger samples
manufactured-launch participants, which over-represents losers. The
COPYABLE cohort has to come from a broader trade feed, not this ledger.
`--min-span-days` flag (default 14; the ledger spans ~13d, so 7 was
used for the interim run). 99.98% of wallets fail the gates, which is
exactly the base rate the research predicts.
Re-run periodically as the ledger grows: `python3 wallet_vetter.py`.

### 3. `convergence_watch.py` — the ≥3-wallet signal
Q3 rule #9: one smart wallet buying = noise; three independent vetted
wallets on the same mint = signal. Scans a trailing window of the
ledger for buys by vetted wallets, emits to `edge_convergence.jsonl`.
Suggested cadence: run every 15–30 min via the existing loop infra.

### Already capturing (pre-existing, mapped to research)
- `curve_collector.py` / `mfg_tokens.jsonl` — lifecycle map data (Q2)
- `birth_watch.py`, `h16_early*.py` — firehose + first-minutes traction (Q1)
- `mfg_report.py` — runner/husk feature separation (manufactured-attention detector)
- `deployer_safety.py`, `cluster_detector.py`, `fp_cluster.py` — forensics plane
- `exec_journal.jsonl`, `exec_dry.py` — the trade journal (Q3 #11)

## Not capturable on-chain (acknowledged gaps)
- **Narrative pre-existence** (signal #1: meme pre-dates token) — needs
  X/TikTok traction data; manual check or future social API.
- **KOL-promotion-as-sell-signal** — needs KOL identity + post times.
- **CEX-listing distribution events** — watchable via exchange wallet
  labels, not currently in the data plane.

## Workflow (daily)
1. `wallet_vetter.py` weekly — refresh the wallet DB (both ledgers)
2. `convergence_watch.py` every 15–30 min — convergence alerts
3. `edge_screen.py <mint>` on any alert or manual candidate — verdict before entry
4. Entries/exits journaled via existing exec layer

Or just run the loop: `./edge_capture_loop.sh` (broad feed poll every
60s, 20-min convergence cadence across both ledgers, weekly vetter).
Kill switch: `touch STOP_EDGE_CAPTURE`.

## Added 2026-09-18 (evening) — four upgrades

### 4. `broad_feed.py` — graduated-token trade feed (COPYABLE hunt)
The mfg ledger gave zero COPYABLE wallets because it samples
manufactured-launch traders. PumpPortal's token-trade websocket needs a
funded API key (server-verified: rejects without 0.02 SOL on account),
so this polls Helius enhanced SWAP transactions for the top ~25
PumpSwap pools by 24h tx count (GeckoTerminal ranking) and appends to
`broad_trades.jsonl` in the exact `mfg_wallet_trades.jsonl` schema.
Verified live: 61 trades from 25 mints in one cycle; FARTCOIN buy/sell
legs parse with wallet + SOL amounts. Vet it with
`python3 wallet_vetter.py --ledger broad_trades.jsonl --out
smart_wallets_broad.json` — expect days-to-weeks of capture before any
wallet clears the 30-trip gate. That wait is the price of an honest
COPYABLE cohort.

### 5. `edge_screen.py --profile early_pumpswap`
Named profile for the sub-30m PumpSwap lane. Forensic checks (bundle,
overhang, authorities, concentration, blacklist) are byte-identical
across profiles; only the lane floors change: age floor WAIVED (the
40min floor would WATCH every in-lane candidate by definition), mcap
floor softened 150 → 40 SOL. Verified: age=12min/mcap=95 SOL both PASS
under the profile while insider overhang 50.4% still AVOIDs the mint.
`exec_dry.py` now calls screen with this profile — its entry lane is
exactly this lane.

### 6. screen() TTL cache
`screen(..., ttl=300)` caches per mint+profile in `screen_cache.json`.
Polling loops (exec_dry every ~1min) no longer re-hit Helius for the
same mint. Cached returns are marked `"cached": true` and NOT re-logged.
`--ttl 0` or `ttl=0` bypasses. Verified: second identical screen returns
instantly with the cached verdict.

### 7. convergence → exec_dry priority lane
`convergence_watch.py` now writes qualifying alerts to
`edge_candidates.jsonl` (plus merged multi-DB/multi-ledger support via
`--db` / `--ledger` comma lists). `exec_dry.py` loads candidates fresh
<2h and sorts them ABOVE raw liquidity rank when picking entries.
Verified: fresh candidate outranks a 100x-higher-liquidity mint; stale
(3h) candidate correctly expires.

## Test results 2026-09-18

End-to-end live tests via `_edge_live_test.py` (grabs a fresh pump.fun
birth off the PumpPortal websocket, screens it at true entry time):

- **DYC**, **MiSoHorne**, **bc** births: all correctly AVOID —
  manufactured concentration (~50% single insider wallet, vault
  excluded), bundle share ~1–2% after the §334 fix.
- **§334 bundle_share fix (critical).** The old create-tx heuristic
  (`deployer delta >700M`) silently never fired — pump.fun credits the
  curve's 793.1M inventory to the curve vault owner, not the creator.
  Result: outsider_pct printed 202–209% (constant ~100pp create
  allocation + platform-reserve re-distribution double-count). Fixed by
  detecting the create tx via full-supply distribution (>900M positive
  deltas), identifying `curve_owner` from it, and counting only
  acquisitions FROM THE CURVE. Same mints recompute to **1.24% / 2.19%**.
  Side findings: `BwWK17cbHx…de6s` is the pump.fun curve vault owner on
  every launch; `deployer_pct` now reads ~0 because the creator's
  initialBuy rides inside the create tx (use the ledger's `initialBuy`
  field for creator seed size instead). Cache is versioned (`v: 2`) —
  pre-fix entries recompute automatically.
- **Vault-exclusion base58 fix.** `_b58()` was counting all zero bytes
  instead of leading ones, producing invalid pubkeys → Helius
  WrongSize → vault silently NOT excluded. After fix, `vault_pct`
  separates correctly (e.g. 49.6% vault vs 50.4% insider top1).
- **insider_overhang** now logs a WATCH entry when the classifier
  errors instead of vanishing from output.
- **Entry-time indexing lag:** a seconds-old mint can return empty
  sigs/supply from RPC. bundle_share now retries empty sig pages 3×
  with 3s backoff; if other checks read "no data", re-screen ~60s
  after birth.
- **Known limits:** mints with >3000 txs return "birth beyond
  3000-sig window" → bundle WATCH (verdict still works off the other
  six checks); retrospective verdicts on old mints are invalid by
  design (closed ATAs read as concentration).
- **convergence_watch.py** mechanics verified over the full ledger
  span (31 alerts); production use is `--minutes 60 --min-wallets 3`.
