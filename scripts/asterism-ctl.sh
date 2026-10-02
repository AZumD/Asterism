#!/usr/bin/env bash
# Asterism IPC client.
# Usage:
#   asterism-ctl show|hide|toggle|status|ping
#   asterism-ctl stop-desktop   # ADMIN/recovery only — kills desktop session
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1091
. "$root/scripts/_env.sh"

cmd=${1:-status}
sock=$ASTERISM_IPC_SOCK

if [ "$cmd" = "stop-desktop" ]; then
  echo "NOTE: stop-desktop is administrative/debug/recovery — not normal shell behavior." >&2
fi

if [ ! -S "$sock" ]; then
  echo "ERROR: Asterism control socket missing: $sock" >&2
  echo "Is asterism-dashboard.service running?" >&2
  exit 1
fi

python3 - "$sock" "$cmd" <<'PY'
import json, socket, sys
sock_path, cmd = sys.argv[1], sys.argv[2]
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(20)
s.connect(sock_path)
s.sendall((cmd + "\n").encode())
data = b""
while not data.endswith(b"\n"):
    chunk = s.recv(4096)
    if not chunk:
        break
    data += chunk
s.close()
text = data.decode()
try:
    obj = json.loads(text)
    print(json.dumps(obj, indent=2))
    raise SystemExit(0 if obj.get("ok", True) else 1)
except json.JSONDecodeError:
    print(text)
    raise SystemExit(1)
PY
