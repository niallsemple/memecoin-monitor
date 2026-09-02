import json, sys, urllib.request
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(sys.executable).parent.parent.parent))
from daimon_runtime import setup_plot
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

W = "CQcKkSee9bdHZ1bejYFDUXVtodbfKHe2KSx6AaAnTW2K"

# exit timestamps from trade log
sells = {}
for line in open("mfg_live_trades.jsonl"):
    r = json.loads(line)
    if r.get("action") == "pool_sell":
        sells[r["mint"]] = r["ts"]

d = json.load(open("live_positions.json"))
rows = []
for mint, p in d.items():
    if p["open"] or p.get("pnl_sol") is None:
        continue
    rows.append({
        "mint": mint[:8],
        "exit_t": sells.get(mint, p["entry_t"] + 900),
        "pnl": p["pnl_sol"],
        "reason": p.get("closed_reason", "?"),
    })
df = pd.DataFrame(rows).sort_values("exit_t").reset_index(drop=True)
df["cum"] = df["pnl"].cumsum()
df["t"] = pd.to_datetime(df["exit_t"], unit="s", utc=True).dt.tz_convert("Europe/London")

req = urllib.request.Request("https://api.mainnet-beta.solana.com",
    data=json.dumps({"jsonrpc":"2.0","id":1,"method":"getBalance","params":[W]}).encode(),
    headers={"Content-Type":"application/json"})
bal = json.load(urllib.request.urlopen(req, timeout=30))["result"]["value"] / 1e9

setup_plot()
fig, ax = plt.subplots(figsize=(10, 5.5))
colors = ["#d62728" if p < 0 else "#2ca02c" for p in df["pnl"]]
ax.bar(df["t"], df["pnl"], color=colors, alpha=0.45, width=0.02, label="per-trade PnL")
ax.plot(df["t"], df["cum"], marker="o", color="#1f77b4", lw=2, label="cumulative PnL")
for _, r in df[df["pnl"] < -0.05].iterrows():
    ax.annotate("DRAIN", (r["t"], r["cum"]), textcoords="offset points",
                xytext=(0, -14), ha="center", fontsize=8, color="#d62728")
ax.axhline(0, color="gray", lw=0.8, ls="--")
ax.set_title(f"Live memecoin book — {len(df)} closes, {int((df['pnl']>0).sum())} green | wallet {bal:.4f} SOL (funded 2.0)")
ax.set_ylabel("SOL")
ax.legend()
fig.autofmt_xdate()
fig.savefig("equity_curve.png", dpi=200, bbox_inches="tight")
print("wallet:", bal)
print(df[["mint","reason","pnl","cum"]].to_string())
