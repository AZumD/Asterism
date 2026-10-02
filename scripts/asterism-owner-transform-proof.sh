#!/usr/bin/env bash
# Owner-transform proof protocol (experimental Gamescope only).
# ONE set-test-absolute = ONE SetOverlayTransformAbsolute. No loops.
set -euo pipefail
root=${ASTERISM_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
# shellcheck disable=SC1091
. "$root/scripts/_env.sh"

log=$ASTERISM_LOG_DIR/owner-transform-proof.log
mkdir -p "$ASTERISM_LOG_DIR"
exec > >(tee -a "$log") 2>&1

echo "=== $(date -Iseconds) owner-transform proof ==="
echo "stock gamescope: $(command -v gamescope || true)"
echo "ASTERISM_GAMESCOPE_BIN=${ASTERISM_GAMESCOPE_BIN:-<unset>}"
echo "ASTERISM_OPENVR_CTRL=${ASTERISM_OPENVR_CTRL:-<unset>}"
if [ -f "$root/gamescope-asterism/BUILT_FROM_COMMIT" ]; then
  echo "experimental commit: $(cat "$root/gamescope-asterism/BUILT_FROM_COMMIT")"
fi

sock=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/asterism/gamescope-openvr.sock
if [ ! -S "$sock" ]; then
  echo "FAIL: control socket missing ($sock)."
  echo "Build experimental gamescope, set ASTERISM_GAMESCOPE_BIN + ASTERISM_OPENVR_CTRL=1,"
  echo "restart Asterism desktop only, then re-run."
  exit 1
fi

key=${1:-}
if [ -z "$key" ]; then
  keys=$("$root/scripts/asterism-layout" keys)
  key=$(python3 -c "import json,sys; k=json.load(sys.stdin); print(k[0] if k else '')" <<<"$keys")
fi
if [ -z "$key" ]; then
  echo "FAIL: no overlay key"
  exit 1
fi
echo "Using overlay key: $key"

echo "--- external live inspect ---"
"$root/scripts/asterism-layout" live || true

echo "--- owner inspect (before undock) ---"
"$root/scripts/asterism-gamescope-ctrl.sh" inspect "$key" || \
  "$root/scripts/asterism-gamescope-ctrl.sh" inspect

cat <<EOF
MANUAL: Use SteamVR / vrcmd to move THIS panel to World (undock), then press Enter.
  Example: vrcmd --dock-overlay world $key
EOF
read -r -p "[Enter when panel is in World] " _

echo "--- owner inspect (world, before set) ---"
"$root/scripts/asterism-gamescope-ctrl.sh" inspect "$key"

echo "--- ONE set-test-absolute (safe pose: 0 1.5 -1.5 0 0 0) ---"
"$root/scripts/asterism-gamescope-ctrl.sh" set-test-absolute "$key" 0 1.5 -1.5 0 0 0

echo "Observe headset: did the panel jump? Wait ~3s without further writes."
sleep 3
echo "--- owner inspect (3s later) ---"
"$root/scripts/asterism-gamescope-ctrl.sh" inspect "$key"

echo "--- external live inspect (after) ---"
"$root/scripts/asterism-layout" live || true

cat <<'EOF'
Record in docs/OWNERSHIP_BOUNDARY.md:
  - SetOverlayTransformAbsolute return code/name
  - transform type before/after
  - absolute readable?
  - visible headset motion?
  - SteamVR overwrite within 3s?
  - Conclusion A / B / C
EOF
echo "Log: $log"
