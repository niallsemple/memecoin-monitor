import json, time, os
STATE = 'xchain_outcomes.json'
print(1)
s = json.load(open(STATE)) if os.path.exists(STATE) else {}
print(2, len(s))
