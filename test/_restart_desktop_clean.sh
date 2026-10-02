#!/usr/bin/env bash
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus

# Fix installed config CRLF
tr -d '\r' < ~/asterism/conf/asterism.conf.example > ~/.config/asterism/asterism.conf

# Sync fixed session scripts
cp -a ~/asterism/desktop/asterism-session.sh ~/asterism/desktop/asterism-session-inner.sh /tmp/ 2>/dev/null || true

systemctl --user stop asterism-desktop.service || true
sleep 2
pkill -TERM -f 'gamescope .*--vr-overlay-key asterism' 2>/dev/null || true
sleep 1

~/asterism/scripts/asterism-ctl.sh show
sleep 12
~/asterism/scripts/asterism-ctl.sh status
echo "=== overlays ==="
LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64 /opt/steamvr/bin/linuxarm64/vrcmd --overlays 2>/dev/null | rg "asterism" || true
echo "=== cmdline ==="
pgrep -af 'vr-overlay-key asterism' | head -3
echo "=== vrserver still up? ==="
pgrep -x vrserver && pgrep -x vrcompositor && echo OK
