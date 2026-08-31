"""funder_trace2.py <tag> <entry_t> — for stored pre-entry buyer wallets, find wallet birth time + first-tx fee payer (funder)."""
import json, urllib.request, time, collections, sys
RPC="https://api.mainnet-beta.solana.com"
def rpc(method, params, tries=8):
    for i in range(tries):
        try:
            req=urllib.request.Request(RPC, data=json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode(),
                                       headers={'Content-Type':'application/json'})
            return json.load(urllib.request.urlopen(req, timeout=25))
        except Exception as e:
            time.sleep(min(2+2*i, 15) if '429' in str(e) else 1)
    return {}
tag, entry_t = sys.argv[1], float(sys.argv[2])
st=json.load(open(f'wt_{tag}.json'))
wallets=list(dict.fromkeys(st.get('payers',[])))
print(f"{tag}: {len(wallets)} unique buyer wallets")
fund=[]
for w in wallets:
    sigs=rpc("getSignaturesForAddress",[w,{"limit":1000}]).get('result') or []
    sigs=[s for s in sigs if s.get('blockTime')]
    if not sigs: continue
    first=sigs[-1]  # oldest within first page
    birth=first['blockTime']
    funder=None
    t=rpc("getTransaction",[first['signature'],{"encoding":"json","maxSupportedTransactionVersion":0}]).get('result')
    if t:
        keys=t['transaction']['message']['accountKeys']
        funder=keys[0] if keys else None
        if funder==w and len(keys)>1: funder=keys[1]
    fund.append({"w":w,"birth":birth,"funder":funder})
    time.sleep(0.3)
ages=[(entry_t-f['birth'])/3600 for f in fund]
fc=collections.Counter(f['funder'] for f in fund)
json.dump(fund, open(f'funders_{tag}.json','w'))
print(f"traced {len(fund)}; wallet ages (h): min={min(ages):.2f} med={sorted(ages)[len(ages)//2]:.2f} max={max(ages):.1f}")
print(f"unique funders: {len(fc)}; top: {[(str(k)[:8],v) for k,v in fc.most_common(5)]}")
print(f"funder concentration (top1 share): {fc.most_common(1)[0][1]/len(fund):.2f}")
