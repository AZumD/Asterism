#!/usr/bin/env bash
set -eu
export LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64
for i in $(seq 1 24); do
  echo "try $i"
  pgrep -a vrmonitor | head -1 || echo "no vrmonitor"
  pgrep -a vrserver | head -1 || echo "no vrserver"
  /opt/steamvr/bin/linuxarm64/vrcmd --pollposes 2>&1 | head -1 || true
  if pgrep -x vrmonitor >/dev/null && /opt/steamvr/bin/linuxarm64/vrcmd --pollposes 2>&1 | head -1 | grep -q ','; then
    echo READY
    /tmp/headpose 2>&1 | tail -20 || true
    exit 0
  fi
  sleep 5
done
echo TIMEOUT
exit 1
