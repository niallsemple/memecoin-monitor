import subprocess, sys, time, os
p = subprocess.Popen([sys.executable, "xchain_track.py"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
start = time.time()
output = []
try:
    while p.poll() is None and time.time() - start < 45:
        line = p.stdout.readline()
        if line:
            output.append(line)
            print(line, end="")
            sys.stdout.flush()
        else:
            time.sleep(0.5)
finally:
    p.kill()
    p.wait()
    for line in p.stdout:
        output.append(line)
        print(line, end="")
    with open("/tmp/track_captured.txt", "w") as f:
        f.writelines(output)
