#!/usr/bin/env bash
# Talk to experimental Gamescope OpenVR control socket (ASTERISM_OPENVR_CTRL=1).
set -euo pipefail
sock=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/asterism/gamescope-openvr.sock
if [ ! -S "$sock" ]; then
  echo "error: control socket missing: $sock" >&2
  echo "Is ASTERISM_GAMESCOPE_BIN experimental + ASTERISM_OPENVR_CTRL=1?" >&2
  exit 1
fi
cmd=${*:-inspect}
printf '%s\n' "$cmd" | socat - UNIX-CONNECT:"$sock"
