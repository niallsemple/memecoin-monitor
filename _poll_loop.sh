#!/bin/bash
# Outer poll loop — rebuilt 09-13 after finding all components dead.
# Order is mandated: collector data must be fresh BEFORE the live engine
# reads it (live-before-collector = stale-data entries, cost us 9Ndi once).
# 09-13b: position-priority mode — while a live position is open, hfna_live
# re-runs back-to-back (each invocation = a 150s on-chain fast loop with
# 15s fee-curve sampling + tripwire). Paper arms wait. Fixes the blind
# 0-237s accrual window seen on probe #4.
M="$(cd "$(dirname "$0")" && pwd)"
cd "$M" || exit 1
while true; do
  [ -f STOP_LIVE_TRADING ] && { echo "$(date +%s) kill switch present — loop exiting"; exit 0; }
  python3 bin_collector.py   >> _bin_collector.log 2>&1
  python3 pool_txflow.py     >> _pool_txflow.log 2>&1
  python3 hfna_live.py       >> _hfna_live.log 2>&1
  # position-priority: keep the engine's fast loop running while in position
  for i in 1 2 3 4; do
    python3 -c "import json,sys; sys.exit(0 if json.load(open('hfna_live_state.json')).get('pos') else 1)" || break
    echo "$(date +%s) position open — engine priority pass $i" >> _hfna_live.log
    python3 hfna_live.py     >> _hfna_live.log 2>&1
  done
  python3 wash_scan.py       >> _wash_scan.log 2>&1
  python3 hfna_paper.py        >> _paper.log 2>&1
  python3 hfna_paper_w7.py     >> _paper_w7.log 2>&1
  python3 hfna_paper_repo.py   >> _paper_repo.log 2>&1
  python3 hfna_paper_flow.py   >> _paper_flow.log 2>&1
  python3 hfna_paper_reflow.py >> _paper_reflow.log 2>&1
  python3 hfna_paper_thin.py   >> _paper_thin.log 2>&1
  python3 bin_collector.py fast >> _bin_collector.log 2>&1
  python3 regime.py            >> _regime.log 2>&1
  date +%s > _loop_heartbeat   # dead-man: any turn can check freshness
  sleep 20
done
