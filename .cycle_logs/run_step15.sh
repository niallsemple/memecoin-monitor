#!/bin/bash
cd /Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor
{
echo "== bsc_paper bsc =="
python3 bsc_paper.py bsc 2>&1 | tail -12
echo "== bsc_paper base =="
python3 bsc_paper.py base 2>&1 | tail -12
echo "== bsc_paper bsc lockgate =="
python3 bsc_paper.py bsc lockgate 2>&1 | tail -12
echo "== bsc_paper bsc lockgate_usdt =="
python3 bsc_paper.py bsc lockgate_usdt 2>&1 | tail -12
echo "== bsc_paper bsc lockgate_gp =="
python3 bsc_paper.py bsc lockgate_gp 2>&1 | tail -12
} > .cycle_logs/bsc_paper_all.log 2>&1
echo "step15 done $(date +%H%M%S)"
