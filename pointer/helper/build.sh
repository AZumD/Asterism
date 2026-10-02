#!/usr/bin/env bash
# Build asterism-place on the Frame host.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root/pointer/helper"
mkdir -p build
g++ -std=c++17 -O2 -Wall -Wno-unused-parameter -fno-math-errno \
  -I/opt/steamvr/tools/hellovr_vulkan_linux/src/openvr/headers \
  -I"$root/pointer" \
  -o build/asterism-place asterism-place.cpp \
  -L/opt/steamvr/bin/linuxarm64 -lopenvr_api -lpthread -Wl,-rpath,/opt/steamvr/bin/linuxarm64
echo "built $root/pointer/helper/build/asterism-place"
