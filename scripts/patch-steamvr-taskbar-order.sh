#!/usr/bin/env bash
# Narrow hash-gated PoC: Asterism-specific dashboard-bar tab publish order.
# Layers on the known-safe dashmgr bridge v1 chunk (does NOT regenerate bridge).
#
# Changes only Dt[] used by Pt() in Dashboard.updateVRGamepadUIPathProperties:
#   Steam(14) -> asterism.desktop.app.* overlays -> appid(33) -> other overlays
#   -> Display(15) -> hwnd
#
# Usage:
#   scripts/patch-steamvr-taskbar-order.sh --dry-run
#   scripts/patch-steamvr-taskbar-order.sh --yes
#   scripts/patch-steamvr-taskbar-order.sh --status
#   scripts/patch-steamvr-taskbar-order.sh --unpatch --yes
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1091
. "$root/scripts/_env.sh"

CHUNK=$STEAMVR_WEBUI/chunk~8012d0c89.js
EXPECTED_BUILD=1790822802
INPUT_SHA=272c1e40f75bafe28a7108485295681ffdac2a322a6a10f3e2d35278d596dfd9
OUTPUT_SHA=047c1d4ef8110849da024ed34948370dc92f572bc06e4c1de3f5b81fc4bccb8e
MARKER=$ASTERISM_STATE_DIR/taskbar-order-installed

OLD_DT='Dt=[e=>{var t;return 14==(null===(t=e.icon())||void 0===t?void 0:t.enum())},e=>{var t;return 33==(null===(t=e.icon())||void 0===t?void 0:t.enum())},e=>{var t;return null!=(null===(t=e.icon())||void 0===t?void 0:t.overlay())},e=>{var t;return 15==(null===(t=e.icon())||void 0===t?void 0:t.enum())},e=>{var t;return null!=(null===(t=e.icon())||void 0===t?void 0:t.hwnd())}];'
NEW_DT='Dt=[e=>{var t;return 14==(null===(t=e.icon())||void 0===t?void 0:t.enum())},e=>{var t;return null!=(null===(t=e.icon())||void 0===t?void 0:t.overlay())&&0===String(t.overlay()).indexOf("asterism.desktop.app.")},e=>{var t;return 33==(null===(t=e.icon())||void 0===t?void 0:t.enum())},e=>{var t;return null!=(null===(t=e.icon())||void 0===t?void 0:t.overlay())&&0!==String(t.overlay()).indexOf("asterism.desktop.app.")},e=>{var t;return 15==(null===(t=e.icon())||void 0===t?void 0:t.enum())},e=>{var t;return null!=(null===(t=e.icon())||void 0===t?void 0:t.hwnd())}];'
BRIDGE_V1='window.__ASTERISM_STEAMVR||(window.__ASTERISM_STEAMVR={version:1,yWq:i.yWq,getFramesForSummonKey:function(e){return M.JJ.GetFramesWithAssociatedSummonKeys(e)||[]}})'

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
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

sha() { sha256sum "$1" | awk '{print $1}'; }

ask() {
  [ "$assume_yes" = 1 ] && return 0
  local a; read -r -p "$1 [y/N] " a || a=
  [[ ${a:-n} =~ ^[Yy]$ ]]
}

READONLY_WAS_DISABLED=0
reenable_readonly() {
  if [ "$READONLY_WAS_DISABLED" != 1 ]; then
    return 0
  fi
  if ! command -v steamos-readonly >/dev/null 2>&1; then
    return 0
  fi
  echo "== re-enable steamos-readonly =="
  sudo steamos-readonly enable
  READONLY_WAS_DISABLED=0
}

count_str() {
  python3 - "$1" "$2" <<'PY'
import sys
path, needle = sys.argv[1], sys.argv[2]
data = open(path, "rb").read().decode("utf-8", "surrogateescape")
print(data.count(needle))
PY
}

status() {
  echo "SteamVR build: $(steamvr_build_id)"
  echo "chunk: $CHUNK"
  if [ -f "$CHUNK" ]; then
    live=$(sha "$CHUNK")
    echo "chunk sha256: $live"
    case "$live" in
      "$INPUT_SHA") echo "state: bridged v1 (taskbar-order NOT applied)" ;;
      "$OUTPUT_SHA") echo "state: bridged v1 + taskbar-order PoC" ;;
      *) echo "state: UNKNOWN / drift" ;;
    esac
    if grep -Fq "$BRIDGE_V1" "$CHUNK"; then
      echo "bridge v1: PRESENT"
    elif grep -Fq '__ASTERISM_STEAMVR' "$CHUNK"; then
      echo "bridge v1: MISSING exact needle (other __ASTERISM_STEAMVR present)"
    else
      echo "bridge: ABSENT"
    fi
    echo "OLD_DT count: $(count_str "$CHUNK" "$OLD_DT")"
    echo "NEW_DT count: $(count_str "$CHUNK" "$NEW_DT")"
  else
    echo "chunk: MISSING"
  fi
  echo "marker: $([ -f "$MARKER" ] && echo yes || echo no)"
  if [ -f "$MARKER" ]; then
    cat "$MARKER"
  fi
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

# --- unpatch: NEW_DT -> OLD_DT, expect OUTPUT then INPUT ---
if [ "$do_unpatch" = 1 ]; then
  echo "Unpatch taskbar-order PoC (keep dashmgr bridge v1)"
  status
  if [ "$live_sha" = "$INPUT_SHA" ]; then
    echo "Already at input (bridged) SHA; nothing to unpatch."
    rm -f "$MARKER"
    exit 0
  fi
  if [ "$live_sha" != "$OUTPUT_SHA" ]; then
    echo "STOP: refuse unpatch; chunk SHA not OUTPUT_SHA" >&2
    echo "  expected $OUTPUT_SHA" >&2
    echo "  actual   $live_sha" >&2
    exit 2
  fi
  if [ "$(count_str "$CHUNK" "$NEW_DT")" != "1" ]; then
    echo "STOP: NEW_DT count != 1" >&2
    exit 2
  fi
  if [ "$dry_run" = 1 ]; then
    echo "[dry-run] would restore OLD_DT and re-enable readonly"
    exit 0
  fi
  ask "Remove Asterism taskbar-order Dt patch (keep bridge)?" || { echo aborted; exit 0; }

  trap 'reenable_readonly' EXIT
  if command -v steamos-readonly >/dev/null 2>&1; then
    echo "== steamos-readonly disable =="
    sudo steamos-readonly disable
    READONLY_WAS_DISABLED=1
    sudo touch "$STEAMVR_WEBUI/.asterism-write-test"
    sudo rm -f "$STEAMVR_WEBUI/.asterism-write-test"
  fi

  BK=$ASTERISM_BACKUP_DIR/taskbar-order-unpatch-$(date +%Y%m%dT%H%M%S)
  mkdir -p "$BK"
  cp -a "$CHUNK" "$BK/chunk~8012d0c89.js"
  echo "backup: $BK"

  python3 - "$CHUNK" "$NEW_DT" "$OLD_DT" "$INPUT_SHA" "$BRIDGE_V1" <<'PY'
import sys, hashlib
path, needle, repl, expect_sha, bridge = sys.argv[1:6]
data = open(path, "rb").read().decode("utf-8", "surrogateescape")
if data.count(needle) != 1:
    raise SystemExit(f"needle count {data.count(needle)}")
if bridge not in data:
    raise SystemExit("bridge v1 missing before unpatch")
out = data.replace(needle, repl, 1)
if out.count(repl) != 1 or needle in out:
    raise SystemExit("replace failed")
if bridge not in out:
    raise SystemExit("bridge v1 missing after unpatch")
raw = out.encode("utf-8", "surrogateescape")
got = hashlib.sha256(raw).hexdigest()
if got != expect_sha:
    raise SystemExit(f"sha mismatch after unpatch: {got} != {expect_sha}")
open(path + ".asterism-tmp", "wb").write(raw)
print(got)
PY
  sudo install -m 0644 "$CHUNK.asterism-tmp" "$CHUNK"
  rm -f "$CHUNK.asterism-tmp"
  got=$(sha "$CHUNK")
  [ "$got" = "$INPUT_SHA" ] || { echo "STOP: post-unpatch sha $got" >&2; exit 2; }
  grep -Fq "$BRIDGE_V1" "$CHUNK"
  rm -f "$MARKER"
  reenable_readonly
  trap - EXIT
  echo "OK unpatched taskbar-order. Clear htmlcache + restart SteamVR."
  echo "rollback backup: $BK"
  exit 0
fi

# --- apply ---
if [ "$live_sha" = "$OUTPUT_SHA" ]; then
  if [ "$(count_str "$CHUNK" "$NEW_DT")" = "1" ] && grep -Fq "$BRIDGE_V1" "$CHUNK"; then
    echo "Already patched (exact OUTPUT_SHA). Idempotent OK."
    status
    exit 0
  fi
  echo "STOP: OUTPUT_SHA but NEW_DT/bridge checks failed" >&2
  exit 2
fi

if [ "$live_sha" != "$INPUT_SHA" ]; then
  echo "STOP: chunk hash mismatch (need bridged v1 input)" >&2
  echo "  expected $INPUT_SHA" >&2
  echo "  actual   $live_sha" >&2
  exit 2
fi

if ! grep -Fq "$BRIDGE_V1" "$CHUNK"; then
  echo "STOP: dashmgr bridge v1 needle missing; refuse to layer taskbar-order" >&2
  exit 2
fi

if [ "$(count_str "$CHUNK" "$OLD_DT")" != "1" ]; then
  echo "STOP: OLD_DT count != 1" >&2
  exit 2
fi
if [ "$(count_str "$CHUNK" "$NEW_DT")" != "0" ]; then
  echo "STOP: NEW_DT already present unexpectedly" >&2
  exit 2
fi

echo "Asterism taskbar-order PoC (Dt bucket reorder only)"
echo "  build:      $live_build"
echo "  input sha:  $live_sha"
echo "  output sha: $OUTPUT_SHA"
echo "  bridge v1:  kept"
echo

if [ "$dry_run" = 1 ]; then
  echo "[dry-run] would backup chunk, replace OLD_DT -> NEW_DT, verify OUTPUT_SHA"
  python3 - "$CHUNK" "$OLD_DT" "$NEW_DT" "$OUTPUT_SHA" "$BRIDGE_V1" <<'PY'
import sys, hashlib
path, old, new, expect, bridge = sys.argv[1:6]
data = open(path, "rb").read().decode("utf-8", "surrogateescape")
out = data.replace(old, new, 1)
raw = out.encode("utf-8", "surrogateescape")
got = hashlib.sha256(raw).hexdigest()
print("dry-run sha", got)
assert got == expect
assert bridge in out
print("dry-run OK")
PY
  exit 0
fi

ask "Backup + apply taskbar-order Dt patch?" || { echo aborted; exit 0; }

trap 'reenable_readonly' EXIT
if command -v steamos-readonly >/dev/null 2>&1; then
  echo "== steamos-readonly disable =="
  sudo steamos-readonly disable
  READONLY_WAS_DISABLED=1
  sudo touch "$STEAMVR_WEBUI/.asterism-write-test"
  sudo rm -f "$STEAMVR_WEBUI/.asterism-write-test"
  echo "readonly disabled (sudo write verified)"
fi

BK=$ASTERISM_BACKUP_DIR/taskbar-order-$(date +%Y%m%dT%H%M%S)
mkdir -p "$BK"
cp -a "$CHUNK" "$BK/chunk~8012d0c89.js"
echo "$INPUT_SHA" >"$BK/INPUT_SHA.txt"
echo "$OUTPUT_SHA" >"$BK/OUTPUT_SHA.txt"
echo "backup: $BK"

python3 - "$CHUNK" "$OLD_DT" "$NEW_DT" "$OUTPUT_SHA" "$BRIDGE_V1" <<'PY'
import sys, hashlib
path, old, new, expect, bridge = sys.argv[1:6]
data = open(path, "rb").read().decode("utf-8", "surrogateescape")
if data.count(old) != 1:
    raise SystemExit(f"OLD_DT count {data.count(old)}")
if bridge not in data:
    raise SystemExit("bridge v1 missing before patch")
if "version:1" not in data:
    raise SystemExit("version:1 missing before patch")
out = data.replace(old, new, 1)
if out.count(new) != 1 or old in out:
    raise SystemExit("replace failed")
if bridge not in out or "version:1" not in out:
    raise SystemExit("bridge v1 damaged")
raw = out.encode("utf-8", "surrogateescape")
got = hashlib.sha256(raw).hexdigest()
if got != expect:
    raise SystemExit(f"sha mismatch: {got} != {expect}")
open(path + ".asterism-tmp", "wb").write(raw)
print(got)
PY

sudo install -m 0644 "$CHUNK.asterism-tmp" "$CHUNK"
rm -f "$CHUNK.asterism-tmp"
got=$(sha "$CHUNK")
if [ "$got" != "$OUTPUT_SHA" ]; then
  echo "STOP: post-install sha $got != $OUTPUT_SHA; restoring backup" >&2
  sudo install -m 0644 "$BK/chunk~8012d0c89.js" "$CHUNK"
  exit 2
fi
grep -Fq "$BRIDGE_V1" "$CHUNK"
grep -Fq 'asterism.desktop.app.' "$CHUNK"
[ "$(count_str "$CHUNK" "$NEW_DT")" = "1" ]
[ "$(count_str "$CHUNK" "$OLD_DT")" = "0" ]

{
  echo "installed=$(date -Iseconds)"
  echo "input_sha=$INPUT_SHA"
  echo "output_sha=$OUTPUT_SHA"
  echo "backup=$BK"
  echo "bridge=v1"
} >"$MARKER"

reenable_readonly
trap - EXIT

echo "OK taskbar-order applied"
echo "  chunk sha: $got"
echo "  backup:    $BK"
echo "  rollback:  $root/scripts/patch-steamvr-taskbar-order.sh --unpatch --yes"
echo "             # or: sudo install -m 0644 $BK/chunk~8012d0c89.js $CHUNK"
echo "Next: clear htmlcache + restart SteamVR, then:"
echo "  ~/asterism/scripts/asterism-dashmgr probe"
echo "  ~/asterism/scripts/asterism-dashmgr probe-taskbar"
echo "  bash ~/asterism/test/_verify_taskbar_order.sh"
