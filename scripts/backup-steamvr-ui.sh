#!/usr/bin/env bash
# Backup SteamVR UI files Asterism may later modify.
# Usage: scripts/backup-steamvr-ui.sh [--dry-run]
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1091
. "$root/scripts/_env.sh"

dry_run=0
for arg in "$@"; do
  case $arg in
    --dry-run) dry_run=1 ;;
    -h|--help) sed -n '2,4p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

ts=$(date +%Y%m%dT%H%M%S)
dest=$ASTERISM_BACKUP_DIR/$ts
stamp_file=$ASTERISM_BACKUP_DIR/.last_backup

if [ -e "$dest" ]; then
  echo "ERROR: backup destination already exists: $dest" >&2
  exit 1
fi

missing=0
while IFS= read -r path; do
  [ -z "$path" ] && continue
  if [ ! -f "$path" ]; then
    echo "ERROR: target missing: $path" >&2
    missing=1
  fi
done < <(asterism_ui_targets)
[ "$missing" = 0 ] || exit 1

echo "Asterism SteamVR UI backup"
echo "  SteamVR build: $(steamvr_build_id)"
echo "  SteamOS build: $(steamos_build_id)"
echo "  Destination:   $dest"
echo

if [ "$dry_run" = 1 ]; then
  echo "[dry-run] would create:"
  while IFS= read -r path; do
    [ -z "$path" ] && continue
    echo "  $path -> $dest$path  sha256=$(sha256_file "$path")"
  done < <(asterism_ui_targets)
  exit 0
fi

mkdir -p "$dest"
manifest=$dest/MANIFEST.tsv
{
  printf 'original_path\tbackup_path\tsha256\tmode\tmtime\n'
  while IFS= read -r path; do
    [ -z "$path" ] && continue
    rel=${path#/}
    backup_path=$dest/$rel
    mkdir -p "$(dirname "$backup_path")"
    cp -a "$path" "$backup_path"
    mode=$(stat -c '%a' "$path")
    mtime=$(stat -c '%Y' "$path")
    hash=$(sha256_file "$path")
    copy_hash=$(sha256_file "$backup_path")
    if [ "$hash" != "$copy_hash" ]; then
      echo "ERROR: backup hash mismatch for $path" >&2
      exit 1
    fi
    printf '%s\t%s\t%s\t%s\t%s\n' "$path" "$backup_path" "$hash" "$mode" "$mtime"
  done < <(asterism_ui_targets)
} > "$manifest"

while IFS= read -r path; do
  [ -z "$path" ] && continue
  echo "backed up: $path"
done < <(asterism_ui_targets)

meta=$dest/META.json
ver=$(asterism_version | tr -d '\r\n')
sv=$(steamvr_build_id | tr -d '\r\n')
so=$(steamos_build_id | tr -d '\r\n')
python3 - "$meta" "$ts" "$sv" "$so" "$ver" "$ASTERISM_MANIFEST" <<'PY'
import json, sys
meta = {
  "timestamp": sys.argv[2],
  "steamvr_build_id": sys.argv[3],
  "steamos_build_id": sys.argv[4],
  "asterism_version": sys.argv[5],
  "compat_manifest": sys.argv[6],
}
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(meta, f, indent=2)
    f.write("\n")
PY

printf '%s\n' "$ts" > "$stamp_file"
asterism_log INFO "backup created $dest"
echo
echo "OK backup at $dest"
echo "manifest: $manifest"
