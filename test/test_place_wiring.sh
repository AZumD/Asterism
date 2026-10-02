#!/usr/bin/env bash
# Verify asterism-place binary + layout place wiring (no live SteamVR place required).
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
fail=0

bin=$root/pointer/helper/build/asterism-place
if [[ -x $bin ]]; then
  echo "PASS: asterism-place present"
else
  echo "FAIL: asterism-place missing at $bin (build pointer/helper)"
  fail=1
fi

so=$root/pointer/driver/build/driver_asterism_pointer.so
if [[ -f $so ]]; then
  echo "PASS: driver_asterism_pointer.so present"
else
  echo "FAIL: driver .so missing"
  fail=1
fi

python3 - <<PY
import sys
sys.path.insert(0, "$root/layout")
from layout import place_bin, place_world, place_on_apply_enabled, default_layout
assert place_bin().name == "asterism-place"
assert place_on_apply_enabled() is False
lay = default_layout(2)
assert lay["screens"][0]["dock"] == "world"
print("PASS: layout place helpers import")
PY

# Unit: place_world reports missing binary cleanly when overridden
ASTERISM_PLACE=/nonexistent/asterism-place python3 - <<PY
import os, sys
sys.path.insert(0, "$root/layout")
from layout import place_world
r = place_world("asterism.desktop.app.2", {"pos":[0,0,-1.6],"face":[0,0],"roll":0})
assert r["ok"] is False and "missing" in r["error"], r
print("PASS: place_world missing-bin error")
PY

exit $fail
