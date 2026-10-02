#!/usr/bin/env bash
# Shared paths and helpers for Asterism scripts. Sourced, not executed.
set -euo pipefail

ASTERISM_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
export ASTERISM_ROOT

ASTERISM_STATE_DIR=${ASTERISM_STATE_DIR:-$HOME/.local/state/asterism}
ASTERISM_DATA_DIR=${ASTERISM_DATA_DIR:-$HOME/.local/share/asterism}
ASTERISM_CONFIG_DIR=${ASTERISM_CONFIG_DIR:-$HOME/.config/asterism}
ASTERISM_BACKUP_DIR=${ASTERISM_BACKUP_DIR:-$ASTERISM_DATA_DIR/backups}
ASTERISM_RUNTIME_DIR=${ASTERISM_RUNTIME_DIR:-${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/asterism}
ASTERISM_LOG_DIR=${ASTERISM_LOG_DIR:-$ASTERISM_STATE_DIR/logs}
ASTERISM_IPC_SOCK=${ASTERISM_IPC_SOCK:-$ASTERISM_RUNTIME_DIR/control.sock}
ASTERISM_MANIFEST=${ASTERISM_MANIFEST:-$ASTERISM_ROOT/compatibility/manifest.json}

STEAMVR_ROOT=${STEAMVR_ROOT:-/opt/steamvr}
STEAMVR_WEBUI=${STEAMVR_WEBUI:-$STEAMVR_ROOT/resources/webinterface/dashboard}
VRCMD=${VRCMD:-$STEAMVR_ROOT/bin/linuxarm64/vrcmd}
export LD_LIBRARY_PATH=${STEAMVR_ROOT}/bin/linuxarm64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}

mkdir -p "$ASTERISM_STATE_DIR" "$ASTERISM_DATA_DIR" "$ASTERISM_CONFIG_DIR" \
  "$ASTERISM_BACKUP_DIR" "$ASTERISM_RUNTIME_DIR" "$ASTERISM_LOG_DIR"

asterism_log() {
  local level=$1; shift
  local line="[$(date -Iseconds)] [$level] $*"
  printf '%s\n' "$line" | tee -a "$ASTERISM_LOG_DIR/asterism.log" >&2
}

asterism_version() {
  if [ -d "$ASTERISM_ROOT/.git" ] && command -v git >/dev/null 2>&1; then
    git -C "$ASTERISM_ROOT" rev-parse --short HEAD 2>/dev/null || echo "unknown"
  elif [ -f "$ASTERISM_ROOT/VERSION" ]; then
    cat "$ASTERISM_ROOT/VERSION"
  else
    echo "0.1.0-poc"
  fi
}

steamvr_build_id() {
  if [ -f "$STEAMVR_ROOT/bin/version.txt" ]; then
    tr -d '\r\n' < "$STEAMVR_ROOT/bin/version.txt"
  else
    echo "unknown"
  fi
}

steamos_build_id() {
  if [ -f /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    echo "${BUILD_ID:-unknown}"
  else
    echo "unknown"
  fi
}

# Files Asterism may patch in a later Phase C. Milestone 0 backs these up;
# Phase B does not modify them.
asterism_ui_targets() {
  cat <<'EOF'
/opt/steamvr/resources/webinterface/dashboard/systemui.html
/opt/steamvr/resources/webinterface/dashboard/systemui.js
/opt/steamvr/resources/webinterface/dashboard/chunk~2e670652e.js
/opt/steamvr/resources/webinterface/dashboard/chunk~8012d0c89.js
EOF
}

sha256_file() {
  sha256sum "$1" | awk '{print $1}'
}
