#!/usr/bin/env bash
# Capture read-only asterism-layout live snapshots for dock-mode states A–E.
# Manual headset steps between captures; does NOT mutate transforms.
set -euo pipefail
root=${ASTERISM_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
# shellcheck disable=SC1091
. "$root/scripts/_env.sh"

out_dir=${1:-$ASTERISM_LOG_DIR/live-inspect}
mkdir -p "$out_dir"
stamp=$(date -u +%Y%m%dT%H%M%SZ)

capture() {
  local label=$1
  local f="$out_dir/${stamp}_${label}.json"
  echo "=== capture $label -> $f ==="
  "$root/scripts/asterism-layout" live | tee "$f"
  echo
}

cat <<'EOF'
Manual sequence (SteamVR + Asterism desktop running):

  A  panel freshly created (just after desktop start, before docking)
  B  panel docked on dashboard (vrcmd or SteamVR UI → dashboard)
  C  panel moved to theater
  D  panel manually floated to world
  E  panel moved/resized manually in world

Press Enter before each capture. Ctrl-C to abort.
EOF

for label in A_fresh B_dashboard C_theater D_world_float E_world_moved; do
  read -r -p "Ready for $label? [Enter] " _
  capture "$label"
done

echo "Wrote captures under $out_dir"
echo "Also dump configured layout:"
"$root/scripts/asterism-layout" show | tee "$out_dir/${stamp}_layout.json"
