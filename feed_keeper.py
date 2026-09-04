#!/usr/bin/env python3
"""Feed keeper (§280): dead-man switch for the birth feed.

The tracker automation passes are the feed writers (embedded pumpportal WS,
~19-min window every 20 min). When the interval scheduler slips (§274, §279),
curves.jsonl stops growing and the gap lasts until someone notices.

This daemon watches tape freshness every 60 s. If:
  - no tracker pass process is alive, AND
  - no keeper-spawned collector is running, AND
  - curves.jsonl is stale > STALE_S seconds,
it launches curve_collector.py (standalone PumpPortal birth collector) for
KEEP_MIN minutes so births keep landing on disk until the scheduler recovers,
and fires a macOS notification so the slip is visible.

It deliberately does NOT touch trading: entries/exits only happen inside real
passes. The keeper's job is preserving the raw backlog so the recovering pass
can re-evaluate what was born during the slip.
"""
import os, subprocess, time
from pathlib import Path

ROOT = Path(__file__).parent
CURVES = ROOT / "curves.jsonl"
LOG = ROOT / "feed_keeper.log"
STALE_S = 300        # normal inter-pass gap is ~1-3 min; 5 min = slipped
KEEP_MIN = 20        # covers one full interval; respawned if still stale
CHECK_S = 60
PASS_MARKER = "automation_3840d0e4"   # runner --module path contains this
COLLECTOR = ROOT / "curve_collector.py"


def _pgrep(pat):
    r = subprocess.run(["pgrep", "-f", pat], capture_output=True, text=True)
    return bool(r.stdout.strip())


def _log(msg):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())}Z {msg}"
    with LOG.open("a") as f:   # stdout is already redirected here by nohup
        f.write(line + "\n")


def _notify(title, body):
    try:
        subprocess.run(["osascript", "-e",
                        f'display notification "{body}" with title "{title}"'],
                       timeout=5, capture_output=True)
    except Exception:
        pass


def main():
    _log(f"feed_keeper start (stale>{STALE_S}s, keep={KEEP_MIN}min)")
    last_hb = 0
    while True:
        try:
            age = time.time() - os.path.getmtime(CURVES)
            pass_up = _pgrep(PASS_MARKER)
            keep_up = _pgrep(f"curve_collector.py")
            if not pass_up and not keep_up and age > STALE_S:
                _log(f"SLIP: feed stale {age:.0f}s, no pass — spawning "
                     f"collector for {KEEP_MIN} min")
                subprocess.Popen(
                    ["python3", "-u", str(COLLECTOR), str(KEEP_MIN)],
                    stdout=LOG.open("a"), stderr=subprocess.STDOUT,
                    cwd=str(ROOT), start_new_session=True)
                _notify("Memecoin feed keeper",
                        f"Scheduler slip: feed stale {age/60:.0f} min, "
                        f"backup collector started")
            if time.time() - last_hb > 3600:
                _log(f"hb: age={age:.0f}s pass_up={pass_up} keep_up={keep_up}")
                last_hb = time.time()
        except Exception as e:
            _log(f"error: {e}")
        time.sleep(CHECK_S)


if __name__ == "__main__":
    main()
