#!/usr/bin/env bash
# Verify Desktop Settings can attach to nested Plasma from a clean SSH-like env.
set -euo pipefail
cd ~/asterism
sed -i 's/\r$//' \
  desktop-settings/asterism-desktop-settings \
  desktop-settings/asterism-shell-env.sh \
  desktop-settings/asterism_desktop_settings.py \
  desktop/asterism-session-inner.sh \
  test/test_desktop_settings.py || true
chmod +x desktop-settings/asterism-desktop-settings desktop-settings/asterism-shell-env.sh

python3 -m unittest test.test_desktop_settings -v

# Simulate SSH: wipe display vars, then launch
env -u DISPLAY -u WAYLAND_DISPLAY -u XAUTHORITY \
  bash -lc '
    . desktop-settings/asterism-shell-env.sh
    if asterism_shell_env_attach; then
      echo "ATTACH_OK runtime=$XDG_RUNTIME_DIR wayland=$WAYLAND_DISPLAY display=$DISPLAY"
    else
      echo "ATTACH_FAIL"
      exit 1
    fi
  '

# Brief GUI smoke (timeout = success if window came up)
env -u DISPLAY -u WAYLAND_DISPLAY -u XAUTHORITY \
  timeout 4 ~/.local/bin/asterism-desktop-settings \
  && echo launched_ok || echo "launcher_timeout_or_exit:$?"
