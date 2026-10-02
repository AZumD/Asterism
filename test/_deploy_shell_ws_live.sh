#!/usr/bin/env bash
# Live-write ONLY asterism_shell.js (+ optional systemui.html contenthash bump).
# Does NOT touch the Valve chunk bridge.
set -euo pipefail
cd /home/steamos/asterism
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus

DASH=/opt/steamvr/resources/webinterface/dashboard
CHUNK=$DASH/chunk~8012d0c89.js
SHELL_DST=$DASH/asterism_shell.js
HTML=$DASH/systemui.html
BRIDGED_SHA=272c1e40f75bafe28a7108485295681ffdac2a322a6a10f3e2d35278d596dfd9
TAG_OLD='asterism_shell.js?contenthash=asterism2'
TAG_NEW='asterism_shell.js?contenthash=asterism3'

sha() { sha256sum "$1" | awk '{print $1}'; }

sudo_run() {
  if [ -w "$DASH" ]; then
    "$@"
    return
  fi
  local pw=""
  if [ -f /home/steamos/dev/frametop/.env ]; then
    pw=$(sed -n 's/^steamos_root_pwd=//p' /home/steamos/dev/frametop/.env | sed 's/^["'\'']//;s/["'\'']$//')
  elif [ -f /home/steamos/frametop/.env ]; then
    pw=$(sed -n 's/^steamos_root_pwd=//p' /home/steamos/frametop/.env | sed 's/^["'\'']//;s/["'\'']$//')
  fi
  [ -n "$pw" ] || { echo "NEED_SUDO"; exit 42; }
  printf '%s\n' "$pw" | sudo -S -p '' "$@"
}

echo "== preflight =="
live_chunk=$(sha "$CHUNK")
echo "chunk sha: $live_chunk"
if [ "$live_chunk" != "$BRIDGED_SHA" ]; then
  echo "STOP: chunk is not the known bridged hash; refuse shell-only deploy"
  echo "  expected $BRIDGED_SHA"
  exit 2
fi
echo "chunk bridge OK (untouched)"

# steamos user backup of files we will change
BK=$HOME/.local/share/asterism/backups/shell-ws-$(date +%Y%m%dT%H%M%S)
mkdir -p "$BK"
cp -a "$SHELL_DST" "$BK/asterism_shell.js" 2>/dev/null || true
cp -a "$HTML" "$BK/systemui.html"
echo "backup: $BK"

# Stage with contenthash bump
STAGE=/tmp/asterism-shell-ws-stage
rm -rf "$STAGE"
mkdir -p "$STAGE"
# LF-normalize sources (python, not sed \r)
python3 - <<'PY'
from pathlib import Path
root = Path("/home/steamos/asterism")
stage = Path("/tmp/asterism-shell-ws-stage")
for src, dst in [
    (root / "patches/asterism_shell.js", stage / "asterism_shell.js"),
]:
    data = src.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    dst.write_bytes(data)
html = Path("/opt/steamvr/resources/webinterface/dashboard/systemui.html").read_text(encoding="utf-8", errors="surrogateescape")
old = "asterism_shell.js?contenthash=asterism2"
new = "asterism_shell.js?contenthash=asterism3"
if old in html:
    html = html.replace(old, new, 1)
elif "contenthash=asterism3" in html:
    pass
elif "asterism_shell.js" in html:
    # already injected with other hash — force asterism3
    import re
    html = re.sub(r"asterism_shell\.js\?contenthash=[^\"]+", new, html, count=1)
else:
    raise SystemExit("systemui.html missing asterism_shell inject")
Path("/tmp/asterism-shell-ws-stage/systemui.html").write_text(html, encoding="utf-8", errors="surrogateescape")
print("staged shell", __import__("hashlib").sha256((stage/"asterism_shell.js").read_bytes()).hexdigest())
print("staged html ", __import__("hashlib").sha256((stage/"systemui.html").read_bytes()).hexdigest())
PY

echo "== install (shell+html only) =="
# disable readonly if present
if command -v steamos-readonly >/dev/null 2>&1; then
  sudo_run steamos-readonly disable || true
fi
sudo_run install -m 0644 "$STAGE/asterism_shell.js" "$SHELL_DST"
sudo_run install -m 0644 "$STAGE/systemui.html" "$HTML"
if command -v steamos-readonly >/dev/null 2>&1; then
  sudo_run steamos-readonly enable || true
fi

echo "== verify =="
echo "chunk (must unchanged): $(sha "$CHUNK")"
test "$(sha "$CHUNK")" = "$BRIDGED_SHA"
echo "shell: $(sha "$SHELL_DST")"
echo "html:  $(sha "$HTML")"
grep -F "$TAG_NEW" "$HTML"
grep -F 'ws://localhost:47832' "$SHELL_DST"

# Restart dashboard (WS server) then SteamVR
systemctl --user restart asterism-dashboard.service
sleep 2
curl -fsS http://127.0.0.1:47831/ping; echo
curl -fsS http://127.0.0.1:47831/status | python3 -m json.tool | head -40

rm -rf "$HOME/.cache/SteamVR/htmlcache"
systemctl --user restart steamvr.service
echo "SteamVR restart issued"
echo "WAIT for WS connect then: ~/asterism/scripts/asterism-dashmgr probe"
