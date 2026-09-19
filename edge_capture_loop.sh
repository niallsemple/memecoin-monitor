#!/bin/bash
# edge_capture_loop.sh — capture-only loop for the research-derived edge layer.
# NO trading. Runs convergence detection on a cadence and refreshes the
# smart-wallet DB weekly. Kill by: touch STOP_EDGE_CAPTURE
set -euo pipefail
trap '' HUP
cd "$(dirname "$0")"
export SSL_CERT_FILE="$(python3 -c 'import certifi; print(certifi.where())')"
export REQUESTS_CA_BUNDLE="$SSL_CERT_FILE"
mkdir -p logs
echo "[$(date)] edge_capture_loop start pid=$$" >> logs/edge_capture.log

CONVERGENCE_EVERY_S=1200        # 20 min
VETTER_EVERY_S=604800           # 7 days
FEED_EVERY_S=60                 # broad graduated-token trade poll
last_conv=0
last_vet=0
last_feed=0

while true; do
  if [ -f STOP_EDGE_CAPTURE ]; then
    echo "[$(date)] STOP_EDGE_CAPTURE found — exiting" >> logs/edge_capture.log
    exit 0
  fi
  now=$(date +%s)

  # broad feed: poll Helius swaps on top PumpSwap graduates every minute
  # (single-cycle; the loop IS the scheduler, no extra daemon needed)
  if [ $((now - last_feed)) -ge $FEED_EVERY_S ]; then
    python3 broad_feed.py --once --watch 25 \
      >> logs/broad_feed.log 2>&1 || true
    last_feed=$now
  fi

  if [ $((now - last_conv)) -ge $CONVERGENCE_EVERY_S ]; then
    python3 convergence_watch.py --minutes 60 --min-wallets 3 \
      --db smart_wallets.json,smart_wallets_broad.json \
      --ledger mfg_wallet_trades.jsonl,broad_trades.jsonl \
      >> logs/edge_convergence.log 2>&1 || true
    last_conv=$now
  fi

  if [ $((now - last_vet)) -ge $VETTER_EVERY_S ]; then
    python3 wallet_vetter.py --min-span-days 7 \
      >> logs/edge_vetter.log 2>&1 || true
    python3 wallet_vetter.py --min-span-days 7 \
      --ledger broad_trades.jsonl --out smart_wallets_broad.json \
      >> logs/edge_vetter.log 2>&1 || true
    last_vet=$now
  fi

  sleep 60 || true
done
