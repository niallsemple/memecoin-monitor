import subprocess, sys

p = subprocess.Popen(
    [sys.executable, "xchain_track.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

try:
    stdout, _ = p.communicate(timeout=280)
    print(stdout, end="")
except subprocess.TimeoutExpired:
    p.kill()
    stdout, _ = p.communicate()
    print(stdout, end="")
    print("\n--- TIMED OUT ---")
