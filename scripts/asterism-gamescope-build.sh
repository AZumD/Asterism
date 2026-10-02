#!/usr/bin/env bash
# Build a side-by-side experimental Gamescope for Asterism owner-transform proof.
# NEVER installs into /usr or /opt. Output: $ASTERISM_ROOT/gamescope-asterism/out/gamescope
set -euo pipefail
root=${ASTERISM_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
src=$root/gamescope-asterism/src
out=$root/gamescope-asterism/out
# Prefer a Frame-matching tag if present; otherwise upstream master tip at clone time.
tag=${ASTERISM_GAMESCOPE_TAG:-}

mkdir -p "$root/gamescope-asterism"
if [ ! -d "$src/.git" ]; then
  echo "Cloning ValveSoftware/gamescope (this is large)…"
  git clone --depth 1 ${tag:+--branch "$tag"} https://github.com/ValveSoftware/gamescope.git "$src"
  git -C "$src" submodule update --init --recursive
fi

# Record exact commit for the end-of-pass report.
commit=$(git -C "$src" rev-parse HEAD)
echo "$commit" >"$root/gamescope-asterism/BUILT_FROM_COMMIT"
echo "Building experimental gamescope from $commit"

# Apply Asterism owner-transform control (idempotent Python string-anchor patcher).
python3 "$root/scripts/asterism-gamescope-patch.py" "$src"

# Build into a private prefix (meson/ninja typical for gamescope).
build=$root/gamescope-asterism/build
mkdir -p "$build" "$out"
if command -v meson >/dev/null; then
  meson setup "$build" "$src" --prefix="$out" -Dpipewire=enabled || meson setup --reconfigure "$build" "$src" --prefix="$out"
  ninja -C "$build"
  ninja -C "$build" install
else
  echo "meson not found — install build deps on Frame, then re-run" >&2
  echo "See gamescope-asterism/README.md" >&2
  exit 1
fi

bin=$out/bin/gamescope
if [ ! -x "$bin" ]; then
  # Some installs put the binary directly under out/
  bin=$out/gamescope
fi
if [ ! -x "$bin" ]; then
  echo "build finished but gamescope binary not found under $out" >&2
  exit 1
fi
ln -sfn "$bin" "$out/gamescope"
echo "OK experimental gamescope -> $out/gamescope"
echo "Set ASTERISM_GAMESCOPE_BIN=$out/gamescope in ~/.config/asterism/asterism.conf"
echo "Set ASTERISM_OPENVR_CTRL=1 and restart Asterism desktop only."
