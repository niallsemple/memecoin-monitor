#!/usr/bin/env bash
# Idempotent wire-in: after exec_dry.py --once, run pattern_markout.py --once || true
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
LOOP="${1:-$ROOT/exec_dry_loop.sh}"
MARKER='python3 pattern_markout.py --once'

if [[ ! -f "$LOOP" ]]; then
  echo "missing loop: $LOOP" >&2
  exit 1
fi

if grep -qF "$MARKER" "$LOOP"; then
  echo "already wired: $LOOP"
  exit 0
fi

# Insert after the first exec_dry.py --once line (preserving || true style)
python3 - <<'PY' "$LOOP"
import pathlib, sys, re
path = pathlib.Path(sys.argv[1])
text = path.read_text()
lines = text.splitlines(keepends=True)
out = []
done = False
for line in lines:
    out.append(line)
    if (not done) and re.search(r'exec_dry\.py\s+--once', line):
        indent = re.match(r'^(\s*)', line).group(1)
        # Match surrounding || true pattern if present on exec_dry line
        if '|| true' in line or '||true' in line:
            out.append(f"{indent}python3 pattern_markout.py --once || true\n")
        else:
            out.append(f"{indent}python3 pattern_markout.py --once || true\n")
        done = True
if not done:
    # Append before final sleep/done if it's a while loop, else append at end
    out.append("\n# pattern observation (dry)\npython3 pattern_markout.py --once || true\n")
path.write_text(''.join(out))
print(f"wired pattern_markout into {path}")
PY
