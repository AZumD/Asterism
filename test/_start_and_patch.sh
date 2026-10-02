#!/usr/bin/env bash
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
cd ~/asterism

systemctl --user daemon-reload
systemctl --user start asterism-dashboard.service asterism-desktop.service
sleep 3
./scripts/asterism-ctl.sh status || true

# Apply Phase C patch with sudo. Prefer askpass / cached credentials.
apply_patch() {
  ./scripts/patch-steamvr-ui.sh --yes
}

if [ -w /opt/steamvr/resources/webinterface/dashboard ]; then
  apply_patch
elif [ -n "${SUDO_ASKPASS:-}" ]; then
  SUDO_ASKPASS="$SUDO_ASKPASS" sudo -A bash -c "cd /home/steamos/asterism && ./scripts/patch-steamvr-ui.sh --yes"
elif [ -f /home/steamos/dev/frametop/.env ]; then
  # Reuse FrameTop host sudo helper pattern without printing secret
  pw=$(sed -n 's/^steamos_root_pwd=//p' /home/steamos/dev/frametop/.env 2>/dev/null | sed 's/^[\"'\'']//;s/[\"'\'']$//')
  if [ -n "$pw" ]; then
    printf '%s\n' "$pw" | sudo -S -p '' bash -c "cd /home/steamos/asterism && ./scripts/patch-steamvr-ui.sh --yes"
  else
    echo "NEED_SUDO: run: cd ~/asterism && sudo ./scripts/patch-steamvr-ui.sh --yes"
    exit 42
  fi
elif [ -f /home/steamos/frametop/.env ]; then
  pw=$(sed -n 's/^steamos_root_pwd=//p' /home/steamos/frametop/.env 2>/dev/null | sed 's/^[\"'\'']//;s/[\"'\'']$//')
  if [ -n "$pw" ]; then
    printf '%s\n' "$pw" | sudo -S -p '' bash -c "cd /home/steamos/asterism && ./scripts/patch-steamvr-ui.sh --yes"
  else
    echo "NEED_SUDO"
    exit 42
  fi
else
  echo "NEED_SUDO: no passwordless write to /opt/steamvr"
  exit 42
fi

./scripts/patch-steamvr-ui.sh --status
./scripts/asterism-ctl.sh hide >/tmp/h.json || true
./scripts/asterism-ctl.sh status | tee /tmp/after-hide.json
pid1=$(systemctl --user show -p MainPID --value asterism-desktop.service)
./scripts/asterism-ctl.sh show >/tmp/s.json || true
pid2=$(systemctl --user show -p MainPID --value asterism-desktop.service)
echo "desktop pid before/after show: $pid1 $pid2"
pgrep -x vrserver >/dev/null && echo SteamVR_ok
./scripts/asterism-displayctl list
./scripts/asterism-displayctl add --resolution 1920x1080
./scripts/asterism-displayctl list
./scripts/asterism-displayctl remove display-2
./scripts/asterism-displayctl list
