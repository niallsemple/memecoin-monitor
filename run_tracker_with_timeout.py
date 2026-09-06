import subprocess, sys, time, signal, os

# Run xchain_track.py and capture output for 240 seconds
proc = subprocess.Popen([sys.executable, "xchain_track.py"],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True)

try:
    outs, errs = proc.communicate(timeout=240)
    print(outs)
except subprocess.TimeoutExpired:
    proc.kill()
    outs, errs = proc.communicate()
    print(outs)
