#!/usr/bin/env bash
set -u
export LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
cp -f /tmp/layout.py /home/steamos/asterism/layout/layout.py 2>/dev/null || true
/home/steamos/asterism/scripts/asterism-layout apply --wait 25
echo "===="
/opt/steamvr/bin/linuxarm64/vrcmd --overlays 2>&1 | grep -E "asterism\.desktop\.app\.[23]'" || true
