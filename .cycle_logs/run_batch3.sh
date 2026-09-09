#!/bin/bash
cd /Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor
nohup python3 pumpswap_live.py --minutes 6 > .cycle_logs/pswap_live.log 2>&1 &
echo "live pid $! at $(date +%H%M%S)"
python3 pumpswap_fastpoll.py --minutes 3 > .cycle_logs/fastpoll.log 2>&1 &
P1=$!
python3 pool_reserve_poller.py --minutes 2 > .cycle_logs/reserve.log 2>&1 &
P2=$!
wait $P1 $P2
echo "=== batch3 done $(date +%H%M%S) ==="
