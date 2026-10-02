#!/usr/bin/env bash
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
export LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
cd ~/asterism

echo '=== wait for overlay keys ==='
KEY=
for i in $(seq 1 60); do
  keys=$(./scripts/asterism-layout keys 2>/dev/null || echo '[]')
  KEY=$(python3 -c 'import json,sys; k=json.load(sys.stdin); print(k[0] if k else "")' <<<"$keys")
  if [ -n "$KEY" ]; then
    echo "keys ready i=$i KEY=$KEY"
    break
  fi
  sleep 1
done
if [ -z "$KEY" ]; then
  echo 'FAIL no keys'; ./scripts/asterism-layout keys; exit 1
fi

test -S "$XDG_RUNTIME_DIR/asterism/gamescope-openvr.sock"

VRCMD=/opt/steamvr/bin/linuxarm64/vrcmd
echo '=== dock world ==='
$VRCMD --dock-overlay world "$KEY" || true
sleep 2

echo '=== owner inspect ==='
./scripts/asterism-gamescope-ctrl.sh inspect "$KEY" | tee ~/.local/state/asterism/logs/owner-inspect.json
echo
echo '=== ONE set-test-absolute ==='
./scripts/asterism-gamescope-ctrl.sh set-test-absolute "$KEY" 0 1.5 -1.5 0 0 0 | tee ~/.local/state/asterism/logs/owner-setabs.json
echo
sleep 3
echo '=== owner inspect +3s ==='
./scripts/asterism-gamescope-ctrl.sh inspect "$KEY" | tee ~/.local/state/asterism/logs/owner-after3s.json
echo
echo '=== external live ==='
./scripts/asterism-layout live | tee ~/.local/state/asterism/logs/owner-external-after.json
echo
echo PROOF_DONE
