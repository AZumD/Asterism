#!/usr/bin/env bash
# Minimal hash-gated SteamVR chunk bridge for Asterism Dashboard Manager access.
# Exposes window.__ASTERISM_STEAMVR { yWq, getFramesForSummonKey } ONLY.
# Does NOT change Valve docking behavior.
#
# Usage:
#   scripts/patch-steamvr-dashmgr-bridge.sh --dry-run
#   scripts/patch-steamvr-dashmgr-bridge.sh --yes
#   scripts/patch-steamvr-dashmgr-bridge.sh --status
#   scripts/patch-steamvr-dashmgr-bridge.sh --unpatch --yes
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1091
. "$root/scripts/_env.sh"

CHUNK=$STEAMVR_WEBUI/chunk~8012d0c89.js
EXPECTED_BUILD=1790822802
EXPECTED_SHA=4a33b035cadd9ee3c709247a20c8d6b8f983c9f62b18cb8b328e13383c04378b
MARKER=$ASTERISM_STATE_DIR/dashmgr-bridge-installed

# Exact unique stock needle (must appear once).
NEEDLE='window.Dashboard=this,this.m_dashboardThumbnailsChangedEventHandle='
# Minimal exposure: Frame lookup + yWq enum. No behavior change.
BRIDGE='window.Dashboard=this,window.__ASTERISM_STEAMVR||(window.__ASTERISM_STEAMVR={version:1,yWq:i.yWq,getFramesForSummonKey:function(e){return M.JJ.GetFramesWithAssociatedSummonKeys(e)||[]}}),this.m_dashboardThumbnailsChangedEventHandle='

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
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

sha() { sha256sum "$1" | awk '{print $1}'; }

ask() {
  [ "$assume_yes" = 1 ] && return 0
  local a; read -r -p "$1 [y/N] " a || a=
  [[ ${a:-n} =~ ^[Yy]$ ]]
}

status() {
  echo "SteamVR build: $(steamvr_build_id)"
  echo "chunk: $CHUNK"
  if [ -f "$CHUNK" ]; then
    echo "chunk sha256: $(sha "$CHUNK")"
    if grep -Fq '__ASTERISM_STEAMVR' "$CHUNK"; then
      echo "bridge: PRESENT"
    else
      echo "bridge: absent"
    fi
    c_needle=$(grep -Fo "$NEEDLE" "$CHUNK" 2>/dev/null | wc -l | tr -d ' ')
    c_bridge=$(grep -Fo "$BRIDGE" "$CHUNK" 2>/dev/null | wc -l | tr -d ' ')
    echo "stock needle count: $c_needle"
    echo "bridge needle count: $c_bridge"
  else
    echo "chunk: MISSING"
  fi
  echo "marker: $([ -f "$MARKER" ] && echo yes || echo no)"
}

if [ "$do_status" = 1 ]; then
  status
  exit 0
fi

live_build=$(steamvr_build_id)
if [ "$live_build" != "$EXPECTED_BUILD" ]; then
  echo "STOP: SteamVR build mismatch expected=$EXPECTED_BUILD live=$live_build" >&2
  exit 2
fi

if [ ! -f "$CHUNK" ]; then
  echo "STOP: missing $CHUNK" >&2
  exit 2
fi

live_sha=$(sha "$CHUNK")

if [ "$do_unpatch" = 1 ]; then
  echo "Unpatch dashmgr bridge"
  status
  if [ "$dry_run" = 1 ]; then
    echo "[dry-run] would restore chunk from latest backup"
    exit 0
  fi
  ask "Restore chunk from Asterism backup (removes bridge)?" || { echo aborted; exit 0; }
  "$root/scripts/restore-steamvr-ui.sh" --yes
  rm -f "$MARKER"
  echo "OK unpatched (full UI restore). Clear htmlcache + restart SteamVR."
  exit 0
fi

# Already bridged?
if grep -Fq '__ASTERISM_STEAMVR' "$CHUNK"; then
  if grep -Fq "$BRIDGE" "$CHUNK"; then
    echo "Already bridged (exact match). Idempotent OK."
    status
    exit 0
  fi
  echo "STOP: chunk has unknown __ASTERISM_STEAMVR content; refuse fuzzy re-patch" >&2
  exit 2
fi

if [ "$live_sha" != "$EXPECTED_SHA" ]; then
  echo "STOP: chunk hash mismatch" >&2
  echo "  expected $EXPECTED_SHA" >&2
  echo "  actual   $live_sha" >&2
  exit 2
fi

# Count exact needle
count=$(python3 - "$CHUNK" "$NEEDLE" <<'PY'
import sys
path, needle = sys.argv[1], sys.argv[2]
data = open(path, "rb").read().decode("utf-8", "surrogateescape")
print(data.count(needle))
PY
)
if [ "$count" != "1" ]; then
  echo "STOP: stock needle count=$count (want 1); refuse patch" >&2
  exit 2
fi

echo "Asterism dashmgr bridge patch"
echo "  build: $live_build"
echo "  sha:   $live_sha"
echo "  needle count: 1 (OK)"
echo
echo "Replacement inserts window.__ASTERISM_STEAMVR={yWq,getFramesForSummonKey} after window.Dashboard=this"
echo

if [ "$dry_run" = 1 ]; then
  echo "[dry-run] would backup UI then apply exact byte replacement"
  "$root/scripts/backup-steamvr-ui.sh" --dry-run
  exit 0
fi

ask "Backup + apply minimal chunk bridge?" || { echo aborted; exit 0; }

"$root/scripts/backup-steamvr-ui.sh"
latest=$(tr -d '\r\n' < "$ASTERISM_BACKUP_DIR/.last_backup")
echo "backup id: $latest"

apply() {
  python3 - "$CHUNK" "$NEEDLE" "$BRIDGE" <<'PY'
import sys, hashlib
path, needle, bridge = sys.argv[1], sys.argv[2], sys.argv[3]
data = open(path, "rb").read().decode("utf-8", "surrogateescape")
n = data.count(needle)
if n != 1:
    raise SystemExit(f"needle count {n}")
if bridge in data:
    raise SystemExit("bridge already present")
new = data.replace(needle, bridge, 1)
open(path, "w", encoding="utf-8", errors="surrogateescape").write(new)
print("patched sha256", hashlib.sha256(open(path, "rb").read()).hexdigest())
PY
}

if [ -w "$CHUNK" ]; then
  apply
else
  tmp=$(mktemp)
  cp -a "$CHUNK" "$tmp"
  CHUNK=$tmp NEEDLE="$NEEDLE" BRIDGE="$BRIDGE" python3 - "$tmp" "$NEEDLE" "$BRIDGE" <<'PY'
import sys, hashlib
path, needle, bridge = sys.argv[1], sys.argv[2], sys.argv[3]
data = open(path, "rb").read().decode("utf-8", "surrogateescape")
if data.count(needle) != 1:
    raise SystemExit("needle count")
new = data.replace(needle, bridge, 1)
open(path, "w", encoding="utf-8", errors="surrogateescape").write(new)
print("tmp sha256", hashlib.sha256(open(path, "rb").read()).hexdigest())
PY
  sudo cp -a "$tmp" "$CHUNK"
  rm -f "$tmp"
fi

# Verify
if ! grep -Fq "$BRIDGE" "$CHUNK"; then
  echo "ERROR: bridge string missing after patch; restore immediately" >&2
  "$root/scripts/restore-steamvr-ui.sh" --yes "$latest"
  exit 1
fi
if grep -Fq "$NEEDLE" "$CHUNK"; then
  echo "ERROR: stock needle still present" >&2
  "$root/scripts/restore-steamvr-ui.sh" --yes "$latest"
  exit 1
fi

patched_sha=$(sha "$CHUNK")
{
  echo "installed=$(date -Iseconds)"
  echo "steamvr_build=$live_build"
  echo "original_sha=$EXPECTED_SHA"
  echo "patched_sha=$patched_sha"
  echo "backup=$latest"
} > "$MARKER"

asterism_log INFO "dashmgr chunk bridge applied sha=$patched_sha"
echo "OK bridged. patched sha256=$patched_sha"
echo "Clear ~/.cache/SteamVR/htmlcache and restart SteamVR."
status
