import json

d = json.load(open('mfg_state.json'))
k = list(d.keys())[0]
print('Key:', repr(k))
print('Value type:', type(d[k]))
print(json.dumps(d[k], indent=2, default=str)[:1000])

print('\n--- paper_v6.json ---')
p = json.load(open('paper_v6.json'))
print('Type:', type(p))
if isinstance(p, dict):
    for k2, v in p.items():
        print('Key:', repr(k2))
        print(json.dumps(v, indent=2, default=str)[:600])
        break
elif isinstance(p, list):
    for v in p[:2]:
        print(json.dumps(v, indent=2, default=str)[:600])
