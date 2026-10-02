#!/usr/bin/env bash
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus

echo "=== desktop unit ==="
systemctl --user status asterism-desktop.service --no-pager -l | head -60 || true
echo "=== journal ==="
journalctl --user -u asterism-desktop.service -n 80 --no-pager || true
echo "=== desktop.log tail ==="
tail -80 ~/.local/state/asterism/logs/desktop.log || true
echo "=== steamvr ==="
systemctl --user is-active steamvr.service
pgrep -x vrserver; pgrep -x vrcompositor
echo "=== conf ==="
cat -A ~/.config/asterism/asterism.conf
echo "=== try start again ==="
systemctl --user start asterism-desktop.service || true
sleep 8
systemctl --user is-active asterism-desktop.service || true
pgrep -af 'vr-overlay-key asterism' || echo no-gamescope
LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64 /opt/steamvr/bin/linuxarm64/vrcmd --overlays 2>/dev/null | rg asterism || echo no-overlay
tail -30 ~/.local/state/asterism/logs/desktop.log || true
