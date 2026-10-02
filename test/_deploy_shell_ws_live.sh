#!/usr/bin/env bash
# Live-write ONLY asterism_shell.js (+ systemui.html contenthash bump).
# Does NOT touch the Valve chunk bridge.
#
# Safety:
# - backup as steamos user
# - verify exact SteamVR bridged chunk hash
# - interactive sudo (never read third-party .env for passwords)
# - steamos-readonly disable/enable with verification (failures abort)
# - trap re-enables readonly on failure when possible
set -euo pipefail
cd /home/steamos/asterism
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus

DASH=/opt/steamvr/resources/webinterface/dashboard
CHUNK=$DASH/chunk~8012d0c89.js
SHELL_DST=$DASH/asterism_shell.js
HTML=$DASH/systemui.html
# Accept current live v1 bridge OR staged v2 after manual apply
BRIDGED_SHA_V1=272c1e40f75bafe28a7108485295681ffdac2a322a6a10f3e2d35278d596dfd9
TAG_NEW='asterism_shell.js?contenthash=asterism4'
EXPECTED_BUILD=1790822802

sha() { sha256sum "$1" | awk '{print $1}'; }

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
  # Verify: writing to DASH should fail (or require root). Prefer status if available.
  if steamos-readonly status 2>/dev/null | grep -qi 'enabled\|read-only\|active'; then
    echo "steamos-readonly: enabled (status ok)"
  else
    # Fall back: try creating a file as steamos user — should fail when readonly
    if touch "$DASH/.asterism-ro-check" 2>/dev/null; then
      rm -f "$DASH/.asterism-ro-check"
      echo "WARNING: DASH still appears writable after enable" >&2
      return 1
    fi
    echo "steamos-readonly: enabled (write blocked)"
  fi
  READONLY_WAS_DISABLED=0
}

trap 'reenable_readonly' EXIT

echo "== preflight =="
if [ -f /opt/steamvr/bin/version.txt ]; then
  build=$(tr -d '\r\n' < /opt/steamvr/bin/version.txt)
  echo "SteamVR version.txt: $build (expected build id $EXPECTED_BUILD)"
fi
live_chunk=$(sha "$CHUNK")
echo "chunk sha: $live_chunk"
if [ "$live_chunk" != "$BRIDGED_SHA_V1" ]; then
  if grep -Fq 'applyWorldTransformForSummonKey' "$CHUNK" && grep -Fq 'version:2' "$CHUNK"; then
    echo "chunk looks like bridge v2 (direct-transform); allowing shell-only deploy"
  else
    echo "STOP: chunk is not the known bridged hash and not recognized v2" >&2
    echo "  expected v1 $BRIDGED_SHA_V1" >&2
    exit 2
  fi
else
  echo "chunk bridge v1 OK (untouched by this script)"
fi

BK=$HOME/.local/share/asterism/backups/shell-ws-$(date +%Y%m%dT%H%M%S)
mkdir -p "$BK"
cp -a "$SHELL_DST" "$BK/asterism_shell.js" 2>/dev/null || true
cp -a "$HTML" "$BK/systemui.html"
echo "backup: $BK"

STAGE=/tmp/asterism-shell-ws-stage
rm -rf "$STAGE"
mkdir -p "$STAGE"
python3 - <<'PY'
from pathlib import Path
import hashlib, re
root = Path("/home/steamos/asterism")
stage = Path("/tmp/asterism-shell-ws-stage")
src = root / "patches/asterism_shell.js"
data = src.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
(stage / "asterism_shell.js").write_bytes(data)
html_path = Path("/opt/steamvr/resources/webinterface/dashboard/systemui.html")
html = html_path.read_text(encoding="utf-8", errors="surrogateescape")
new = "asterism_shell.js?contenthash=asterism4"
if "asterism_shell.js" not in html:
    raise SystemExit("systemui.html missing asterism_shell inject")
html = re.sub(r"asterism_shell\.js\?contenthash=[^\"]+", new, html, count=1)
if new not in html:
    raise SystemExit("failed to set contenthash=asterism4")
(stage / "systemui.html").write_text(html, encoding="utf-8", errors="surrogateescape")
print("staged shell", hashlib.sha256((stage/"asterism_shell.js").read_bytes()).hexdigest())
print("staged html ", hashlib.sha256((stage/"systemui.html").read_bytes()).hexdigest())
PY

echo "== steamos-readonly disable =="
if command -v steamos-readonly >/dev/null 2>&1; then
  sudo steamos-readonly disable
  READONLY_WAS_DISABLED=1
  touch "$DASH/.asterism-write-test"
  rm -f "$DASH/.asterism-write-test"
  echo "readonly disabled (write verified)"
else
  if [ ! -w "$DASH" ]; then
    echo "STOP: $DASH not writable and steamos-readonly unavailable" >&2
    exit 2
  fi
fi

echo "== install (shell+html only) =="
sudo install -m 0644 "$STAGE/asterism_shell.js" "$SHELL_DST"
sudo install -m 0644 "$STAGE/systemui.html" "$HTML"

echo "== verify install =="
echo "chunk (must unchanged this script): $(sha "$CHUNK")"
echo "shell: $(sha "$SHELL_DST")"
echo "html:  $(sha "$HTML")"
grep -F "$TAG_NEW" "$HTML"
grep -F 'ws://localhost:47832' "$SHELL_DST"
grep -F 'resolveFramesReport' "$SHELL_DST"

reenable_readonly
trap - EXIT

systemctl --user restart asterism-dashboard.service
sleep 2
curl -fsS http://127.0.0.1:47831/ping; echo
curl -fsS http://127.0.0.1:47831/status | python3 -m json.tool | head -40

rm -rf "$HOME/.cache/SteamVR/htmlcache"
systemctl --user restart steamvr.service
echo "SteamVR restart issued"
echo "WAIT for WS connect then: ~/asterism/scripts/asterism-dashmgr probe"
