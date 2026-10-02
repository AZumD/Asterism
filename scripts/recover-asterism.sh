#!/usr/bin/env bash
# Emergency Asterism recovery over SSH (no GUI required).
# Usage: scripts/recover-asterism.sh [--dry-run] [--yes] [--no-restart]
#
# Does NOT: reboot, reset headset, delete user data, touch FrameTop,
# uninstall unrelated OpenVR drivers, or wipe SteamVR config.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1091
. "$root/scripts/_env.sh"

dry_run=0
assume_yes=0
no_restart=0
for arg in "$@"; do
  case $arg in
    --dry-run) dry_run=1 ;;
    --yes|-y) assume_yes=1 ;;
    --no-restart) no_restart=1 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

run() {
  if [ "$dry_run" = 1 ]; then
    echo "[dry-run] $*"
  else
    eval "$@"
  fi
}

ask() {
  [ "$assume_yes" = 1 ] && return 0
  [ "$dry_run" = 1 ] && return 0
  local answer
  read -r -p "$1 [y/N] " answer || answer=
  [[ ${answer:-n} =~ ^[Yy]$ ]]
}

echo "Asterism emergency recovery"
echo "  repo: $ASTERISM_ROOT"
echo "  dry-run: $dry_run  no-restart: $no_restart"
echo
echo "This will:"
echo "  1. Disable Asterism user services"
echo "  2. Stop Asterism processes"
echo "  3. Confirm no Valve UI injection is active (Phase B installs none)"
echo "  4. Restore SteamVR UI from latest backup IF a patch marker exists"
echo "  5. Clear only Asterism temp/cache under ~/.local/state/asterism and runtime"
echo "  6. Optionally restart SteamVR (skipped with --no-restart)"
echo "It will NOT touch FrameTop, boot config, or unrelated OpenVR drivers."
echo

if ! ask "Continue?"; then
  echo "aborted"
  exit 0
fi

export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
export DBUS_SESSION_BUS_ADDRESS=${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}

echo "== 1. Disable Asterism user services =="
if systemctl --user cat asterism-dashboard.service >/dev/null 2>&1; then
  run "systemctl --user disable --now asterism-dashboard.service 2>/dev/null || true"
  echo "  asterism-dashboard.service: disable --now"
else
  echo "  asterism-dashboard.service: not installed"
fi
if systemctl --user cat asterism-desktop.service >/dev/null 2>&1; then
  # Desktop unit is on-demand (no WantedBy); stop only — do not disable
  run "systemctl --user stop asterism-desktop.service 2>/dev/null || true"
  echo "  asterism-desktop.service: stop"
else
  echo "  asterism-desktop.service: not installed"
fi
run "systemctl --user daemon-reload 2>/dev/null || true"

echo "== 2. Stop Asterism processes =="
# SIGTERM gamescope/session owned by Asterism first (clean OpenVR shutdown)
run "pkill -TERM -f '[g]amescope .*--vr-overlay-key asterism\\.desktop' 2>/dev/null || true"
run "pkill -TERM -f '[a]sterism-session' 2>/dev/null || true"
run "pkill -TERM -f '[a]sterism-dashboard' 2>/dev/null || true"
if [ "$dry_run" != 1 ]; then
  sleep 1
  pkill -KILL -f '[g]amescope .*--vr-overlay-key asterism\.desktop' 2>/dev/null || true
fi
echo "  process stop requested"

echo "== 3. UI injection status =="
patch_marker=$ASTERISM_STATE_DIR/ui-patch-installed
if [ -f "$patch_marker" ]; then
  echo "  patch marker present: $patch_marker"
  echo "  will restore SteamVR UI from latest backup"
else
  echo "  no Phase C patch marker (expected for Milestone 0 / Phase B)"
fi

echo "== 4. Restore Valve UI if patched =="
if [ -f "$patch_marker" ]; then
  if [ "$dry_run" = 1 ]; then
    echo "[dry-run] would run restore-steamvr-ui.sh --yes"
    echo "[dry-run] would remove /opt/steamvr/resources/webinterface/dashboard/asterism_shell.js"
  else
    "$root/scripts/restore-steamvr-ui.sh" --yes
    shell_js=/opt/steamvr/resources/webinterface/dashboard/asterism_shell.js
    if [ -f "$shell_js" ]; then
      if [ -w "$(dirname "$shell_js")" ]; then rm -f "$shell_js"
      else sudo rm -f "$shell_js"
      fi
      echo "  removed $shell_js"
    fi
    rm -f "$patch_marker"
  fi
else
  # Still verify backups exist for future use
  if [ -d "$ASTERISM_BACKUP_DIR" ] && ls "$ASTERISM_BACKUP_DIR"/*/MANIFEST.tsv >/dev/null 2>&1; then
    echo "  backups present; leaving Valve files untouched"
  else
    echo "  WARNING: no backups found under $ASTERISM_BACKUP_DIR"
  fi
  # Orphan inject file without marker
  shell_js=/opt/steamvr/resources/webinterface/dashboard/asterism_shell.js
  if [ -f "$shell_js" ]; then
    echo "  WARNING: orphan $shell_js present without patch marker"
  fi
fi

echo "== 5. Clear Asterism temporary/cache state only =="
run "rm -rf '$ASTERISM_RUNTIME_DIR'"
run "rm -f '$ASTERISM_LOG_DIR'/*.tmp 2>/dev/null || true"
# Do not delete historical logs or backups
echo "  cleared runtime $ASTERISM_RUNTIME_DIR"

echo "== 6. SteamVR restart =="
if [ "$no_restart" = 1 ]; then
  echo "  skipped (--no-restart)"
elif [ "$dry_run" = 1 ]; then
  echo "[dry-run] would: systemctl --user restart steamvr.service"
else
  if ask "Restart steamvr.service now?"; then
    if systemctl --user restart steamvr.service; then
      echo "  steamvr.service restart issued"
      sleep 2
      systemctl --user is-active steamvr.service || true
      pgrep -a vrserver | head -1 || echo "  DIAG: vrserver not running"
      pgrep -a vrcompositor | head -1 || echo "  DIAG: vrcompositor not running"
    else
      echo "  DIAG: steamvr.service restart failed"
      systemctl --user status steamvr.service --no-pager -l | tail -40 || true
      # Empty pending path is a known SteamOS black-screen cause (FrameTop lesson)
      pending=$HOME/.config/openvr/steamvr-pending.path
      if [ -e "$pending" ] && [ ! -s "$pending" ]; then
        echo "  DIAG: empty steamvr-pending.path detected (SteamVR path lookup can fail)"
        echo "  DIAG: remove it manually if SteamVR will not start: rm -f $pending"
      fi
    fi
  else
    echo "  SteamVR left running/stopped as-is"
  fi
fi

asterism_log INFO "recover-asterism completed dry_run=$dry_run"
echo
echo "OK recovery steps finished"
echo "Next: put headset on if needed, then: systemctl --user start steamvr.service"
echo "Status: $root/scripts/asterism-status.sh"
