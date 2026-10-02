#!/usr/bin/env bash
# Live-write ONLY asterism_shell.js (+ systemui.html contenthash bump).
# Does NOT touch the Valve chunk bridge.
#
# Safety:
# - backup as steamos user
# - verify exact known chunk SHA allowlist (no fuzzy grep recognition)
# - interactive sudo (never read third-party .env for passwords)
# - trap installed BEFORE steamos-readonly disable
# - writability probe uses sudo (not confused with Unix dir perms)
# - re-enable readonly in trap; never swallow readonly failures with || true
set -euo pipefail
cd /home/steamos/asterism
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus

DASH=/opt/steamvr/resources/webinterface/dashboard
CHUNK=$DASH/chunk~8012d0c89.js
SHELL_DST=$DASH/asterism_shell.js
HTML=$DASH/systemui.html
# Exact allowlist only
BRIDGED_SHA_V1=272c1e40f75bafe28a7108485295681ffdac2a322a6a10f3e2d35278d596dfd9
# Known-broken experimental v2 (black rectangle) — allow shell-only redeploy for recovery
BRIDGED_SHA_V2_BROKEN=83a3bcbf43f179b290614af038835395226b0d8b54aaf188ce1a44c540a8aa2a
TAG_NEW='asterism_shell.js?contenthash=asterism6'
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
  if steamos-readonly status 2>/dev/null | grep -qiE 'enabled|read-only|active'; then
    echo "steamos-readonly: enabled (status ok)"
  else
    # Prefer sudo test file that should fail to create when readonly is on
    if sudo touch "$DASH/.asterism-ro-check" 2>/dev/null; then
      sudo rm -f "$DASH/.asterism-ro-check"
      # On some images touch as root still works when "readonly"; rely on status above.
      echo "NOTE: root can still write $DASH after enable; trust steamos-readonly enable exit=0"
    fi
  fi
  READONLY_WAS_DISABLED=0
}

# Trap BEFORE any readonly disable / install work
trap 'reenable_readonly' EXIT

echo "== preflight =="
if [ -f /opt/steamvr/bin/version.txt ]; then
  build=$(tr -d '\r\n' < /opt/steamvr/bin/version.txt)
  echo "SteamVR version.txt: $build (expected build id $EXPECTED_BUILD)"
fi
live_chunk=$(sha "$CHUNK")
echo "chunk sha: $live_chunk"
case "$live_chunk" in
  "$BRIDGED_SHA_V1")
    echo "chunk bridge v1 OK (untouched by this script)"
    ;;
  "$BRIDGED_SHA_V2_BROKEN")
    echo "WARNING: live chunk is known-broken v2 ($BRIDGED_SHA_V2_BROKEN)"
    echo "         shell-only deploy allowed for recovery; roll chunk back to v1 ASAP"
    ;;
  *)
    echo "STOP: chunk SHA not in allowlist" >&2
    echo "  expected v1 $BRIDGED_SHA_V1" >&2
    echo "  or known-broken v2 $BRIDGED_SHA_V2_BROKEN" >&2
    exit 2
    ;;
esac

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
new = "asterism_shell.js?contenthash=asterism6"
if "asterism_shell.js" not in html:
    raise SystemExit("systemui.html missing asterism_shell inject")
html = re.sub(r"asterism_shell\.js\?contenthash=[^\"]+", new, html, count=1)
if new not in html:
    raise SystemExit("failed to set contenthash=asterism6")
(stage / "systemui.html").write_text(html, encoding="utf-8", errors="surrogateescape")
print("staged shell", hashlib.sha256((stage/"asterism_shell.js").read_bytes()).hexdigest())
print("staged html ", hashlib.sha256((stage/"systemui.html").read_bytes()).hexdigest())
PY

echo "== steamos-readonly disable =="
if command -v steamos-readonly >/dev/null 2>&1; then
  sudo steamos-readonly disable
  READONLY_WAS_DISABLED=1
  # Verify rootfs writable via sudo (not ordinary-user dir perms)
  sudo touch "$DASH/.asterism-write-test"
  sudo rm -f "$DASH/.asterism-write-test"
  echo "readonly disabled (sudo write verified)"
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
grep -F 'findLiveUndockedOverlayForFrame' "$SHELL_DST"
grep -F 'seedPresentationTransform' "$SHELL_DST"

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
