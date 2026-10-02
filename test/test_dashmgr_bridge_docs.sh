#!/usr/bin/env bash
# Offline + Frame-oriented checks for dashmgr bridge tooling.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
from pathlib import Path
shell = Path("patches/asterism_shell.js").read_text(encoding="utf-8")
assert "runDashboardProbe" in shell
assert "m_mapLastRelativeTransformForDockLocation" in shell
assert "dashmgr/poll" in shell
assert "__ASTERISM_STEAMVR" in shell
dash = Path("dashboard/asterism-dashboard.py").read_text(encoding="utf-8")
assert "dashmgr_request" in dash
assert "/dashmgr/poll" in dash
assert "global _DASHMGR_PENDING" in dash
bridge = Path("scripts/patch-steamvr-dashmgr-bridge.sh").read_text(encoding="utf-8")
assert "4a33b035cadd9ee3c709247a20c8d6b8f983c9f62b18cb8b328e13383c04378b" in bridge
assert "window.__ASTERISM_STEAMVR" in bridge
assert "GetFramesWithAssociatedSummonKeys" in bridge
print("OK")
PY
