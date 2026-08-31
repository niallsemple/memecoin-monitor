import subprocess, sys, threading, time

out_lines = []

def reader(pipe):
    for line in iter(pipe.readline, ''):
        out_lines.append(line)
        # Write to file in real-time
        with open('/tmp/track_live.txt', 'a') as f:
            f.write(line)
    pipe.close()

p = subprocess.Popen(
    [sys.executable, "xchain_track.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

t = threading.Thread(target=reader, args=(p.stdout,))
t.daemon = True
t.start()

try:
    p.wait(timeout=280)
except subprocess.TimeoutExpired:
    p.kill()
    p.wait()

# Give reader thread a moment to finish
time.sleep(1)

# Print what we got
for line in out_lines:
    print(line, end='')

print("\n--- END ---")
