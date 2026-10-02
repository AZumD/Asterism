#!/usr/bin/env bash
# Asterism installer (Milestone 0–1 + Phase C tooling; UI patch is separate).
# Usage: ./install.sh [--yes] [--dry-run] [--skip-backup]
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck disable=SC1091
. "$root/scripts/_env.sh"

assume_yes=0
dry_run=0
skip_backup=0
for arg in "$@"; do
  case $arg in
    --yes|-y) assume_yes=1 ;;
    --dry-run) dry_run=1 ;;
    --skip-backup) skip_backup=1 ;;
    -h|--help) sed -n '2,5p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

ask() {
  [ "$assume_yes" = 1 ] && return 0
  local answer
  read -r -p "$1 [y/N] " answer || answer=
  [[ ${answer:-n} =~ ^[Yy]$ ]]
}

echo "Asterism install"
echo "  root: $root"
echo "  version: $(asterism_version)"
echo "  SteamVR: $(steamvr_build_id)"
echo
echo "Installs: user units (dashboard+desktop WantedBy steamvr), ctl, displayctl,"
echo "          Desktop Settings launcher, default displays.json, UI backup."
echo "Does NOT: apply Phase C UI patch (use scripts/patch-steamvr-ui.sh),"
echo "          install OpenVR drivers, touch FrameTop, restart SteamVR."
echo

preflight_ok=1
[ -d "$STEAMVR_ROOT" ] || { echo "FAIL: no $STEAMVR_ROOT"; preflight_ok=0; }
command -v gamescope >/dev/null || { echo "FAIL: gamescope"; preflight_ok=0; }
command -v python3 >/dev/null || { echo "FAIL: python3"; preflight_ok=0; }
[ -f "$ASTERISM_MANIFEST" ] || { echo "FAIL: no manifest"; preflight_ok=0; }

# Compat: allow systemui.html drift only if already patched
if [ -f "$ASTERISM_MANIFEST" ]; then
  if ! python3 - "$ASTERISM_MANIFEST" "$ASTERISM_STATE_DIR/ui-patch-installed" <<'PY'
import json, hashlib, os, sys
m = json.load(open(sys.argv[1]))
patched = os.path.isfile(sys.argv[2])
live_sv = open("/opt/steamvr/bin/version.txt").read().strip() if os.path.isfile("/opt/steamvr/bin/version.txt") else ""
exp_sv = m.get("steamvr", {}).get("build_id", "")
if exp_sv and live_sv and exp_sv != live_sv:
    print(f"STOP: SteamVR build drift: {exp_sv} vs {live_sv}"); sys.exit(2)
for t in m.get("ui_targets", []):
    path, exp = t["path"], t["sha256"]
    if not os.path.isfile(path):
        print(f"STOP: missing {path}"); sys.exit(2)
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if h != exp:
        if patched and path.endswith("systemui.html"):
            print(f"NOTE: {path} differs (Phase C patch present) — OK for install")
            continue
        print(f"STOP: hash mismatch {path}"); print(f"  expected {exp}"); print(f"  actual   {h}"); sys.exit(2)
print("compat check OK")
PY
  then preflight_ok=0; fi
fi
[ "$preflight_ok" = 1 ] || exit 1

ask "Proceed with Asterism install?" || { echo aborted; exit 0; }
[ "$dry_run" = 1 ] && { echo "[dry-run] would install units/links/config"; exit 0; }

if [ "$skip_backup" = 1 ]; then
  ls "$ASTERISM_BACKUP_DIR"/*/MANIFEST.tsv >/dev/null 2>&1 || { echo "ERROR: no backup"; exit 1; }
else
  # Backup only if stock hashes still match (skip rewriting Valve tree when already patched)
  if [ ! -f "$ASTERISM_STATE_DIR/ui-patch-installed" ]; then
    "$root/scripts/backup-steamvr-ui.sh"
  else
    echo "Phase C patch present — skipping stock UI backup (already backed up pre-patch)"
  fi
fi

unit_dir=$HOME/.config/systemd/user
mkdir -p "$unit_dir" "$HOME/.local/bin" "$HOME/.local/share/applications" "$ASTERISM_CONFIG_DIR"

sed "s|@REPO@|$root|g" "$root/systemd/asterism-dashboard.service" > "$unit_dir/asterism-dashboard.service"
sed "s|@REPO@|$root|g" "$root/systemd/asterism-desktop.service" > "$unit_dir/asterism-desktop.service"
sed "s|@REPO@|$root|g" "$root/desktop-settings/asterism-desktop-settings.desktop" \
  > "$HOME/.local/share/applications/asterism-desktop-settings.desktop"

ln -sfn "$root/scripts/asterism-ctl.sh" "$HOME/.local/bin/asterism-ctl"
ln -sfn "$root/scripts/asterism-displayctl" "$HOME/.local/bin/asterism-displayctl"
chmod +x "$root"/scripts/*.sh "$root"/scripts/asterism-displayctl "$root"/desktop/*.sh \
  "$root"/dashboard/*.py "$root"/desktop-settings/*.py 2>/dev/null || true

if [ ! -f "$ASTERISM_CONFIG_DIR/asterism.conf" ]; then
  tr -d '\r' < "$root/conf/asterism.conf.example" > "$ASTERISM_CONFIG_DIR/asterism.conf"
fi
if [ ! -f "$ASTERISM_CONFIG_DIR/displays.json" ]; then
  python3 - <<PY
import sys
sys.path.insert(0, "$root/display")
from displays import default_config, save
from pathlib import Path
save(default_config(), Path("$ASTERISM_CONFIG_DIR/displays.json"))
print("wrote displays.json")
PY
fi

# Drop old default.target wants if present
rm -f "$unit_dir/default.target.wants/asterism-dashboard.service"
systemctl --user daemon-reload
systemctl --user enable asterism-dashboard.service asterism-desktop.service
# Start now if SteamVR is up
if systemctl --user is-active steamvr.service >/dev/null 2>&1; then
  systemctl --user start asterism-dashboard.service asterism-desktop.service || true
fi

asterism_log INFO "install completed"
echo "OK. Phase C UI patch (optional): $root/scripts/patch-steamvr-ui.sh --dry-run"
echo "Desktop Settings: asterism-desktop-settings or applications menu"
