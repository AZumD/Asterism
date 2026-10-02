#!/usr/bin/env bash
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
cd ~/asterism

for i in $(seq 1 45); do
  pgrep -x plasmashell >/dev/null && break
  sleep 1
done
pid=$(pgrep -n -x plasmashell || true)
echo "pid=${pid:-none}"
if [ -z "${pid:-}" ]; then
  echo "no plasmashell yet"
  exit 1
fi
NESTED_BUS=$(tr '\0' '\n' <"/proc/$pid/environ" | awk -F= '$1=="DBUS_SESSION_BUS_ADDRESS"{print $2; exit}')
echo "nested=$NESTED_BUS"
env DBUS_SESSION_BUS_ADDRESS="$NESTED_BUS" \
  XDG_RUNTIME_DIR=/run/user/$(id -u)/asterism_nested \
  systemd-run --user --collect --quiet \
    -E XDG_RUNTIME_DIR=/run/user/$(id -u) \
    -E DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus \
    /bin/bash -lc 'systemctl --user is-active asterism-desktop.service'
echo HOST_ENV_OK
./scripts/asterism-ctl.sh status
echo "=== recent dashboard ensure/restart ==="
grep -E 'steamvr-up|desktop started|restarting|stale|ensure after|focus|showdashboard' \
  ~/.local/state/asterism/logs/dashboard.log | tail -20
