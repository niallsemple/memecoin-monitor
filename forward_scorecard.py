#!/usr/bin/env python3
"""Forward scorecard (REPORT.md §19/§31): pre-registered numbers for the
morning read and Pass 3. Read-only — never modifies books or strategy.

Scores:
  1. v6 (cluster+momentum) forward entries vs the momentum-only baseline
     (66% reach 2x, 29% dead) — the H10 criterion: >=30 entries beating it.
  2. Live cluster touch rate + live-hit peak distribution vs in-sample
     (46% hit-2x, median peak 1.84x).
  3. Reconstruction wedge watch: v4/v5/v6 realized results vs §14/§28
     reconstructed expectations.
  4. Pipeline health: cycles ok/error in last 24h of auto_log.md.
"""
import json
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
state = json.loads((ROOT / "state.json").read_text())["seen"]
now = datetime.now(timezone.utc)

print(f"=== FORWARD SCORECARD — {now:%Y-%m-%d %H:%M}Z ===\n")

# --- books ---
for v in ["v2", "v3", "v4", "v5", "v6"]:
    f = ROOT / f"paper_{v}.json"
    if not f.exists():
        continue
    b = json.loads(f.read_text())
    cash = b.get("cash", 0)
    pos = b.get("positions", {})
    closed = b.get("closed", [])
    start = b.get("bank_start", 1000)
    open_val = 0
    for k, p in pos.items():
        ent = state.get(k) or {}
        hist = ent.get("history") or []
        det = (ent.get("detect") or {}).get("mcap") or p.get("entry_mcap") or 1
        last = (hist[-1].get("mcap") if hist else None) or det
        open_val += p.get("size_gbp", 0) * p.get("remaining", 1) * (last / (p.get("entry_mcap") or det))
    bank = cash + open_val
    roi = (bank / start - 1) * 100
    print(f"[{v}] bank=£{bank:,.2f} ROI={roi:+.1f}% open={len(pos)} closed={len(closed)}")

# --- v6 forward detail (H10 pre-registered test) ---
v6 = json.loads((ROOT / "paper_v6.json").read_text())
print(f"\n[v6 H10 test] evaluations={len(v6.get('seen_done', {}))} "
      f"verdicts={dict(Counter(v6.get('seen_done', {}).values()))}")
entries = list(v6.get("positions", {}).items()) + [(c.get("key"), c) for c in v6.get("closed", [])]
print(f"[v6 H10 test] ENTRIES={len(entries)} (pre-registered target: >=30, beat 66% hit-2x / 29% dead)")
for k, p in entries:
    ent = state.get(k) or {}
    hist = ent.get("history") or []
    det = (ent.get("detect") or {}).get("mcap") or 1
    em = p.get("entry_mcap") or det
    peak = max([p.get("peak_mcap", 0)] + [h.get("mcap") or 0 for h in hist])
    print(f"  {k[7:19]} entry={em:,.0f} peak/entry={peak / em:.2f}x "
          f"{'HIT2x' if peak >= 2 * em else ''} pnl=£{p.get('pnl_gbp', 0):+.2f}")

# --- live cluster touches (trustworthy tags only: post-fix §27) ---
tags = [(k, v) for k, v in state.items()
        if isinstance(v.get("cluster"), dict) and "error" not in v["cluster"]
        and (v["cluster"].get("fix") or str(v.get("first_seen")) >= "2026-08-27T20:10")]
hits = [(k, v) for k, v in tags if v["cluster"].get("hit")]
print(f"\n[cluster live] trustworthy tags={len(tags)} hits={len(hits)} "
      f"({100 * len(hits) / max(1, len(tags)):.1f}% vs ~10% in-sample)")
peaks = []
for k, v in hits:
    det = (v.get("detect") or {}).get("mcap") or 1
    hist = v.get("history") or []
    peak = max([h.get("mcap") or 0 for h in hist] + [0]) / det
    age = (now - datetime.fromisoformat(hist[0]["t"])).total_seconds() / 60 if hist else 0
    peaks.append(peak)
    print(f"  HIT {k[7:19]} age={age:.0f}m peak={peak:.2f}x "
          f"wallets={[w[:8] for w in v['cluster']['hit']]}")
if peaks:
    import statistics
    flat = sum(1 for p in peaks if p < 1.4)
    print(f"  live-hit peaks: median={statistics.median(peaks):.2f}x "
          f"(in-sample 1.84x) | flat (<1.4x): {flat}/{len(peaks)}"
          + ("  << WATCH: decoupling risk if flat persists (§32)" if flat >= max(3, len(peaks) * 0.7) else ""))

# --- pipeline health, last 24h ---
log = (ROOT / "auto_log.md").read_text().splitlines()
ok = err = 0
cutoff = now - timedelta(hours=24)
for line in log:
    try:
        stamp = datetime.strptime(line[2:19], "%Y-%m-%d %H:%MZ").replace(tzinfo=timezone.utc)
    except Exception:
        continue
    if stamp < cutoff:
        continue
    if " | ok |" in line:
        ok += 1
    elif "error" in line:
        err += 1
print(f"\n[pipeline 24h] cycles ok={ok} error={err}")
