#!/usr/bin/env bash
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/1000/asterism_nested
export WAYLAND_DISPLAY=wayland-0
export DBUS_SESSION_BUS_ADDRESS=$(tr '\0' '\n' </proc/$(pgrep -n -x plasmashell)/environ | sed -n 's/^DBUS_SESSION_BUS_ADDRESS=//p' | head -1)
echo "bus=$DBUS_SESSION_BUS_ADDRESS"
echo "=== kscreen-doctor ==="
kscreen-doctor -o 2>&1 | head -100 || true
echo "=== wlr/randr if any ==="
command -v wlr-randr && wlr-randr 2>&1 | head -40 || true
echo "=== openvr ==="
ls /opt/steamvr/bin/linuxarm64/libopenvr_api.so 2>/dev/null
ls /usr/lib/python3*/site-packages/openvr* 2>/dev/null | head
find /opt/steamvr -name 'openvr_api*' 2>/dev/null | head
echo "=== dock overlay test help via strings ==="
strings /opt/steamvr/bin/linuxarm64/vrcmd | rg -i 'dock-overlay|theater|dashboard|world' | head -30
