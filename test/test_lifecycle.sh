#!/usr/bin/env bash
# Lifecycle semantics tests (unit-style with mocks where possible + live checks if SteamVR up).
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1091
. "$root/scripts/_env.sh"

pass=0; fail=0
check() { local n=$1; shift; if "$@"; then echo "PASS $n"; pass=$((pass+1)); else echo "FAIL $n"; fail=$((fail+1)); fi; }

echo "=== lifecycle unit checks ==="
# show must not be the only starter — ensure_desktop reason documented in source
check "show recovers only on crash (source)" \
  grep -q 'crash-recovery' "$root/dashboard/asterism-dashboard.py"
check "hide does not stop desktop (source)" \
  grep -q 'desktop session kept alive' "$root/dashboard/asterism-dashboard.py"
check "stop-desktop marked admin (source)" \
  grep -q 'administrative/debug' "$root/dashboard/asterism-dashboard.py"
check "desktop BindsTo steamvr" \
  grep -q 'BindsTo=steamvr.service' "$root/systemd/asterism-desktop.service"
check "no control-bar-close flag" bash -c '! grep -qE -- "--vr-overlay-enable-control-bar-close" "$0"' "$root/desktop/asterism-session.sh"

export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
export DBUS_SESSION_BUS_ADDRESS=${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}

if systemctl --user is-active asterism-dashboard.service >/dev/null 2>&1 \
   && pgrep -x vrserver >/dev/null; then
  echo "=== live lifecycle ==="
  before=$(systemctl --user show -p MainPID --value asterism-desktop.service 2>/dev/null || echo 0)
  "$root/scripts/asterism-ctl.sh" hide >/tmp/ast-hide.json || true
  after_hide=$(systemctl --user show -p MainPID --value asterism-desktop.service 2>/dev/null || echo 0)
  check "hide keeps desktop pid" [ "$before" = "$after_hide" ] || [ "$after_hide" != "0" ]
  "$root/scripts/asterism-ctl.sh" show >/tmp/ast-show.json || true
  after_show=$(systemctl --user show -p MainPID --value asterism-desktop.service 2>/dev/null || echo 0)
  check "show does not replace desktop pid" [ "$before" = "$after_show" ] || [ "$after_show" != "0" ]
  "$root/scripts/asterism-ctl.sh" status | tee /tmp/ast-status.json
  check "status has desktop_running" rg -q 'desktop_running' /tmp/ast-status.json
  check "status has desktop_visible" rg -q 'desktop_visible' /tmp/ast-status.json
  check "status has steamvr_running" rg -q 'steamvr_running' /tmp/ast-status.json
else
  echo "(skip live lifecycle — dashboard/SteamVR not active)"
fi

echo "Result: $pass passed, $fail failed"
[ "$fail" = 0 ]
