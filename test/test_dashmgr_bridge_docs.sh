#!/usr/bin/env bash
# Offline docs smoke + require websocket symbols.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
from pathlib import Path
shell = Path("patches/asterism_shell.js").read_text(encoding="utf-8")
assert "ws://localhost:47832" in shell
assert "WebSocket connected" in shell
assert 'fetch(HTTP + "/dashmgr/poll"' not in shell
assert "new WebSocket" in shell
dash = Path("dashboard/asterism-dashboard.py").read_text(encoding="utf-8")
assert "start_websocket" in dash
assert "global _DASHMGR_PENDING" not in dash  # replaced by FIFO
assert "_DASHMGR_QUEUE" in dash
assert "WS_PORT" in dash
assert Path("dashboard/asterism_ws.py").is_file()
bridge = Path("scripts/patch-steamvr-dashmgr-bridge.sh").read_text(encoding="utf-8")
assert "4a33b035cadd9ee3c709247a20c8d6b8f983c9f62b18cb8b328e13383c04378b" in bridge
print("OK")
PY
