#!/usr/bin/env bash
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus

echo "=== unit children ==="
systemctl --user status asterism-desktop.service --no-pager | head -50
echo "=== hide ==="
~/asterism/scripts/asterism-ctl.sh hide
sleep 1
~/asterism/scripts/asterism-ctl.sh status
echo "=== toggle ==="
~/asterism/scripts/asterism-ctl.sh toggle
sleep 2
~/asterism/scripts/asterism-ctl.sh status
echo "=== overlays again ==="
LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64 /opt/steamvr/bin/linuxarm64/vrcmd --overlays 2>/dev/null | rg "asterism\\.desktop'" 
echo "=== recover dry ==="
~/asterism/scripts/recover-asterism.sh --dry-run --yes --no-restart | tail -20
echo "=== stop desktop (soft) ==="
~/asterism/scripts/asterism-ctl.sh stop-desktop
sleep 3
~/asterism/scripts/asterism-ctl.sh status
pgrep -af 'vr-overlay-key asterism' || echo "asterism gamescope gone"
pgrep -x vrserver >/dev/null && pgrep -x vrcompositor >/dev/null && echo "SteamVR still healthy after stop"
# FrameTop untouched?
systemctl --user is-active frametop-desktop.service 2>/dev/null || echo "frametop-desktop: n/a"
pgrep -af 'ft-screens|frametop' | head -5 || echo "no frametop desktop procs (ok)"
