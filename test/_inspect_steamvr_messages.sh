#!/usr/bin/env bash
set -euo pipefail
python3 <<'PY'
import pathlib, re
d = pathlib.Path("/opt/steamvr/resources/webinterface/dashboard/chunk~8012d0c89.js").read_text(errors="ignore")
msgs = sorted(set(m.group(1) for m in re.finditer(r'SendMessage\(\s*"([^"]+)"', d)))
handlers = sorted(set(m.group(1) for m in re.finditer(r'RegisterHandler\(\s*"([^"]+)"', d)))
print("SendMessage count", len(msgs))
for s in msgs[:80]:
    print(" SM", s)
print("RegisterHandler count", len(handlers))
for s in handlers[:80]:
    print(" RH", s)
PY
