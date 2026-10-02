#!/usr/bin/env bash
set -euo pipefail
cd ~/asterism
# Disable preload path for stock (caps ignore/unstable); use patched binary instead.
CONF=~/.config/asterism/asterism.conf
sed -i '/^ASTERISM_OPENVR_CTRL=/d' "$CONF"
sed -i '/^ASTERISM_GAMESCOPE_BIN=/d' "$CONF"

src=~/asterism/gamescope-asterism/src
if [ ! -d "$src/.git" ]; then
  git clone --depth 1 https://github.com/ValveSoftware/gamescope.git "$src"
fi
git -C "$src" rev-parse HEAD | tee ~/asterism/gamescope-asterism/BUILT_FROM_COMMIT

echo '=== submodules (may take a while) ==='
git -C "$src" submodule update --init --recursive

echo '=== apply asterism patch ==='
python3 ~/asterism/scripts/asterism-gamescope-patch.py "$src"

echo '=== meson setup ==='
build=~/asterism/gamescope-asterism/build
out=~/asterism/gamescope-asterism/out
mkdir -p "$build" "$out"
# Disable features that often lack deps on Frame; OpenVR backend is what we need.
meson setup "$build" "$src" --prefix="$out" \
  -Dpipewire=enabled \
  -Denable_openvr_support=true \
  || meson setup --reconfigure "$build" "$src" --prefix="$out" \
  -Dpipewire=enabled \
  -Denable_openvr_support=true

echo '=== ninja ==='
ninja -C "$build"
ninja -C "$build" install
# Prefer installed bin; also keep a direct link
if [ -x "$out/bin/gamescope" ]; then
  ln -sfn "$out/bin/gamescope" "$out/gamescope"
elif [ -x "$build/gamescope" ]; then
  ln -sfn "$build/gamescope" "$out/gamescope"
fi
ls -la "$out/gamescope" "$out/bin/gamescope" 2>/dev/null || ls -la "$build"/gamescope*
# Ensure NO file capabilities on experimental binary
getcap "$out/gamescope" 2>/dev/null || true
echo BUILD_OK
