#!/usr/bin/env bash
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
cd ~/asterism

echo "=== live lifecycle ==="
pid1=$(systemctl --user show -p MainPID --value asterism-desktop.service)
./scripts/asterism-ctl.sh hide >/dev/null
sleep 1
pid2=$(systemctl --user show -p MainPID --value asterism-desktop.service)
./scripts/asterism-ctl.sh show >/dev/null
sleep 1
pid3=$(systemctl --user show -p MainPID --value asterism-desktop.service)
./scripts/asterism-ctl.sh toggle >/dev/null || true
pid4=$(systemctl --user show -p MainPID --value asterism-desktop.service)
echo "pids: start=$pid1 hide=$pid2 show=$pid3 toggle=$pid4"
test "$pid1" = "$pid2" && test "$pid2" = "$pid3" && test "$pid3" = "$pid4" && echo PASS_same_desktop_pid

echo "=== displayctl ==="
./scripts/asterism-displayctl list
./scripts/asterism-displayctl add --resolution 1920x1080
./scripts/asterism-displayctl set display-2 scale 1.25
./scripts/asterism-displayctl set-primary display-1
./scripts/asterism-displayctl list --json | head -40
./scripts/asterism-displayctl remove display-2
./scripts/asterism-displayctl apply
./scripts/asterism-displayctl list

echo "=== recover dry-run ==="
./scripts/recover-asterism.sh --dry-run --yes --no-restart | tail -15

echo "=== steamvr health ==="
systemctl --user is-active steamvr.service
pgrep -x vrserver >/dev/null && pgrep -x vrcompositor >/dev/null && echo OK

echo "=== prepare patch payload (no root) ==="
mkdir -p /tmp/asterism-patch-out
cp -a patches/asterism_shell.js /tmp/asterism-patch-out/
python3 - <<'PY'
from pathlib import Path
html = Path("/opt/steamvr/resources/webinterface/dashboard/systemui.html").read_text(encoding="utf-8", errors="surrogateescape")
tag = '<script defer="defer" src="asterism_shell.js?contenthash=asterism1"></script>'
if "asterism_shell.js" not in html:
    i = html.lower().rfind("</body>")
    end = html[i:i+7]
    html = html[:i] + tag + end + html[i+7:]
Path("/tmp/asterism-patch-out/systemui.html").write_text(html, encoding="utf-8", errors="surrogateescape")
import hashlib
for p in Path("/tmp/asterism-patch-out").iterdir():
    print(p.name, hashlib.sha256(p.read_bytes()).hexdigest())
PY
echo "Apply with: sudo cp /tmp/asterism-patch-out/asterism_shell.js /opt/steamvr/resources/webinterface/dashboard/ && sudo cp /tmp/asterism-patch-out/systemui.html /opt/steamvr/resources/webinterface/dashboard/systemui.html"
echo "Or: cd ~/asterism && sudo ./scripts/patch-steamvr-ui.sh --yes"
