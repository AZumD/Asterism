#!/usr/bin/env bash
# Merge Asterism-friendly SteamVR dashboard overlay size limits into the user
# steamvr.vrsettings (does NOT touch /opt/steamvr).
#
# Stock SteamVR clamps floating overlay drag-resize with:
#   dashboard.scaleSliderMin = 0.75
#   dashboard.scaleSliderMax = 1.5
# That feels tiny for a world-space Linux desktop. We widen the range (FrameTop
# ft-screens allows ~0.15–6 m panel width; gamescope starts from PHYS_WIDTH).
#
# Usage: scripts/asterism-vrsettings.sh [--yes] [--dry-run] [install|status|uninstall]
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1091
. "$root/scripts/_env.sh"

assume_yes=0
dry_run=0
action=install
for arg in "$@"; do
  case $arg in
    --yes|-y) assume_yes=1 ;;
    --dry-run) dry_run=1 ;;
    install|status|uninstall) action=$arg ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown: $arg" >&2; exit 2 ;;
  esac
done

# Prefer the path SteamVR on Frame actually uses.
candidates=(
  "$HOME/.config/openvr/config/steamvr.vrsettings"
  "$HOME/.local/share/Steam/config/steamvr.vrsettings"
  "$HOME/.steam/steam/config/steamvr.vrsettings"
)
vrsettings=
for c in "${candidates[@]}"; do
  if [ -f "$c" ]; then vrsettings=$c; break; fi
done
if [ -z "$vrsettings" ]; then
  vrsettings=$HOME/.config/openvr/config/steamvr.vrsettings
fi

# Keys we own (restored on uninstall from .asterism-bak sibling).
SCALE_MIN=${ASTERISM_SCALE_SLIDER_MIN:-0.40}
SCALE_MAX=${ASTERISM_SCALE_SLIDER_MAX:-4.0}

ask() {
  [ "$assume_yes" = 1 ] && return 0
  local a
  read -r -p "$1 [y/N] " a || a=
  [[ ${a:-n} =~ ^[Yy]$ ]]
}

status() {
  echo "vrsettings: $vrsettings"
  if [ ! -f "$vrsettings" ]; then
    echo "  (file missing)"
    return 0
  fi
  python3 - "$vrsettings" <<'PY'
import json, sys
p = sys.argv[1]
d = json.loads(open(p, encoding="utf-8").read())
dash = d.get("dashboard") or {}
for k in ("scaleSliderMin", "scaleSliderMax", "desktopScale", "defaultTheaterScale"):
    print(f"  dashboard.{k} = {dash.get(k, '(unset)')}")
PY
}

install_settings() {
  echo "Will set dashboard.scaleSliderMin=$SCALE_MIN scaleSliderMax=$SCALE_MAX"
  echo "  in $vrsettings"
  echo "SteamVR may need a restart for floating resize limits to take effect."
  ask "Apply Asterism overlay size limits?" || { echo aborted; exit 0; }
  [ "$dry_run" = 1 ] && { echo "[dry-run] skip write"; exit 0; }
  mkdir -p "$(dirname "$vrsettings")"
  python3 - "$vrsettings" "$SCALE_MIN" "$SCALE_MAX" <<'PY'
import json, os, sys, tempfile
path, smin, smax = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
bak = path + ".asterism-bak"
if os.path.isfile(path) and not os.path.isfile(bak):
    open(bak, "wb").write(open(path, "rb").read())
    print(f"backed up -> {bak}")
data = {}
if os.path.isfile(path):
    data = json.loads(open(path, encoding="utf-8").read())
dash = data.setdefault("dashboard", {})
# Preserve originals once under asterism_* keys for uninstall.
if "asterism_prev_scaleSliderMin" not in dash and "scaleSliderMin" in dash:
    dash["asterism_prev_scaleSliderMin"] = dash["scaleSliderMin"]
if "asterism_prev_scaleSliderMax" not in dash and "scaleSliderMax" in dash:
    dash["asterism_prev_scaleSliderMax"] = dash["scaleSliderMax"]
dash["scaleSliderMin"] = smin
dash["scaleSliderMax"] = smax
data["dashboard"] = dash
dirn = os.path.dirname(path) or "."
fd, tmp = tempfile.mkstemp(dir=dirn, prefix=".steamvr-", suffix=".tmp")
with os.fdopen(fd, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=3)
    f.write("\n")
os.replace(tmp, path)
print(f"wrote {path}")
print(f"  scaleSliderMin={smin} scaleSliderMax={smax}")
PY
}

uninstall_settings() {
  ask "Restore previous dashboard scale slider limits?" || { echo aborted; exit 0; }
  [ "$dry_run" = 1 ] && { echo "[dry-run] skip"; exit 0; }
  [ -f "$vrsettings" ] || { echo "no $vrsettings"; exit 0; }
  python3 - "$vrsettings" <<'PY'
import json, os, sys, tempfile
path = sys.argv[1]
data = json.loads(open(path, encoding="utf-8").read())
dash = data.get("dashboard") or {}
if "asterism_prev_scaleSliderMin" in dash:
    dash["scaleSliderMin"] = dash.pop("asterism_prev_scaleSliderMin")
if "asterism_prev_scaleSliderMax" in dash:
    dash["scaleSliderMax"] = dash.pop("asterism_prev_scaleSliderMax")
data["dashboard"] = dash
dirn = os.path.dirname(path) or "."
fd, tmp = tempfile.mkstemp(dir=dirn, prefix=".steamvr-", suffix=".tmp")
with os.fdopen(fd, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=3)
    f.write("\n")
os.replace(tmp, path)
print(f"restored slider limits in {path}")
PY
}

case $action in
  status) status ;;
  install) install_settings; status ;;
  uninstall) uninstall_settings; status ;;
esac
