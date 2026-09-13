#!/bin/bash
# momentum-cell evidence loop: feed + DRY watcher, 60s cadence.
# Evidence-first: --dry always; live requires explicit owner action.
cd "$(dirname "$0")"
while true; do
  python3 pumpswap_tracker.py        >> _cell_feed.log 2>&1
  python3 pumpswap_live.py --once --dry >> _cell_watch.log 2>&1
  sleep 60
done
