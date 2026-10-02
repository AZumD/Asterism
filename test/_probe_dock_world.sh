#!/usr/bin/env bash
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
export LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64
VR=/opt/steamvr/bin/linuxarm64/vrcmd

keys=($("$VR" --overlays 2>/dev/null | sed -n "s/^'\\(asterism\\.desktop\\.app\\.[1-9][0-9]*\\)'.*/\\1/p" | sort -u))
echo "keys: ${keys[*]}"

for key in "${keys[@]}"; do
  echo "==== float $key ===="
  set +e
  echo "-- theater"
  "$VR" --dock-overlay theater "$key"; echo rc=$?
  sleep 1
  echo "-- dashboard"
  "$VR" --dock-overlay dashboard "$key"; echo rc=$?
  sleep 1
  echo "-- world"
  "$VR" --dock-overlay world "$key"; echo rc=$?
  sleep 1
  set -e
done
"$VR" --hidedashboard || true
sleep 1
echo "==== after manual float ===="
"$VR" --overlays 2>&1 | rg "asterism\\.desktop\\.app\\.[0-9]+'" | rg -v thumb | rg -v layer

echo "==== try reverse arg order location last ===="
key=${keys[0]:-}
if [ -n "$key" ]; then
  "$VR" --dock-overlay "$key" world; echo rc=$?
  sleep 1
  "$VR" --overlays 2>&1 | rg "$key'" | head -3
fi
