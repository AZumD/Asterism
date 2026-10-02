#!/usr/bin/env bash
# Verify restart-desktop uses real user bus + session no longer exits 0 on stale gs.
set -euo pipefail
cd ~/asterism
sed -i 's/\r$//' \
  desktop/asterism-session.sh \
  desktop-settings/asterism_desktop_settings.py \
  dashboard/asterism-dashboard.py \
  scripts/asterism-ctl.sh \
  test/test_lifecycle.sh || true

bash test/test_lifecycle.sh

export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus

# Reload dashboard so restart-desktop handler is live
systemctl --user daemon-reload
systemctl --user restart asterism-dashboard.service
sleep 2

echo "=== status before ==="
./scripts/asterism-ctl.sh status | tee /tmp/ast-pre.json
grep -q '"desktop_running": true' /tmp/ast-pre.json

echo "=== restart-desktop via ctl (real bus) ==="
./scripts/asterism-ctl.sh restart-desktop | tee /tmp/ast-restart.json
grep -q '"ok": true' /tmp/ast-restart.json

# Wait for gamescope
for i in $(seq 1 40); do
  if pgrep -f '[g]amescope .*--vr-overlay-key asterism.desktop' >/dev/null; then
    echo "gamescope up after restart ($i)"
    break
  fi
  sleep 0.5
done
pgrep -f '[g]amescope .*--vr-overlay-key asterism.desktop' >/dev/null

echo "=== simulate nested private bus → host systemd-run (settings path) ==="
# Settings launches systemd-run with host_env (real user bus), not the nested bus.
env DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus \
  XDG_RUNTIME_DIR=/run/user/$(id -u) \
  systemd-run --user --collect --quiet \
    /bin/bash -lc '"$HOME/asterism/scripts/asterism-ctl.sh" status >/tmp/ast-host-run.json' \
  && echo "systemd-run host-env OK" || echo "systemd-run host-env FAIL"
test -f /tmp/ast-host-run.json && grep -q desktop_running /tmp/ast-host-run.json

echo "=== ensure after steamvr-healthy path in source ==="
grep -q 'focus_desktop_overlay' dashboard/asterism-dashboard.py
grep -q 'stale gamescope' desktop/asterism-session.sh
echo ALL_OK
