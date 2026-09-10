import json

# Count for control
with open(    ) as f:
    lines = [json.loads(l) for l in f]
entries = [x for x in lines if x.get(    )]
exits = [x for x in lines if x.get(    )]
print(f'control entries={len(entries)}, exits={len(exits)}, open={len(entries)-len(exits)}')

with open(    ) as f:
    lines = [json.loads(l) for l in f]
entries = [x for x in lines if x.get(    )]
exits = [x for x in lines if x.get(    )]
print(f'crowd entries={len(entries)}, exits={len(exits)}, open={len(entries)-len(exits)}')

with open(    ) as f:
    lines = [json.loads(l) for l in f]
print(f'pumpswap_live trades={len(lines)}')
for l in lines:
    action = l.get(    )
    if action in (    ,    ):
        print(f'  [{l.get(    ,    )}] {action}: {l.get(    ,    )}')
