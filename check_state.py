import json
d=json.load(open('xchain_outcomes.json'))
print(len(d), 'tracked positions')
for k,v in d.items():
    print(k, v.get('status'), v.get('exit_reason'))
