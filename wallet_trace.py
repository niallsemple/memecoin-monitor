"""wallet_trace.py <mint> <entry_t> — count unique pre-entry swap fee payers (public RPC)."""
import json, urllib.request, time, collections, sys
RPC="https://api.mainnet-beta.solana.com"
def rpc(method, params, tries=6):
    for i in range(tries):
        try:
            req=urllib.request.Request(RPC, data=json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode(),
                                       headers={'Content-Type':'application/json'})
            return json.load(urllib.request.urlopen(req, timeout=25))
        except Exception as e:
            time.sleep(2+2*i if '429' in str(e) else 1)
    return {}
mint, entry_t = sys.argv[1], float(sys.argv[2])
pre=[]; before=None; pages=0
t_end=time.time()+200
while time.time()<t_end and pages<30:
    p=[mint,{"limit":1000}]
    if before: p[1]["before"]=before
    sigs=[s for s in (rpc("getSignaturesForAddress",p).get('result') or []) if s.get('blockTime')]
    if not sigs:
        if before is None: break
        time.sleep(1); continue
    pages+=1
    pre.extend(s for s in sigs if s['blockTime']<=entry_t)
    if sigs[-1]['blockTime']<=entry_t: break
    before=sigs[-1]['signature']
    time.sleep(0.4)
pre.sort(key=lambda s:s['blockTime'])
payers=[]
for s in pre[:90]:
    t=rpc("getTransaction",[s['signature'],{"encoding":"json","maxSupportedTransactionVersion":0}])
    res=t.get('result')
    if res: payers.append(res['transaction']['message']['accountKeys'][0])
    time.sleep(0.35)
c=collections.Counter(payers)
out={"mint":mint[:8],"pages":pages,"pre_sigs":len(pre),"fetched":len(payers),
     "unique":len(c),"repeat_frac":round(1-len(c)/max(len(payers),1),3),
     "top":[(k[:8],v) for k,v in c.most_common(5)]}
print(json.dumps(out, indent=1))
