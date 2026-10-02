#!/usr/bin/env bash
# Install/remove the asterism_pointer SteamVR driver (virtual controller for world place).
# SteamVR loads external drivers only at startup — restart SteamVR after install/uninstall.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
# shellcheck disable=SC1091
. "$root/scripts/_env.sh"

src=$root/pointer/driver
dest=${ASTERISM_POINTER_DRIVER:-$HOME/.local/share/asterism/asterism_pointer}
reg=/opt/steamvr/bin/linuxarm64/vrpathreg
so=$src/build/driver_asterism_pointer.so

backup_paths() {
  paths=$HOME/.config/openvr/openvrpaths.vrpath
  [[ -f $paths ]] || return 0
  bak=$paths.asterism-pre-pointer.$(date +%Y%m%d%H%M%S)
  cp -a "$paths" "$bak"
  ln -sfn "$bak" "$paths.asterism-pre-pointer.latest"
  echo "backed up openvrpaths -> $bak"
}

case ${1:-install} in
  install)
    [[ -f $so ]] || { echo "missing $so — build pointer/driver first" >&2; exit 1; }
    backup_paths
    rm -rf "$dest.new"
    mkdir -p "$dest.new/bin/linuxarm64"
    cp -a "$src/asterism_pointer/." "$dest.new/"
    cp -a "$so" "$dest.new/bin/linuxarm64/"
    rm -rf "$dest"
    mv "$dest.new" "$dest"
    LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64 "$reg" adddriver "$dest"
    echo "installed asterism_pointer at $dest"
    LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64 "$reg" show | grep -A5 -i external || true
    echo "Restart SteamVR before using asterism-place."
    ;;
  uninstall)
    if LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64 "$reg" show 2>/dev/null | grep -F "$dest" >/dev/null; then
      LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64 "$reg" removedriver "$dest" || true
    fi
    rm -rf "$dest"
    echo "removed asterism_pointer"
    echo "Restart SteamVR to unload the driver."
    ;;
  status)
    LD_LIBRARY_PATH=/opt/steamvr/bin/linuxarm64 "$reg" show || true
    [[ -d $dest ]] && echo "files: $dest" || echo "files: not installed"
    ;;
  *)
    echo "usage: $0 install|uninstall|status" >&2
    exit 2
    ;;
esac
