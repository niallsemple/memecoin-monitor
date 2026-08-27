# Memecoin Monitor

Live study + paper-trading system for Solana memecoin new listings.

Monitors dexscreener new token profiles, audits each candidate with
GoPlus + RugCheck + holder-concentration backfill, and tracks outcomes
against a strict filter set. Paper traders (v1–v4) simulate execution
with progressively tighter entry/exit rules. **No real orders.**

## Components

- `monitor.py` — new-listing monitor (dexscreener feed, audit pipeline)
- `holders.py` — holder-concentration backfill
- `analyze.py` / `analysis_rows.json` — outcome analysis
- `backtest.py` / `sweep.py` / `sim.py` — historical replay and parameter sweeps
- `papertrader.py` → `papertrader_v4.py` — paper-trading engine iterations
- `paper*.json` — paper account state per version
- `trades*.md` — trade logs per version
- `REPORT.md` — findings from the live study (window 2026-08-25)

## Key findings (see REPORT.md)

- ~48% of new listings fall >50% from detection — the base rate of catastrophic loss
- FAIL-audit cohort: median −58.8%; PASS cohort: median +9.8%
- Audit filters prevent rug mechanics, not selling — exit discipline is the edge
