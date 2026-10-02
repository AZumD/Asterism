#!/usr/bin/env bash
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
cd ~/asterism

echo "=== dashboard status ==="
systemctl --user status asterism-dashboard.service --no-pager | head -25

echo "=== ping ==="
./scripts/asterism-ctl.sh ping

echo "=== show ==="
./scripts/asterism-ctl.sh show

sleep 10

echo "=== status ==="
./scripts/asterism-ctl.sh status

echo "=== overlays (asterism) ==="
LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64 /opt/steamvr/bin/linuxarm64/vrcmd --overlays 2>/dev/null | rg -i 'asterism' || echo "(no asterism overlay yet)"

echo "=== overlays (gamescope/desktop) ==="
LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64 /opt/steamvr/bin/linuxarm64/vrcmd --overlays 2>/dev/null | rg -i 'asterism|desktopgame|Gamescope \(Thumb\)|systemui' | head -40

echo "=== desktop unit ==="
systemctl --user status asterism-desktop.service --no-pager | head -40 || true
journalctl --user -u asterism-desktop.service -n 50 --no-pager || true

echo "=== desktop.log ==="
tail -50 ~/.local/state/asterism/logs/desktop.log 2>/dev/null || true

echo "=== dashboard.log ==="
tail -30 ~/.local/state/asterism/logs/dashboard.log 2>/dev/null || true

echo "=== procs ==="
pgrep -af 'vr-overlay-key asterism' || echo "(no asterism gamescope)"
pgrep -af 'asterism-session' || true
