#!/usr/bin/env bash
# Talk to Asterism Gamescope OpenVR control socket (ASTERISM_OPENVR_CTRL=1).
set -euo pipefail
sock=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/asterism/gamescope-openvr.sock
if [ ! -S "$sock" ]; then
  echo "error: control socket missing: $sock" >&2
  echo "Enable ASTERISM_OPENVR_CTRL=1 (LD_PRELOAD owner so or experimental gamescope) and restart desktop." >&2
  exit 1
fi
cmd=${*:-inspect}
python3 - "$sock" "$cmd" <<'PY'
import socket, sys
sock_path, cmd = sys.argv[1], sys.argv[2]
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(10)
s.connect(sock_path)
s.sendall((cmd + "\n").encode())
data = b""
while True:
    chunk = s.recv(8192)
    if not chunk:
        break
    data += chunk
    if data.endswith(b"\n") and len(data) > 1:
        break
s.close()
sys.stdout.write(data.decode())
PY
