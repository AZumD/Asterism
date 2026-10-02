#!/usr/bin/env bash
set -euo pipefail
ssh frame 'bash -s' <<'REMOTE'
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
ls -la $XDG_RUNTIME_DIR/asterism/ || true
pgrep -af 'gamescope .*asterism' || echo no_gs
systemctl --user is-active asterism-desktop.service || true
grep asterism-openvr-owner ~/.local/state/asterism/logs/desktop.log | tail -20 || true
# Restart desktop cleanly and wait for fresh socket
~/asterism/scripts/asterism-ctl.sh restart-desktop
# Owner so waits for overlays before bind — allow up to ~100s
for i in $(seq 1 120); do
  if [ -S $XDG_RUNTIME_DIR/asterism/gamescope-openvr.sock ]; then
    if python3 -c "import socket; s=socket.socket(socket.AF_UNIX); s.settimeout(2); s.connect('$XDG_RUNTIME_DIR/asterism/gamescope-openvr.sock'); s.sendall(b'inspect\n'); print(s.recv(400).decode()[:200]); s.close()" 2>/tmp/sockerr; then
      echo SOCK_OK i=$i
      break
    else
      echo "sock present but refuse i=$i $(cat /tmp/sockerr 2>/dev/null)"
    fi
  fi
  sleep 1
done
ls -la $XDG_RUNTIME_DIR/asterism/
grep asterism-openvr-owner ~/.local/state/asterism/logs/desktop.log | tail -20 || true
if [ ! -S $XDG_RUNTIME_DIR/asterism/gamescope-openvr.sock ]; then
  echo FAIL_NO_SOCK
  exit 1
fi
# wait keys
for i in $(seq 1 60); do
  k=$(~/asterism/scripts/asterism-layout keys | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d[0] if d else "")')
  [ -n "$k" ] && echo KEY=$k && break
  sleep 1
done
KEY=$(~/asterism/scripts/asterism-layout keys | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d[0] if d else "")')
export LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64
/opt/steamvr/bin/linuxarm64/vrcmd --dock-overlay world "$KEY" || true
sleep 2
~/asterism/scripts/asterism-gamescope-ctrl.sh inspect "$KEY" | tee ~/.local/state/asterism/logs/owner-inspect.json
echo
~/asterism/scripts/asterism-gamescope-ctrl.sh set-test-absolute "$KEY" 0 1.5 -1.5 0 0 0 | tee ~/.local/state/asterism/logs/owner-setabs.json
echo
sleep 3
~/asterism/scripts/asterism-gamescope-ctrl.sh inspect "$KEY" | tee ~/.local/state/asterism/logs/owner-after3s.json
echo
~/asterism/scripts/asterism-layout live | tee ~/.local/state/asterism/logs/owner-external-after.json
echo PROOF_DONE
REMOTE
