#!/usr/bin/env bash
# Restore SteamVR UI files from an Asterism backup.
# Usage: scripts/restore-steamvr-ui.sh [--dry-run] [--yes] [BACKUP_ID]
# Default BACKUP_ID: most recent under ~/.local/share/asterism/backups/
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1091
. "$root/scripts/_env.sh"

dry_run=0
assume_yes=0
backup_id=""
for arg in "$@"; do
  case $arg in
    --dry-run) dry_run=1 ;;
    --yes|-y) assume_yes=1 ;;
    -h|--help) sed -n '2,5p' "$0"; exit 0 ;;
    *)
      if [ -n "$backup_id" ]; then
        echo "unexpected argument: $arg" >&2
        exit 2
      fi
      backup_id=$arg
      ;;
  esac
done

if [ -z "$backup_id" ]; then
  if [ -f "$ASTERISM_BACKUP_DIR/.last_backup" ]; then
    backup_id=$(tr -d '\r\n' < "$ASTERISM_BACKUP_DIR/.last_backup")
  else
    backup_id=$(find "$ASTERISM_BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort | tail -1 || true)
  fi
fi

[ -n "$backup_id" ] || { echo "ERROR: no backups found in $ASTERISM_BACKUP_DIR" >&2; exit 1; }
src=$ASTERISM_BACKUP_DIR/$backup_id
manifest=$src/MANIFEST.tsv
[ -d "$src" ] || { echo "ERROR: backup not found: $src" >&2; exit 1; }
[ -f "$manifest" ] || { echo "ERROR: missing manifest: $manifest" >&2; exit 1; }

echo "Asterism SteamVR UI restore"
echo "  Backup: $src"
echo
echo "Files that will be restored:"

declare -a lines=()
while IFS=$'\t' read -r original backup_path hash mode mtime; do
  [ "$original" = "original_path" ] && continue
  [ -z "$original" ] && continue
  lines+=("$original|$backup_path|$hash|$mode|$mtime")
  echo "  $original"
  echo "    from $backup_path"
  echo "    expected sha256=$hash mode=$mode"
done < "$manifest"

[ ${#lines[@]} -gt 0 ] || { echo "ERROR: empty manifest" >&2; exit 1; }

# Validate backup checksums before restoring
for entry in "${lines[@]}"; do
  IFS='|' read -r original backup_path hash mode mtime <<<"$entry"
  if [ ! -f "$backup_path" ]; then
    echo "ERROR: backup file missing: $backup_path" >&2
    exit 1
  fi
  got=$(sha256_file "$backup_path")
  if [ "$got" != "$hash" ]; then
    echo "ERROR: backup corrupted for $original" >&2
    echo "  expected $hash" >&2
    echo "  got      $got" >&2
    exit 1
  fi
done
echo
echo "Backup checksums OK."

if [ "$dry_run" = 1 ]; then
  echo "[dry-run] no files written."
  exit 0
fi

if [ "$assume_yes" != 1 ]; then
  read -r -p "Restore these files now? [y/N] " ans || ans=
  [[ ${ans:-n} =~ ^[Yy]$ ]] || { echo "aborted"; exit 0; }
fi

# Restoring into /opt/steamvr typically needs root.
need_root=0
for entry in "${lines[@]}"; do
  IFS='|' read -r original _ <<<"$entry"
  dir=$(dirname "$original")
  if [ ! -w "$dir" ] 2>/dev/null; then
    need_root=1
    break
  fi
done

do_restore() {
  for entry in "${lines[@]}"; do
    IFS='|' read -r original backup_path hash mode mtime <<<"$entry"
    cp -a "$backup_path" "$original"
    chmod "$mode" "$original" 2>/dev/null || true
    # Best-effort mtime restore
    touch -d "@$mtime" "$original" 2>/dev/null || true
    got=$(sha256_file "$original")
    if [ "$got" != "$hash" ]; then
      echo "ERROR: restore verification failed for $original" >&2
      exit 1
    fi
    echo "restored: $original"
  done
}

if [ "$need_root" = 1 ]; then
  echo "Note: writing under /opt/steamvr requires elevated privileges."
  if [ "$(id -u)" = 0 ]; then
    do_restore
  else
    # Export function body via a temp script for sudo
    tmp=$(mktemp)
    {
      echo '#!/usr/bin/env bash'
      echo 'set -euo pipefail'
      declare -p lines
      echo 'sha256_file() { sha256sum "$1" | awk "{print \$1}"; }'
      type do_restore | tail -n +2
      echo 'do_restore'
    } > "$tmp"
    chmod +x "$tmp"
    sudo bash "$tmp"
    rm -f "$tmp"
  fi
else
  do_restore
fi

asterism_log INFO "restored backup $backup_id"
echo "OK restore complete from $backup_id"
