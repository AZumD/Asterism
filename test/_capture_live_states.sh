#!/usr/bin/env bash
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
cd ~/asterism

echo '=== restart dashboard to load visibility-only code ==='
systemctl --user restart asterism-dashboard.service
sleep 2
systemctl --user is-active asterism-dashboard.service
# Prove new code has no apply spawn path in process... check source on disk
grep -n 'spawning asterism-layout' dashboard/asterism-dashboard.py && echo 'FAIL still has spawn' || echo 'OK no spawn in source'
grep -n 'Visibility/focus only' dashboard/asterism-dashboard.py

echo '=== layout.json ==='
./scripts/asterism-layout show

echo '=== LIVE A (current / freshly observed) ==='
mkdir -p ~/.local/state/asterism/logs/live-inspect
OUT=~/.local/state/asterism/logs/live-inspect
stamp=$(date -u +%Y%m%dT%H%M%SZ)
./scripts/asterism-layout live | tee "$OUT/${stamp}_A_current.json"

# B dashboard
KEY=$(./scripts/asterism-layout keys | python3 -c 'import json,sys; print(json.load(sys.stdin)[0])')
echo "Using KEY=$KEY"
VRCMD=/opt/steamvr/bin/linuxarm64/vrcmd
export LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}

echo '=== LIVE B dock dashboard ==='
$VRCMD --dock-overlay dashboard "$KEY" || true
sleep 1
./scripts/asterism-layout live | tee "$OUT/${stamp}_B_dashboard.json"

echo '=== LIVE C dock theater ==='
$VRCMD --dock-overlay theater "$KEY" || true
sleep 1
./scripts/asterism-layout live | tee "$OUT/${stamp}_C_theater.json"

echo '=== LIVE D float world ==='
$VRCMD --dock-overlay world "$KEY" || true
sleep 2
./scripts/asterism-layout live | tee "$OUT/${stamp}_D_world.json"

echo '=== wait 3s (no move) E ==='
sleep 3
./scripts/asterism-layout live | tee "$OUT/${stamp}_E_world_idle.json"

echo '=== also dump external inspect binary alone ==='
./pointer/helper/build/asterism-overlay-inspect json asterism.desktop.app.2 asterism.desktop.app.3 | tee "$OUT/${stamp}_raw_inspect.json"

echo DONE stamp=$stamp
ls -la "$OUT" | tail
