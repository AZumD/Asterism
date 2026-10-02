#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Antho/Projects/Asterism
sed -i 's/\r$//' \
  "$SRC/pointer/helper/asterism-openvr-owner.cpp" \
  "$SRC/desktop/asterism-session.sh"
scp "$SRC/pointer/helper/asterism-openvr-owner.cpp" frame:asterism/pointer/helper/
scp "$SRC/desktop/asterism-session.sh" frame:asterism/desktop/
ssh frame bash -s <<'REMOTE'
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
export LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64
cd ~/asterism
sed -i 's/\r$//' pointer/helper/asterism-openvr-owner.cpp pointer/helper/build.sh desktop/asterism-session.sh
bash pointer/helper/build.sh
rm -f "$XDG_RUNTIME_DIR/asterism/gamescope-openvr.sock"
~/asterism/scripts/asterism-ctl.sh restart-desktop

echo '=== wait for live owner socket (overlay-gated) ==='
ok=0
for i in $(seq 1 120); do
  if [ -S "$XDG_RUNTIME_DIR/asterism/gamescope-openvr.sock" ]; then
    if out=$(python3 - <<PY
import socket
s=socket.socket(socket.AF_UNIX)
s.settimeout(3)
s.connect("$XDG_RUNTIME_DIR/asterism/gamescope-openvr.sock")
s.sendall(b"inspect\n")
print(s.recv(8000).decode())
s.close()
PY
); then
      echo "SOCK_OK i=$i"
      echo "$out" | head -c 500; echo
      ok=1
      break
    fi
  fi
  sleep 1
done
grep asterism-openvr-owner ~/.local/state/asterism/logs/desktop.log | tail -30 || true
if [ "$ok" != 1 ]; then
  echo FAIL_NO_SOCK
  exit 1
fi

for i in $(seq 1 60); do
  KEY=$(./scripts/asterism-layout keys | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d[0] if d else "")')
  [ -n "$KEY" ] && break
  sleep 1
done
echo KEY=$KEY
/opt/steamvr/bin/linuxarm64/vrcmd --dock-overlay world "$KEY" || true
sleep 2
./scripts/asterism-gamescope-ctrl.sh inspect "$KEY" | tee ~/.local/state/asterism/logs/owner-inspect.json
echo
./scripts/asterism-gamescope-ctrl.sh set-test-absolute "$KEY" 0 1.5 -1.5 0 0 0 | tee ~/.local/state/asterism/logs/owner-setabs.json
echo
sleep 3
./scripts/asterism-gamescope-ctrl.sh inspect "$KEY" | tee ~/.local/state/asterism/logs/owner-after3s.json
echo
./scripts/asterism-layout live | tee ~/.local/state/asterism/logs/owner-external-after.json
echo
echo PROOF_DONE
REMOTE
