#!/bin/bash
cd /Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor
python3 base4_paper.py > .cycle_logs/paper_ctrl2.log 2>&1 &
P1=$!
python3 base4_paper.py crowd > .cycle_logs/paper_crowd2.log 2>&1 &
P2=$!
python3 deployer_safety.py --hot > .cycle_logs/deployer2.log 2>&1 &
P3=$!
wait $P1 $P2 $P3
echo "=== batch2 done $(date +%H%M%S) ==="
