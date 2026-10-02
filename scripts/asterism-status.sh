#!/usr/bin/env bash
# Paste-friendly Asterism / SteamVR status for bug reports.
# Usage: scripts/asterism-status.sh
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1091
. "$root/scripts/_env.sh"

export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
export DBUS_SESSION_BUS_ADDRESS=${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}

section() { printf '\n== %s ==\n' "$1"; }

section "Asterism"
echo "version: $(asterism_version)"
echo "root: $ASTERISM_ROOT"
echo "commit: $(git -C "$ASTERISM_ROOT" rev-parse HEAD 2>/dev/null || echo n/a)"

section "Host"
echo "SteamOS: $(steamos_build_id)"
echo "SteamVR build: $(steamvr_build_id)"
[ -f /etc/os-release ] && grep -E '^(NAME|VERSION_ID|VARIANT_ID|BUILD_ID)=' /etc/os-release || true

section "UI modification"
if [ -f "$ASTERISM_STATE_DIR/ui-patch-installed" ]; then
  echo "UI patch: INSTALLED"
  cat "$ASTERISM_STATE_DIR/ui-patch-installed"
else
  echo "UI patch: not installed (Phase B uses OpenVR/gamescope only)"
fi

section "Compatibility hashes"
if [ -f "$ASTERISM_MANIFEST" ] && command -v python3 >/dev/null; then
  python3 - "$ASTERISM_MANIFEST" <<'PY'
import json, hashlib, sys, os
m = json.load(open(sys.argv[1]))
ok = True
for t in m.get("ui_targets", []):
    path = t["path"]
    exp = t["sha256"]
    if not os.path.isfile(path):
        print(f"MISSING {path}")
        ok = False
        continue
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    status = "OK" if h == exp else "MISMATCH"
    if h != exp:
        ok = False
    print(f"{status} {path}")
    print(f"  expected {exp}")
    print(f"  actual   {h}")
print("compat:", "match" if ok else "DRIFT — refuse Phase C auto-patch")
PY
else
  echo "manifest missing or no python3"
fi

section "Backups"
latest=""
if [ -f "$ASTERISM_BACKUP_DIR/.last_backup" ]; then
  latest=$(tr -d '\r\n' < "$ASTERISM_BACKUP_DIR/.last_backup")
fi
echo "backup dir: $ASTERISM_BACKUP_DIR"
echo "latest: ${latest:-none}"
ls -1 "$ASTERISM_BACKUP_DIR" 2>/dev/null | tail -5 || true

section "User services"
for unit in asterism-dashboard.service asterism-desktop.service steamvr.service; do
  en=$(systemctl --user is-enabled "$unit" 2>/dev/null || echo n/a)
  ac=$(systemctl --user is-active "$unit" 2>/dev/null || echo n/a)
  echo "$unit: enabled=$en active=$ac"
done

section "Processes"
pgrep -a '[a]sterism' || echo "(no asterism processes)"
pgrep -a '[g]amescope .*asterism' || echo "(no asterism gamescope)"
pgrep -a vrserver | head -2 || echo "vrserver: not running"
pgrep -a vrcompositor | head -2 || echo "vrcompositor: not running"
pgrep -a vrwebhelper | head -3 || echo "vrwebhelper/dashboard: not running"

section "Overlay (vrcmd)"
if [ -x "$VRCMD" ] && pgrep -x vrserver >/dev/null; then
  "$VRCMD" --overlays 2>/dev/null | rg -i 'asterism|system\.systemui|desktopgame' || echo "(no matching overlays)"
else
  echo "vrcmd unavailable or vrserver down"
fi

section "IPC"
if [ -S "$ASTERISM_IPC_SOCK" ]; then
  echo "socket: $ASTERISM_IPC_SOCK (present)"
else
  echo "socket: $ASTERISM_IPC_SOCK (absent)"
fi

section "Recent Asterism logs"
if [ -f "$ASTERISM_LOG_DIR/asterism.log" ]; then
  tail -n 40 "$ASTERISM_LOG_DIR/asterism.log"
else
  echo "(no log yet)"
fi
if [ -f "$ASTERISM_LOG_DIR/dashboard.log" ]; then
  echo "--- dashboard.log ---"
  tail -n 30 "$ASTERISM_LOG_DIR/dashboard.log"
fi
if [ -f "$ASTERISM_LOG_DIR/desktop.log" ]; then
  echo "--- desktop.log ---"
  tail -n 30 "$ASTERISM_LOG_DIR/desktop.log"
fi
