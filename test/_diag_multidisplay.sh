#!/usr/bin/env bash
set -euo pipefail
echo "=== displays ==="
cat ~/.config/asterism/displays.json
echo "=== gamescope asterism ==="
pgrep -af 'gamescope .*asterism' || true
echo "=== overlays ==="
LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64 /opt/steamvr/bin/linuxarm64/vrcmd --overlays 2>/dev/null | rg -i 'asterism|Gamescope|PerWindow|app\.' || true
echo "=== kwin wrapper ==="
cat /run/user/1000/asterism_nested/bin/kwin_wayland_wrapper 2>/dev/null || true
echo "=== kscreen ==="
kscreen-doctor -o 2>/dev/null | head -80 || true
echo "=== frametop gamescope layout apply ==="
grep -n 'gamescope\|dock-overlay\|PerWindow\|virtual-connector\|panel' ~/frametop/layout/ft_layout.py | head -50
grep -n 'gamescope\|dock\|theater\|theatre\|Dashboard\|apply' ~/frametop/session/frametop-session.sh | head -40
