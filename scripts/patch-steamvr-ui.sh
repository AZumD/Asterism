#!/usr/bin/env bash
# Phase C: version-locked SteamVR systemui inject for Asterism Desktop shell control.
# Usage:
#   scripts/patch-steamvr-ui.sh --dry-run
#   scripts/patch-steamvr-ui.sh --yes
#   scripts/patch-steamvr-ui.sh --status
#   scripts/patch-steamvr-ui.sh --unpatch --yes
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1091
. "$root/scripts/_env.sh"

dry_run=0
assume_yes=0
do_unpatch=0
do_status=0
for arg in "$@"; do
  case $arg in
    --dry-run) dry_run=1 ;;
    --yes|-y) assume_yes=1 ;;
    --unpatch) do_unpatch=1 ;;
    --status) do_status=1 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

HTML=$STEAMVR_WEBUI/systemui.html
SHELL_JS_SRC=$root/patches/asterism_shell.js
SHELL_JS_DST=$STEAMVR_WEBUI/asterism_shell.js
MARKER='asterism_shell.js'
PATCH_MARKER=$ASTERISM_STATE_DIR/ui-patch-installed
INJECT_TAG='<script defer="defer" src="asterism_shell.js?contenthash=asterism1"></script>'

ask() {
  [ "$assume_yes" = 1 ] && return 0
  local a; read -r -p "$1 [y/N] " a || a=
  [[ ${a:-n} =~ ^[Yy]$ ]]
}

sha() { sha256sum "$1" | awk '{print $1}'; }

compat_check() {
  python3 - "$ASTERISM_MANIFEST" <<'PY'
import json, hashlib, os, sys
m = json.load(open(sys.argv[1]))
live = open("/opt/steamvr/bin/version.txt").read().strip() if os.path.isfile("/opt/steamvr/bin/version.txt") else ""
exp = m.get("steamvr", {}).get("build_id", "")
if exp and live and exp != live:
    print(f"STOP: SteamVR build drift manifest={exp} live={live}")
    sys.exit(2)
for t in m.get("ui_targets", []):
    path, exp_h = t["path"], t["sha256"]
    if not os.path.isfile(path):
        print(f"STOP: missing {path}"); sys.exit(2)
    # If already patched, systemui.html will differ — allow only that file to drift when marker present
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if h != exp_h:
        print(f"STOP: hash mismatch {path}")
        print(f"  expected {exp_h}")
        print(f"  actual   {h}")
        sys.exit(2)
print("compat OK")
PY
}

status() {
  echo "SteamVR build: $(steamvr_build_id)"
  echo "patch marker: $([ -f "$PATCH_MARKER" ] && echo yes || echo no)"
  echo "inject file: $([ -f "$SHELL_JS_DST" ] && echo present || echo absent) $SHELL_JS_DST"
  if [ -f "$HTML" ]; then
    if grep -Fq "$MARKER" "$HTML"; then
      echo "systemui.html: contains asterism_shell inject"
    else
      echo "systemui.html: stock (no asterism inject)"
    fi
    echo "systemui.html sha256: $(sha "$HTML")"
  fi
  if [ -f "$SHELL_JS_DST" ]; then
    echo "asterism_shell.js sha256: $(sha "$SHELL_JS_DST")"
  fi
  return 0
}

if [ "$do_status" = 1 ]; then
  status
  exit 0
fi

if [ "$do_unpatch" = 1 ]; then
  echo "Unpatch Asterism SteamVR UI"
  status
  if [ "$dry_run" = 1 ]; then
    echo "[dry-run] would restore systemui.html from backup and remove asterism_shell.js"
    exit 0
  fi
  ask "Restore Valve UI from latest backup and remove inject?" || { echo aborted; exit 0; }
  "$root/scripts/restore-steamvr-ui.sh" --yes
  if [ -f "$SHELL_JS_DST" ]; then
    if [ "$(id -u)" = 0 ]; then rm -f "$SHELL_JS_DST"
    else sudo rm -f "$SHELL_JS_DST"
    fi
  fi
  rm -f "$PATCH_MARKER"
  asterism_log INFO "UI unpatched"
  echo "OK unpatched. Clear ~/.cache/SteamVR/htmlcache and restart SteamVR manually if UI still shows Desktop."
  exit 0
fi

echo "Asterism Phase C UI patch"
echo "  SteamVR: $(steamvr_build_id)"
echo "  target:  $HTML + $SHELL_JS_DST"
echo

# If already patched, refresh asterism_shell.js (Asterism-owned) then exit.
if [ -f "$PATCH_MARKER" ] && grep -Fq "$MARKER" "$HTML" 2>/dev/null && [ -f "$SHELL_JS_DST" ]; then
  echo "Already patched — refreshing asterism_shell.js only."
  if [ "$dry_run" = 1 ]; then
    echo "[dry-run] would install $SHELL_JS_SRC -> $SHELL_JS_DST"
    status
    exit 0
  fi
  if [ -w "$(dirname "$SHELL_JS_DST")" ]; then
    install -m 0644 "$SHELL_JS_SRC" "$SHELL_JS_DST"
  else
    sudo install -m 0644 "$SHELL_JS_SRC" "$SHELL_JS_DST"
  fi
  echo "asterism_shell.js sha256: $(sha "$SHELL_JS_DST")"
  status
  exit 0
fi

echo "== Compatibility check =="
if ! compat_check; then
  echo "Refuse to patch. Update compatibility/manifest.json after deliberate review."
  exit 1
fi

echo "== Backup =="
if [ "$dry_run" = 1 ]; then
  "$root/scripts/backup-steamvr-ui.sh" --dry-run
else
  "$root/scripts/backup-steamvr-ui.sh"
  latest=$(tr -d '\r\n' < "$ASTERISM_BACKUP_DIR/.last_backup")
  "$root/scripts/restore-steamvr-ui.sh" --dry-run "$latest"
fi

echo "== Planned diff =="
echo "1. Install $SHELL_JS_DST from $SHELL_JS_SRC"
echo "2. Insert before </body> in systemui.html:"
echo "   $INJECT_TAG"
echo

if [ "$dry_run" = 1 ]; then
  echo "[dry-run] no files modified."
  exit 0
fi

ask "Apply Phase C SteamVR UI patch?" || { echo aborted; exit 0; }

install_files() {
  install -m 0644 "$SHELL_JS_SRC" "$SHELL_JS_DST"
  if grep -Fq "$MARKER" "$HTML"; then
    echo "systemui.html already contains inject tag"
  else
    # Insert before </body>
    python3 - "$HTML" "$INJECT_TAG" <<'PY'
import sys
path, tag = sys.argv[1], sys.argv[2]
text = open(path, "r", encoding="utf-8", errors="surrogateescape").read()
if "asterism_shell.js" in text:
    print("already injected")
    raise SystemExit(0)
needle = "</body>"
i = text.lower().rfind(needle)
if i < 0:
    raise SystemExit("no </body> in systemui.html")
# preserve original case of closing tag
end = text[i:i+len(needle)]
new = text[:i] + tag + end + text[i+len(needle):]
open(path, "w", encoding="utf-8", errors="surrogateescape").write(new)
print("injected")
PY
  fi
}

if [ -w "$(dirname "$HTML")" ]; then
  install_files
else
  tmp=$(mktemp -d)
  cp -a "$SHELL_JS_SRC" "$tmp/asterism_shell.js"
  cp -a "$HTML" "$tmp/systemui.html"
  MARKER="$MARKER" INJECT_TAG="$INJECT_TAG" python3 - "$tmp/systemui.html" "$INJECT_TAG" <<'PY'
import sys
path, tag = sys.argv[1], sys.argv[2]
text = open(path, "r", encoding="utf-8", errors="surrogateescape").read()
if "asterism_shell.js" in text:
    raise SystemExit(0)
i = text.lower().rfind("</body>")
if i < 0: raise SystemExit("no body")
end = text[i:i+7]
open(path,"w",encoding="utf-8",errors="surrogateescape").write(text[:i]+tag+end+text[i+7:])
PY
  sudo cp -a "$tmp/asterism_shell.js" "$SHELL_JS_DST"
  sudo cp -a "$tmp/systemui.html" "$HTML"
  rm -rf "$tmp"
fi

# Record patched state
{
  echo "installed=$(date -Iseconds)"
  echo "steamvr_build=$(steamvr_build_id)"
  echo "systemui.html=$(sha "$HTML")"
  echo "asterism_shell.js=$(sha "$SHELL_JS_DST")"
  echo "backup=$(tr -d '\r\n' < "$ASTERISM_BACKUP_DIR/.last_backup" 2>/dev/null || true)"
} > "$PATCH_MARKER"

# Update manifest patched hashes file for operators
python3 - "$root/compatibility/patched-hashes.json" "$HTML" "$SHELL_JS_DST" <<'PY'
import json,hashlib,sys,datetime
out, html, shell = sys.argv[1], sys.argv[2], sys.argv[3]
def h(p):
    return hashlib.sha256(open(p,"rb").read()).hexdigest()
obj={
  "updated": datetime.datetime.now().isoformat(timespec="seconds"),
  "files": {
    html: h(html),
    shell: h(shell),
  },
  "note": "Phase C inject; stock hashes remain in manifest.json ui_targets for pre-patch gate"
}
json.dump(obj, open(out,"w"), indent=2)
print("wrote", out)
PY

asterism_log INFO "Phase C UI patch applied"
echo
echo "OK patched."
status
echo
echo "Manual next steps (SteamVR was NOT restarted):"
echo "  1. rm -rf ~/.cache/SteamVR/htmlcache"
echo "  2. Restart SteamVR from the headset/SSH when convenient:"
echo "       systemctl --user restart steamvr.service"
echo "  3. Open dashboard — look for bottom-left Desktop control"
echo "Recover: $root/scripts/recover-asterism.sh --yes"
