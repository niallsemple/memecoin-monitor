import json

with open('paper_v6.json') as f:
    data = json.load(f)

print("Keys:", list(data.keys())[:10])
print("Type:", type(data))
if isinstance(data, dict):
    for k, v in data.items():
        print(f"{k}: {type(v)}")
        if isinstance(v, list) and v:
            print(f"  len={len(v)}, sample keys: {list(v[0].keys()) if isinstance(v[0], dict) else type(v[0])}")
            break
        elif isinstance(v, dict) and v:
            sk = list(v.keys())[0]
            print(f"  sample key: {sk}, type: {type(v[sk])}")
            break
