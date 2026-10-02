#!/usr/bin/env bash
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
export LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64

echo "=== layout.json ==="
cat ~/.config/asterism/layout.json
echo "=== recent dashboard ==="
grep -E 'layout|dock|steamvr-up|dashboard-start|showdashboard' ~/.local/state/asterism/logs/dashboard.log | tail -40
echo "=== layout.log ==="
tail -30 ~/.local/state/asterism/logs/layout.log 2>/dev/null || echo '(none)'
echo "=== overlays now ==="
/opt/steamvr/bin/linuxarm64/vrcmd --overlays 2>&1 | rg 'asterism\.desktop\.app\.[0-9]+' | rg -v thumb | rg -v layer || true
echo "=== live keys ==="
cd ~/asterism && ./scripts/asterism-layout keys
echo "=== apply now (foreground) ==="
cd ~/asterism && ./scripts/asterism-layout apply --wait 30
sleep 2
echo "=== overlays after apply ==="
/opt/steamvr/bin/linuxarm64/vrcmd --overlays 2>&1 | rg 'asterism\.desktop\.app\.[0-9]+' | rg -v thumb | rg -v layer || true
