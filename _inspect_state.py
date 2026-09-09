import json
with open('mfg_state.json') as f:
    d = json.load(f)
print('entries:', len(d))
for k, v in d.items():
    print(k, type(v).__name__, len(v) if isinstance(v, (list, dict)) else v)
