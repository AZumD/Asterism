#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Antho/Projects/Asterism
rsync -av \
  "$SRC/pointer/helper/asterism-openvr-owner.cpp" \
  "$SRC/pointer/helper/build.sh" \
  "$SRC/desktop/asterism-session.sh" \
  "$SRC/scripts/asterism-gamescope-ctrl.sh" \
  "$SRC/scripts/asterism-owner-transform-proof.sh" \
  frame:asterism/pointer/helper/ 2>/dev/null || true
# Explicit paths
scp "$SRC/pointer/helper/asterism-openvr-owner.cpp" frame:asterism/pointer/helper/
scp "$SRC/pointer/helper/build.sh" frame:asterism/pointer/helper/
scp "$SRC/desktop/asterism-session.sh" frame:asterism/desktop/
scp "$SRC/scripts/asterism-gamescope-ctrl.sh" frame:asterism/scripts/
scp "$SRC/scripts/asterism-owner-transform-proof.sh" frame:asterism/scripts/

ssh frame 'bash -s' <<'REMOTE'
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
cd ~/asterism
sed -i 's/\r$//' pointer/helper/build.sh desktop/asterism-session.sh scripts/asterism-gamescope-ctrl.sh scripts/asterism-owner-transform-proof.sh
chmod +x pointer/helper/build.sh scripts/asterism-gamescope-ctrl.sh scripts/asterism-owner-transform-proof.sh
bash pointer/helper/build.sh
test -f pointer/helper/build/asterism-openvr-owner.so

# Enable owner ctrl in conf (stock gamescope + LD_PRELOAD)
CONF=~/.config/asterism/asterism.conf
grep -q '^ASTERISM_OPENVR_CTRL=' "$CONF" 2>/dev/null && \
  sed -i 's/^ASTERISM_OPENVR_CTRL=.*/ASTERISM_OPENVR_CTRL=1/' "$CONF" || \
  echo 'ASTERISM_OPENVR_CTRL=1' >> "$CONF"
# Ensure experimental gamescope bin is NOT set
sed -i '/^ASTERISM_GAMESCOPE_BIN=/d' "$CONF" || true
echo '--- conf ---'
grep -E 'ASTERISM_|PHYS_|OVERLAY_' "$CONF" || true

echo '=== restart-desktop to load LD_PRELOAD owner so ==='
~/asterism/scripts/asterism-ctl.sh restart-desktop || true
sleep 8
# Wait for overlays + socket
for i in $(seq 1 40); do
  if [ -S "$XDG_RUNTIME_DIR/asterism/gamescope-openvr.sock" ]; then
    echo "ctrl socket up ($i)"
    break
  fi
  sleep 0.5
done
ls -la "$XDG_RUNTIME_DIR/asterism/" || true
pgrep -af 'gamescope .*asterism.desktop' | head -2
# Confirm LD_PRELOAD in process environ
GS=$(pgrep -n -f 'gamescope .*--vr-overlay-key asterism.desktop' || true)
if [ -n "$GS" ]; then
  tr '\0' '\n' < /proc/$GS/environ | grep -E 'ASTERISM_OPENVR|LD_PRELOAD' || echo 'no preload env visible'
fi

echo '=== keys / live ==='
./scripts/asterism-layout keys
./scripts/asterism-layout live | head -c 2000; echo

KEY=$(./scripts/asterism-layout keys | python3 -c 'import json,sys; print(json.load(sys.stdin)[0])')
echo "KEY=$KEY"
VRCMD=/opt/steamvr/bin/linuxarm64/vrcmd
export LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64

echo '=== dock world then owner inspect ==='
$VRCMD --dock-overlay world "$KEY" || true
sleep 2

if [ -S "$XDG_RUNTIME_DIR/asterism/gamescope-openvr.sock" ]; then
  echo '--- owner inspect ---'
  ./scripts/asterism-gamescope-ctrl.sh inspect "$KEY" || ./scripts/asterism-gamescope-ctrl.sh inspect
  echo '--- ONE set-test-absolute ---'
  ./scripts/asterism-gamescope-ctrl.sh set-test-absolute "$KEY" 0 1.5 -1.5 0 0 0 | tee ~/.local/state/asterism/logs/owner-setabs.json
  sleep 3
  echo '--- owner inspect after 3s ---'
  ./scripts/asterism-gamescope-ctrl.sh inspect "$KEY" | tee ~/.local/state/asterism/logs/owner-after3s.json
  echo '--- external live ---'
  ./scripts/asterism-layout live | tee ~/.local/state/asterism/logs/owner-external-after.json
else
  echo 'FAIL: control socket missing — check desktop.log for asterism-openvr-owner'
  tail -40 ~/.local/state/asterism/logs/desktop.log || true
  exit 1
fi
REMOTE
