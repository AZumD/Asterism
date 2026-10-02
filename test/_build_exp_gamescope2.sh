#!/usr/bin/env bash
set -euo pipefail
cd ~/asterism
src=~/asterism/gamescope-asterism/src
build=~/asterism/gamescope-asterism/build
out=~/asterism/gamescope-asterism/out
mkdir -p "$build" "$out"

# Ensure patch applied
python3 ~/asterism/scripts/asterism-gamescope-patch.py "$src" || true

# Reconfigure without tests / optional deps that Frame lacks
meson setup --reconfigure "$build" "$src" --prefix="$out" \
  -Dpipewire=enabled \
  -Denable_openvr_support=true \
  -Denable_gamescope_wsi_layer=true \
  -Denable_xwayland_support=true \
  || meson setup "$build" "$src" --prefix="$out" \
  -Dpipewire=enabled \
  -Denable_openvr_support=true

# If tests still fail, patch meson to skip tests dir
if ! meson setup --reconfigure "$build" "$src" --prefix="$out" -Dpipewire=enabled 2>/tmp/meson_err; then
  if grep -q catch2 /tmp/meson_err "$build/meson-logs/meson-log.txt" 2>/dev/null; then
    echo 'Disabling tests/ in root meson.build'
    python3 - <<'PY'
from pathlib import Path
p = Path.home() / "asterism/gamescope-asterism/src/meson.build"
t = p.read_text()
t2 = t.replace("subdir('tests')", "# subdir('tests')  # Asterism: Frame lacks catch2")
if t2 == t:
    # try other patterns
    import re
    t2 = re.sub(r"subdir\(['\"]tests['\"]\)", "# subdir('tests')  # Asterism", t)
p.write_text(t2)
print("patched", p)
PY
    meson setup --reconfigure "$build" "$src" --prefix="$out" -Dpipewire=enabled -Denable_openvr_support=true
  else
    cat /tmp/meson_err
    exit 1
  fi
fi

ninja -C "$build" -j$(nproc)
ninja -C "$build" install
if [ -x "$out/bin/gamescope" ]; then
  ln -sfn "$out/bin/gamescope" "$out/gamescope"
elif [ -x "$build/src/gamescope" ]; then
  ln -sfn "$build/src/gamescope" "$out/gamescope"
else
  find "$build" -type f -name gamescope -executable | head
  find "$out" -type f -name gamescope -executable | head
fi
ls -la "$out/gamescope"
file "$out/gamescope"
getcap "$out/gamescope" || true
echo BUILD_OK
