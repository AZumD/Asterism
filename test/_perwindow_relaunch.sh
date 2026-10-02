#!/usr/bin/env bash
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
sed -i 's/\r$//' ~/asterism/desktop/asterism-session.sh
systemctl --user stop asterism-desktop.service 2>/dev/null || true
sleep 2
fusermount3 -u -z /run/user/1000/asterism_nested/doc 2>/dev/null || true
umount --recursive /run/user/1000/asterism_nested 2>/dev/null || true
rm -rf /run/user/1000/asterism_nested 2>/dev/null || true
~/asterism/scripts/asterism-ctl.sh show
sleep 15
~/asterism/scripts/asterism-ctl.sh status
echo "=== overlays ==="
LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64 /opt/steamvr/bin/linuxarm64/vrcmd --overlays 2>/dev/null | rg asterism || true
systemctl --user is-active asterism-desktop.service
pgrep -x vrserver >/dev/null && echo vrserver_ok
