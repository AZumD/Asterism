#!/usr/bin/env bash
# TEMPORARY read-only: dump SystemUI dashboard-bar tab publish view for
# GamepadUI (valve.steam.gamepadui.bar) reorder investigation.
# Requires live asterism_shell.js with probe-taskbar + dashmgr HTTP.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}"

echo "== overlays (bar / asterism) =="
LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64 \
  /opt/steamvr/bin/linuxarm64/vrcmd --overlays 2>/dev/null \
  | rg -i 'gamepadui\.bar|asterism\.desktop\.app|system\.systemui' || true

echo "== asterism-dashmgr probe-taskbar =="
./scripts/asterism-dashmgr probe-taskbar | python3 -m json.tool
