#!/usr/bin/env python3
"""Memo #36: measure fee-farming quality on OUR OWN live position series.

Uses lp_guardian.log lines:
  "nBXytBBf: active=-124 range=[-152,-96] tvl=$484,591 vol24=$3,671,267 feeY=0.002505SOL feeX=0"
Reconstructs per-interval fee accrual (dFeeY, reset-aware across claims via
lp_guardian_actions.jsonl), realized price move (|dActiveBin|), and pool vol24
drift. Outputs fee_quality_report.md: fee APR per hour, fee per unit price-vol,
and whether fee growth tracks volume or just time.
"""
import json, os, re, time, statistics

MON = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(MON, "lp_guardian.log")
ACT = os.path.join(MON, "lp_guardian_actions.jsonl")
POOL_KEY = "nBXytBBf"  # KNOTS-SOL live arm
POS_SOL = 0.77

LINE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2}) " + POOL_KEY +
    r": active=(-?\d+) range=\[(-?\d+),(-?\d+)\] tvl=\$([\d,]+) vol24=\$([\d,]+) feeY=([\d.]+)SOL feeX=([\d.]+)")

def main():
    day = time.strftime("%Y-%m-%d")
    rows = []
    for ln in open(LOG, errors="ignore"):
        m = LINE.search(ln)
        if not m:
            continue
        h, mi, s, ab, lo, hi, tvl, vol, fy, fx = m.groups()
        t = int(h) * 3600 + int(mi) * 60 + int(s)
        rows.append(dict(t=t, ab=int(ab), tvl=float(tvl.replace(",", "")),
                         vol=float(vol.replace(",", "")), fy=float(fy)))
    if len(rows) < 3:
        print("not enough guardian samples yet"); return

    claims = []
    if os.path.exists(ACT):
        for ln in open(ACT):
            try: a = json.loads(ln)
            except Exception: continue
            if a.get("kind") == "claim" and "rc=0" in a.get("out", "") or \
               (a.get("kind") == "claim" and "Success" in a.get("out", "")):
                claims.append(a)

    iv = []
    prev = None
    for r in rows:
        if prev:
            dt = r["t"] - prev["t"]
            if dt < -12 * 3600:  # midnight wrap in HH:MM:SS log
                dt += 86400
            if dt <= 0: prev = r; continue
            dfee = r["fy"] - prev["fy"]
            claimed = 0.0
            if dfee < -1e-9:  # a claim reset pending fees in between
                claimed = prev["fy"]; dfee = 0.0
            iv.append(dict(dt=dt, dfee=dfee, claimed=claimed,
                           d_ab=abs(r["ab"] - prev["ab"]),
                           in_range=prev["ab"] is not None))
        prev = r

    span_h = (rows[-1]["t"] - rows[0]["t"])
    if span_h < -12 * 3600:
        span_h += 86400
    span_h /= 3600
    tot_fee = sum(x["dfee"] for x in iv) + sum(x["claimed"] for x in iv)
    tot_move = sum(x["d_ab"] for x in iv)
    # binStep 100 => 1% per bin; price-vol in % ~= |dBin|
    apr_hr = tot_fee / POS_SOL / max(span_h, 1e-9) * 100
    out = []
    out.append(f"# Fee quality on our own live series — {POOL_KEY} (KNOTS-SOL)\n")
    out.append(f"- samples: {len(rows)} guardian passes over {span_h:.2f}h")
    out.append(f"- total fee accrued (incl. {sum(x['claimed'] for x in iv):.4f} SOL claimed mid-series): **{tot_fee:.4f} SOL**")
    out.append(f"- position: {POS_SOL} SOL -> realized **{apr_hr:.1f}%/hour = {apr_hr*24:.0f}%/day**")
    out.append(f"- total |active-bin| travel: {tot_move} bins ({tot_move}% price range swept at binStep 100)")
    if tot_move:
        out.append(f"- fee per unit price travel: {tot_fee/tot_move*1000:.3f} SOL per % moved")
    # rolling windows
    out.append("\n## Hourly windows\n")
    out.append("| window | dt(min) | fee (SOL) | %/hr on 0.77 | |bins| moved |")
    out.append("|---|---|---|---|---|")
    t0 = rows[0]["t"]; buckets = {}
    for x, r in zip(iv, rows[1:]):
        b = int((r["t"] - t0) // 3600)
        buckets.setdefault(b, [0, 0, 0])
        buckets[b][0] += x["dt"]; buckets[b][1] += x["dfee"] + x["claimed"]; buckets[b][2] += x["d_ab"]
    for b in sorted(buckets):
        dt, fee, mv = buckets[b]
        if dt < 60: continue
        out.append(f"| h{b} | {dt/60:.0f} | {fee:.4f} | {fee/POS_SOL/(dt/3600)*100:.1f}% | {mv} |")
    # volume correlation
    vols = [r["vol"] for r in rows]
    if len(set(vols)) > 1:
        # crude: corr between vol24 level and interval fee rate
        rates = [x["dfee"] / x["dt"] for x in iv if x["dt"] > 0]
        vv = vols[1:len(rates)+1]
        if len(vv) == len(rates) and statistics.pstdev(vv) > 0:
            mr, mv_ = statistics.mean(rates), statistics.mean(vv)
            cov = statistics.mean([(a-mr)*(b-mv_) for a, b in zip(rates, vv)])
            corr = cov / (statistics.pstdev(rates) * statistics.pstdev(vv)) if statistics.pstdev(rates) else 0
            out.append(f"\ncorr(vol24 level, fee rate) = {corr:+.2f}")
    open(os.path.join(MON, "fee_quality_report.md"), "w").write("\n".join(out) + "\n")
    print(f"fee_quality: {span_h:.1f}h, {tot_fee:.4f} SOL, {apr_hr*24:.0f}%/day, travel {tot_move} bins")

if __name__ == "__main__":
    main()
