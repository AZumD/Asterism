#!/usr/bin/env bash
# Phase B smoke checks (requires SteamVR running; does not restart SteamVR).
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1091
. "$root/scripts/_env.sh"

export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
export DBUS_SESSION_BUS_ADDRESS=${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}

pass=0; fail=0
check() {
  local n=$1; shift
  if "$@"; then echo "PASS: $n"; pass=$((pass+1)); else echo "FAIL: $n"; fail=$((fail+1)); fi
}

echo "=== Phase B smoke ==="
check "vrserver running" pgrep -x vrserver >/dev/null
check "dashboard unit active" systemctl --user is-active asterism-dashboard.service >/dev/null
check "IPC ping" "$root/scripts/asterism-ctl.sh" ping >/tmp/asterism-ping.json

echo "Starting desktop via show (may take ~10s)..."
"$root/scripts/asterism-ctl.sh" show | tee /tmp/asterism-show.json
sleep 5
check "gamescope asterism running" pgrep -f "[g]amescope .*--vr-overlay-key asterism\\.desktop" >/dev/null
if [ -x "$VRCMD" ]; then
  "$VRCMD" --overlays 2>/dev/null | tee /tmp/asterism-overlays.txt >/dev/null || true
  check "overlay key in vrcmd" rg -q "asterism\\.desktop" /tmp/asterism-overlays.txt
fi

"$root/scripts/asterism-ctl.sh" status | tee /tmp/asterism-status-ipc.json
"$root/scripts/asterism-ctl.sh" hide | tee /tmp/asterism-hide.json || true

echo
echo "Result: $pass passed, $fail failed"
[ "$fail" = 0 ]
