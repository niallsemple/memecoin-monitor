import subprocess, sys, signal, os, time

p = subprocess.Popen([sys.executable, "xchain_track.py"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

try:
    stdout, _ = p.communicate(timeout=120)
    print(stdout)
except subprocess.TimeoutExpired:
    p.send_signal(signal.SIGTERM)
    time.sleep(2)
    if p.poll() is None:
        p.kill()
    stdout, _ = p.communicate()
    print(stdout)
    print("\n[TRACKER TIMED OUT AFTER 120s]")
