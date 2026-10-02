#!/usr/bin/env bash
# Live-fix overlapping outputs + unit tests (no full SteamVR restart required for outputs).
set -euo pipefail
cd ~/asterism
sed -i 's/\r$//' \
  desktop/asterism-apply-outputs.sh \
  desktop/asterism-session-inner.sh \
  desktop/asterism-session.sh \
  layout/layout.py \
  scripts/asterism-layout \
  display/displays.py \
  desktop-settings/asterism_desktop_settings.py \
  test/test_layout.py || true
chmod +x desktop/asterism-apply-outputs.sh scripts/asterism-layout

python3 -m unittest test.test_layout -v

# Init layout if missing
./scripts/asterism-layout sync || ./scripts/asterism-layout init

# Apply outputs inside nested session env
# shellcheck disable=SC1091
. desktop-settings/asterism-shell-env.sh
asterism_shell_env_attach
export ASTERISM_WIDTH=1920 ASTERISM_HEIGHT=1080 ASTERISM_OUTPUT_COUNT=2
./desktop/asterism-apply-outputs.sh
echo "=== geometry after ==="
kscreen-doctor -o 2>&1 | tr -d '\033' | sed 's/\[[0-9;]*m//g' | grep -E 'Output:|Geometry:' | head -20

echo ALL_OK
