#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Antho/Projects/Asterism
scp "$SRC/pointer/helper/asterism-openvr-owner.cpp" frame:asterism/pointer/helper/
scp "$SRC/scripts/asterism-gamescope-ctrl.sh" frame:asterism/scripts/
ssh frame 'bash -s' <<'REMOTE'
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
cd ~/asterism
sed -i 's/\r$//' pointer/helper/build.sh pointer/helper/asterism-openvr-owner.cpp scripts/asterism-gamescope-ctrl.sh
bash pointer/helper/build.sh
# Show IVROverlay version string from headers
grep -R "IVROverlay_" /opt/steamvr/tools/hellovr_vulkan_linux/src/openvr/headers/openvr.h | head -5 || true
grep 'IVROverlay_' /opt/steamvr/tools/hellovr_vulkan_linux/src/openvr/headers/openvr.h | head -10 || true

~/asterism/scripts/asterism-ctl.sh restart-desktop
# wait for socket up to 30s
for i in $(seq 1 60); do
  if [ -S "$XDG_RUNTIME_DIR/asterism/gamescope-openvr.sock" ]; then
    echo "SOCKET_UP i=$i"
    break
  fi
  sleep 0.5
done
ls -la "$XDG_RUNTIME_DIR/asterism/"
grep -i 'asterism-openvr-owner' ~/.local/state/asterism/logs/desktop.log | tail -10 || true

if [ ! -S "$XDG_RUNTIME_DIR/asterism/gamescope-openvr.sock" ]; then
  echo 'FAIL still no socket'
  exit 1
fi

KEY=$(./scripts/asterism-layout keys | python3 -c 'import json,sys; print(json.load(sys.stdin)[0])')
echo KEY=$KEY
VRCMD=/opt/steamvr/bin/linuxarm64/vrcmd
export LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64
$VRCMD --dock-overlay world "$KEY" || true
sleep 2

echo '=== owner inspect ==='
./scripts/asterism-gamescope-ctrl.sh inspect "$KEY" | tee ~/.local/state/asterism/logs/owner-inspect.json
echo '=== ONE set-test-absolute ==='
./scripts/asterism-gamescope-ctrl.sh set-test-absolute "$KEY" 0 1.5 -1.5 0 0 0 | tee ~/.local/state/asterism/logs/owner-setabs.json
sleep 3
echo '=== owner inspect +3s ==='
./scripts/asterism-gamescope-ctrl.sh inspect "$KEY" | tee ~/.local/state/asterism/logs/owner-after3s.json
echo '=== external live ==='
./scripts/asterism-layout live | tee ~/.local/state/asterism/logs/owner-external-after.json
echo PROOF_DONE
REMOTE
