"""wallet_trace2.py <pool> <entry_t> <tag> — resumable paginated unique-buyer counter."""
import json, urllib.request, time, collections, sys, pathlib
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
pool, entry_t, tag = sys.argv[1], float(sys.argv[2]), sys.argv[3]
sf=pathlib.Path(f'wt_{tag}.json')
state=json.load(open(sf)) if sf.exists() else {"before":None,"pages":0,"pre":[],"done":False}
entry_t=float(entry_t)
if not state["done"]:
    t_end=time.time()+150
    while time.time()<t_end:
        p=[pool,{"limit":1000}]
        if state["before"]: p[1]["before"]=state["before"]
        sigs=[s for s in (rpc("getSignaturesForAddress",p).get('result') or []) if s.get('blockTime')]
        if not sigs: time.sleep(1); continue
        state["pages"]+=1
        state["pre"].extend(s['signature'] for s in sigs if s['blockTime']<=entry_t)
        if sigs[-1]['blockTime']<=entry_t:
            state["done"]=True; break
        state["before"]=sigs[-1]['signature']
        time.sleep(0.35)
    json.dump(state, open(sf,'w'))
    print(f"paging: pages={state['pages']} pre={len(state['pre'])} done={state['done']}")
if state["done"]:
    payers=[]
    fetched=state.get("payers",[])
    done_sigs=set(state.get("done_sigs",[]))
    for sig in state["pre"]:
        if sig in done_sigs or len(payers)+len(fetched)>=90: break
        t=rpc("getTransaction",[sig,{"encoding":"json","maxSupportedTransactionVersion":0}])
        res=t.get('result')
        if res: fetched.append(res['transaction']['message']['accountKeys'][0])
        done_sigs.add(sig)
        time.sleep(0.3)
    state["payers"]=fetched; state["done_sigs"]=list(done_sigs)
    json.dump(state, open(sf,'w'))
    c=collections.Counter(fetched)
    print(f"fetched={len(fetched)} unique={len(c)} repeat_frac={round(1-len(c)/max(len(fetched),1),3)} top={[(k[:8],v) for k,v in c.most_common(5)]}")
