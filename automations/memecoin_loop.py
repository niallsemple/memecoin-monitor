"""Memecoin paper-trading loop — runs monitor + v2 + v3 traders headlessly.

Each run executes the existing pipeline scripts in the project workspace
(they resolve all state paths relative to their own files), appends a status
line to memecoin-monitor/auto_log.md, and returns a summary artifact.

Expires after 2026-09-09 (two-week track-record window): later runs no-op.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path("/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor")
LOG = PROJECT / "auto_log.md"
EXPIRES = datetime(2026, 9, 9, 0, 0, tzinfo=timezone.utc)


def sh(args, timeout):
    try:
        p = subprocess.run(
            [sys.executable] + args,
            cwd=str(PROJECT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode, out.strip()
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except Exception as e:  # noqa: BLE001
        return 1, f"ERROR {e}"


def last_line(text, contains=""):
    lines = [l for l in text.splitlines() if l.strip()]
    if contains:
        lines = [l for l in lines if contains in l] or lines
    return lines[-1].strip() if lines else "(no output)"


def run(ctx):
    now = datetime.now(timezone.utc)
    if now >= EXPIRES:
        return {"artifact": {"status": "expired",
                             "details": "Two-week window ended 2026-09-09; disable this automation."}}

    # Single monitor cycle per run: the automation fires every 10 min anyway,
    # and the fast-watch rounds below provide intra-interval price coverage.
    # (The old "2 cycles x 130s" pattern left only ~20s of headroom for audit
    # work; stage-3/4 wallet calls pushed it past the 280s kill — §27.)
    rc1, mon = sh(["monitor.py", "1", "0", "6"], timeout=270)
    rc2, v2 = sh(["papertrader_v2.py"], timeout=120)
    rc3, v3 = sh(["papertrader_v3.py"], timeout=120)
    rc4, v4 = sh(["papertrader_v4.py"], timeout=120)
    rc5, v5 = sh(["papertrader_v5.py"], timeout=120)
    rc6, v6 = sh(["papertrader_v6.py"], timeout=120)

    # fast-watch loop: ~1-min price granularity for the hot set between
    # monitor cycles (attacks the 10-min fill wedge, REPORT.md §22).
    # Traders re-evaluate on each tick so exits/entries fire on fresh data.
    import time as _time
    for _ in range(3):
        _time.sleep(60)
        sh(["fastwatch.py"], timeout=60)
        rc2, v2 = sh(["papertrader_v2.py"], timeout=60)
        rc3, v3 = sh(["papertrader_v3.py"], timeout=60)
        rc4, v4 = sh(["papertrader_v4.py"], timeout=60)
        rc5, v5 = sh(["papertrader_v5.py"], timeout=60)
        rc6, v6 = sh(["papertrader_v6.py"], timeout=60)

    mon_line = last_line(mon)
    v2_line = last_line(v2, "v2")
    v3_line = last_line(v3, "v3")
    v4_line = last_line(v4, "v4")
    v5_line = last_line(v5, "v5")
    v6_line = last_line(v6, "v6")

    ok = rc1 == 0 and rc2 == 0 and rc3 == 0 and rc4 == 0 and rc5 == 0 and rc6 == 0
    status = "ok" if ok else f"error(rc={rc1},{rc2},{rc3},{rc4},{rc5},{rc6})"

    stamp = now.strftime("%Y-%m-%d %H:%MZ")
    try:
        with LOG.open("a") as f:
            f.write(f"- {stamp} | {status} | {mon_line} | {v2_line} | {v3_line} | {v4_line} | {v5_line} | {v6_line}\n")
    except Exception:
        pass

    tracked = 0
    try:
        state = json.loads((PROJECT / "state.json").read_text())
        tracked = len(state.get("seen", {}))
    except Exception:
        pass

    details = mon_line if ok else f"{mon_line} || {last_line(v2)} || {last_line(v3)} || {last_line(v4)} || {last_line(v5)} || {last_line(v6)}"
    return {"artifact": {
        "status": status,
        "v2": v2_line,
        "v3": v3_line,
        "v4": v4_line,
        "v5": v5_line,
        "v6": v6_line,
        "tracked": tracked,
        "details": details[:500],
    }}
