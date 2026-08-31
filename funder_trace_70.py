"""§70b: funding-source cluster trace for the 14 post-cutoff creators.
Each creator is a fresh wallet; the question is whether rug vs runner
launches trace back to different FUNDERS (whoever first sent them SOL).
Resumable: writes funder_trace.json after every wallet."""
import json, time, pathlib, urllib.request, collections

MON = pathlib.Path("/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor")
RPCS = ["https://api.mainnet-beta.solana.com",
        "https://solana-rpc.publicnode.com",
        "https://solana.drpc.org"]
_i = {"i": 0}

def rpc(method, params, tries=4):
    body = json.dumps({"jsonrpc": "2.0", "id": 1,
                       "method": method, "params": params}).encode()
    for _ in range(tries):
        url = RPCS[_i["i"] % len(RPCS)]
        try:
            req = urllib.request.Request(
                url, data=body,
                headers={"Content-Type": "application/json",
                         "User-Agent": "Mozilla/5.0 (funder-trace/1.0)"})
            r = json.loads(urllib.request.urlopen(req, timeout=25).read())
            if "error" in r:
                raise Exception(str(r["error"])[:80])
            time.sleep(0.22)
            return r.get("result")
        except Exception:
            _i["i"] += 1
            time.sleep(0.6)
    return None

# creators + outcomes
replay = json.loads((MON / "rug_replay.json").read_text())
positions = {}
with open(MON / "mfg_paper_trades.jsonl") as f:
    for line in f:
        try:
            x = json.loads(line)
        except Exception:
            continue
        positions[x["mint"]] = x

try:
    trace = json.loads((MON / "funder_trace.json").read_text())
    print(f"resuming: {len(trace)} creators traced")
except Exception:
    trace = {}

for m, v in replay.items():
    creator = v["birth"].get("creator")
    if not creator or creator in trace:
        continue
    # oldest txs first: page to the end
    sigs = rpc("getSignaturesForAddress", [creator, {"limit": 100}]) or []
    if not sigs:
        trace[creator] = {"funder": None, "mint": m}
        continue
    oldest = sigs[-1]["signature"]
    tx = rpc("getTransaction",
             [oldest, {"encoding": "json",
                       "maxSupportedTransactionVersion": 0}])
    funder = None
    if tx:
        try:
            keys = [k if isinstance(k, str) else k["pubkey"]
                    for k in tx["transaction"]["message"]["accountKeys"]]
            idx = keys.index(creator)
            meta = tx["meta"]
            # creator received SOL: find who lost it
            gain = meta["postBalances"][idx] - meta["preBalances"][idx]
            if gain > 0:
                for j, k in enumerate(keys):
                    if j == idx:
                        continue
                    loss = (meta["preBalances"][j]
                            - meta["postBalances"][j])
                    if loss >= gain:  # the source
                        funder = k
                        break
        except Exception:
            pass
    trace[creator] = {"funder": funder, "mint": m,
                      "n_sigs": len(sigs)}
    (MON / "funder_trace.json").write_text(json.dumps(trace, indent=1))
    print(f"{creator[:10]}… funder={str(funder)[:12]}…", flush=True)

# join with outcomes
print("\n=== funder clusters by outcome ===")
by_funder = collections.defaultdict(list)
for c, v in trace.items():
    m = v["mint"]
    p = positions.get(m, {})
    ret = p.get("ret")
    peak = p.get("peak") or 0
    cls = "RUG" if ret is not None and ret <= -0.9 else (
        "RUNNER" if peak >= 1.5 else "quiet")
    by_funder[v.get("funder")].append((cls, m[:8], ret, peak))
for f, rows in sorted(by_funder.items(), key=lambda kv: -len(kv[1])):
    print(f"funder {str(f)[:14]}… n={len(rows)}: "
          + ", ".join(f"{cls}({m},pk{pk})" for cls, m, ret, pk in rows))
