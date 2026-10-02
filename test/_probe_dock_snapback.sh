#!/usr/bin/env bash
set -euo pipefail
cd ~/asterism
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
export LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64
VR=/opt/steamvr/bin/linuxarm64/vrcmd
key=$(./scripts/asterism-layout keys | python3 -c 'import json,sys; print(json.load(sys.stdin)[0])')

echo "Using $key"
"$VR" --hidedashboard || true
sleep 0.5
"$VR" --dock-overlay theater "$key"
sleep 0.8
"$VR" --dock-overlay dashboard "$key"
sleep 1.0
"$VR" --dock-overlay world "$key"
sleep 1.0
"$VR" --hidedashboard || true
sleep 1.0
echo "=== after float+hide ==="
"$VR" --overlays 2>&1 | rg "$key'"

echo "=== show dashboard (snap back?) ==="
"$VR" --showdashboard
sleep 2
"$VR" --overlays 2>&1 | rg "$key'"

echo "=== hide again ==="
"$VR" --hidedashboard || true
sleep 1
"$VR" --overlays 2>&1 | rg "$key'"

echo "=== dump-positions ==="
"$VR" --dump-positions 2>&1 | head -40
