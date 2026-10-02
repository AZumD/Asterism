#!/usr/bin/env bash
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus

# Soft stop desktop if running
systemctl --user stop asterism-desktop.service 2>/dev/null || true
# Wait without SIGKILL storm if unit already dead
for i in $(seq 30); do
  pgrep -f 'vr-overlay-key asterism.desktop' >/dev/null || break
  sleep 0.5
done
# Clean leftover nested runtime (fuse)
fusermount3 -u -z /run/user/1000/asterism_nested/doc 2>/dev/null || true
umount --recursive /run/user/1000/asterism_nested 2>/dev/null || true
rm -rf /run/user/1000/asterism_nested 2>/dev/null || true

systemctl --user daemon-reload
~/asterism/scripts/asterism-ctl.sh show
sleep 15
~/asterism/scripts/asterism-ctl.sh status
echo "=== overlays ==="
LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64 /opt/steamvr/bin/linuxarm64/vrcmd --overlays 2>/dev/null | rg "asterism\\.desktop" || true
echo "=== size ==="
LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64 /opt/steamvr/bin/linuxarm64/vrcmd --overlays 2>/dev/null | rg "asterism\\.desktop'" -n || true
pgrep -af 'vr-overlay-key asterism.desktop' | head -2
systemctl --user is-active asterism-desktop.service
pgrep -x vrserver >/dev/null && pgrep -x vrcompositor >/dev/null && echo "SteamVR healthy"
