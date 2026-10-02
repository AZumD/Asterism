#!/usr/bin/env bash
# Probe FrameTop-timing float; LF endings required.
set -eu
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
export LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64
VR=/opt/steamvr/bin/linuxarm64/vrcmd
key=asterism.desktop.app.2

show() { echo "=== $1 ==="; "$VR" --overlays 2>&1 | grep "$key'" || true; }

"$VR" --showdashboard || true
sleep 1
show "start"

"$VR" --dock-overlay theater "$key"
sleep 0.5
show "theater"

"$VR" --dock-overlay dashboard "$key"
sleep 0.8
show "dashboard"

"$VR" --dock-overlay world "$key"
sleep 0.8
show "world (dash open)"

"$VR" --hidedashboard || true
sleep 0.8
show "after hide"

"$VR" --dump-positions 2>&1 | head -30
