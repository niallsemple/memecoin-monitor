#!/bin/bash
# Execution-first dry loop. Live trading stays OFF (STOP_LIVE_TRADING required).
set -euo pipefail
trap '' HUP
cd "$(dirname "$0")"
if [ ! -f STOP_LIVE_TRADING ]; then
  echo "STOP_LIVE_TRADING missing — refusing to start (dry-only loop)"
  exit 2
fi
export SSL_CERT_FILE="$(python3 -c 'import certifi; print(certifi.where())')"
export REQUESTS_CA_BUNDLE="$SSL_CERT_FILE"
mkdir -p logs
echo "[$(date)] exec_dry_loop start pid=$$" >> logs/exec_dry_loop.log
while true; do
  python3 pool_reserve_poller.py --once >> logs/exec_dry_reserve.log 2>&1 || true
  python3 exec_dry.py --once >> logs/exec_dry.log 2>&1 || true
  python3 pattern_markout.py --once >> logs/pattern_markout.log 2>&1 || true
  sleep 60 || true
done
