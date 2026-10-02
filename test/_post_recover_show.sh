#!/usr/bin/env bash
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus

# Wait for stop to finish
sleep 5
fusermount3 -u -z /run/user/1000/asterism_nested/doc 2>/dev/null || true
umount --recursive /run/user/1000/asterism_nested 2>/dev/null || true
rm -rf /run/user/1000/asterism_nested 2>/dev/null || true

systemctl --user enable asterism-dashboard.service
systemctl --user start asterism-dashboard.service
sleep 1
~/asterism/scripts/asterism-ctl.sh show
sleep 12
~/asterism/scripts/asterism-ctl.sh status
LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64 /opt/steamvr/bin/linuxarm64/vrcmd --overlays 2>/dev/null | rg 'asterism\.desktop' | head -10
pgrep -x vrserver >/dev/null && pgrep -x vrcompositor >/dev/null && echo SteamVR_healthy
echo "UI patch marker?" 
ls ~/.local/state/asterism/ui-patch-installed 2>/dev/null || echo none
sha256sum /opt/steamvr/resources/webinterface/dashboard/systemui.js | awk '{print $1}'
