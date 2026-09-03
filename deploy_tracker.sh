#!/bin/bash
# deploy_tracker.sh — §259: the curve-collector Automation runs a FROZEN COPY
# of the tracker at its assets root, not the repo file. live_trader.py edits
# go live automatically (importlib from MON each pass); tracker_live.py edits
# do NOT — run this after every tracker_live.py change.
set -e
MON="/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor"
A="/Users/niallsemple/Library/Application Support/kimi-desktop/daimon-share/daimon/agents/main/blueprint/automations/automation_3840d0e4-ec6c-4ed2-97e6-781059fe4095/assets"
python3 -m py_compile "$MON/automations/tracker_live.py"
cp "$MON/automations/tracker_live.py" "$A/automation.py"
rm -rf "$A/__pycache__"
diff "$A/automation.py" "$MON/automations/tracker_live.py" && echo "DEPLOYED: assets copy identical to tracker_live.py"
