#!/usr/bin/env bash
# Live place smoke test (continue on soft failures).
set -u
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
export LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64
VR=/opt/steamvr/bin/linuxarm64/vrcmd
PLACE=/home/steamos/asterism/pointer/helper/build/asterism-place
ROOT=/home/steamos/asterism

echo "==== apply layout ===="
"$ROOT/scripts/asterism-layout" apply --wait 30 2>&1 | tail -40
echo "==== overlays ===="
"$VR" --overlays 2>&1 | grep -E "asterism\.desktop\.app\.[23]'" || true
echo "==== head ===="
timeout 15 "$PLACE" head || true
echo "==== measure 2 ===="
timeout 45 "$PLACE" measure asterism.desktop.app.2 || true
echo "==== place 2 ===="
timeout 90 "$PLACE" place asterism.desktop.app.2 -0.441 0.0 -1.538 -16.0 0.0 0.0 || true
echo "==== measure after ===="
timeout 45 "$PLACE" measure asterism.desktop.app.2 || true
echo "==== overlays after ===="
"$VR" --overlays 2>&1 | grep -E "asterism\.desktop\.app\.[23]'" || true
