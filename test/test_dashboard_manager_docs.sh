#!/usr/bin/env bash
# Smoke-test asterism-dashboard-inspect offline pieces.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/asterism-dashboard-inspect --architecture | grep -q 'SetDockLocation'
python3 - <<'PY'
import json, subprocess, sys
from pathlib import Path
out = subprocess.check_output(
    [sys.executable, "scripts/asterism-dashboard-inspect", "--architecture"],
    text=True,
)
data = json.loads(out)
assert "presentation_enum" in data
assert "World" in data["presentation_enum"]["values"]
assert Path("docs/DASHBOARD_MANAGER.md").is_file()
text = Path("docs/OWNERSHIP_BOUNDARY.md").read_text()
assert "PermissionDenied" in text or "blocked" in text.lower()
print("OK")
PY
