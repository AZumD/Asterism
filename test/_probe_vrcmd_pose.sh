#!/usr/bin/env bash
set -euo pipefail
export LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64
VR=/opt/steamvr/bin/linuxarm64/vrcmd
echo "==== dump-positions ===="
"$VR" --dump-positions 2>&1 | head -80
echo "==== dock-overlay usage ===="
"$VR" --dock-overlay 2>&1 | head -30 || true
echo "==== overlays asterism ===="
"$VR" --overlays 2>&1 | rg 'asterism' || true
echo "==== try dump for one key ===="
"$VR" --dump-positions 2>&1 | rg -i 'asterism|Desktop|frametop' | head -40 || true
