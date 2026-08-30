# Live Automation Code (backup of Daimon runtime copies)

These are the deployed copies of the memecoin system's Kimi Work Blueprint
Automations. The runtime executes the versions under the Daimon
`blueprint/automations/` directory; this folder is the version-controlled
backup. Keep them in sync when redeploying.

| file | automation | schedule | purpose |
|---|---|---|---|
| `mfg_tracker.py` | automation_3840d0e4 | every 20 min (19-min window) | Full-lifecycle MFG tracker: PumpPortal birth/migration feed, Helius big-seed curve subs, PumpSwap pool discovery + trade capture, runner alerts (desktop notify), §56e free-roll paper-trader (`paper_score()`), pool-slot recycling (§56g). Feeds MFG TRACKER widget on HL Research canvas. |
| `memecoin_loop.py` | automation_6d57d1be | every 10 min | Dexscreener new-listing pipeline: contract audit (GoPlus+RugCheck), behavioural forensics, cluster tagging; runs paper books v2–v6 in parallel; logs to auto_log.md. |
| `flag_flip_monitor.py` | automation_b70c447a | interval | Audit flag-flip monitor: watches tracked tokens for audit-status changes. |
| (prompt only) | automation_17fc6c1a | condition check every 6h | Go-live alerter: when `gate_check.py` shows v3 STRICT qualified=true, writes go-live-brief.md, latches `.v3_go_live_notified`, desktop-notifies. GO/NO-GO stays with the owner — no real trades without explicit approval. |

Cross-chain system (`xchain_*.py` in repo root) is driven by
automation_8d83a51b (hourly local_conversation) which simply runs
`xchain_scan.py`, sleeps 60s, then `xchain_track.py`.

Secrets: automations read `helius_key.txt` from the repo directory at
runtime; the key file is gitignored and must be provisioned separately.
