#!/usr/bin/env bash
# Inner Plasma session for Asterism (runs inside gamescope Wayland).
# Adapted from /usr/bin/steamos-nested-desktop — separate XDG dirs from FrameTop/stock.
set -euo pipefail

root=${ASTERISM_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
# shellcheck disable=SC1091
. "$root/scripts/_env.sh"

conf=$ASTERISM_CONFIG_DIR/asterism.conf
WIDTH=1280 HEIGHT=800
# shellcheck disable=SC1090
if [ -f "$conf" ]; then
  # shellcheck disable=SC1091
  . <(tr -d '\r' < "$conf")
fi
width=${ASTERISM_WIDTH:-$WIDTH}
height=${ASTERISM_HEIGHT:-$HEIGHT}
width=${width//$'\r'/}
height=${height//$'\r'/}
output_count=${ASTERISM_OUTPUT_COUNT:-1}
output_count=${output_count//$'\r'/}
[[ "$output_count" =~ ^[1-9][0-9]*$ ]] || output_count=1

unset XDG_DESKTOP_PORTAL_DIR
unset LD_PRELOAD

host_runtime=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
runtime=$host_runtime/asterism_nested

wipe_runtime() {
  fusermount3 -u -z "$runtime/doc" 2>/dev/null || true
  umount --recursive "$runtime" 2>/dev/null || true
  rm -rf "$runtime" 2>/dev/null || true
}

cleanup() {
  wipe_runtime
  asterism_log INFO "asterism-session-inner cleanup"
}
trap cleanup EXIT

wipe_runtime
mkdir -m 0700 "$runtime" "$runtime/pulse" "$runtime/bin"
ln -s "$host_runtime/pulse/native" "$runtime/pulse/native" 2>/dev/null || true
ln -s "$host_runtime"/pipewire* "$runtime/" 2>/dev/null || true

# Shadow kwin wrapper — output-count from displays.json enabled displays
cat > "$runtime/bin/kwin_wayland_wrapper" <<EOF
#!/bin/sh
exec /usr/bin/kwin_wayland_wrapper --width $width --height $height --output-count $output_count --no-lockscreen "\$@"
EOF
chmod +x "$runtime/bin/kwin_wayland_wrapper"
export PATH=$runtime/bin:$PATH

case ${WAYLAND_DISPLAY:-gamescope-0} in
  /*) ;;
  *) export WAYLAND_DISPLAY=$host_runtime/${WAYLAND_DISPLAY:-gamescope-0} ;;
esac

export XDG_RUNTIME_DIR=$runtime
export XDG_CONFIG_HOME=$HOME/.config/asterism/plasma
export XDG_STATE_HOME=$HOME/.local/state/asterism/plasma
mkdir -p "$XDG_CONFIG_HOME" "$XDG_STATE_HOME"

export XDG_DATA_DIRS=${XDG_DATA_DIRS:-/usr/local/share:/usr/share}
# shellcheck disable=SC1091
[ -f /etc/profile.d/flatpak.sh ] && { set +u; . /etc/profile.d/flatpak.sh; set -u; }

asterism_log INFO "starting nested Plasma ${width}x${height} outputs=$output_count"

# Background: snapshot plasmashell.env for SSH/menu launchers (FrameTop ft-shell-watch idea).
# shellcheck disable=SC1091
if [ -f "$root/desktop-settings/asterism-shell-env.sh" ]; then
  (
    # shellcheck disable=SC1091
    . "$root/desktop-settings/asterism-shell-env.sh"
    envfile=$(asterism_shell_env_path)
    for _ in $(seq 1 90); do
      sleep 1
      if pid=$(asterism_find_nested_plasmashell 2>/dev/null); then
        if asterism_shell_env_capture "$pid" "$envfile"; then
          asterism_log INFO "wrote plasmashell.env from pid=$pid"
          asterism_shell_env_load "$envfile" || true
          # Fix overlapping KWin geometries (e.g. second output at x=1280 with 1920-wide primary).
          export ASTERISM_WIDTH=$width ASTERISM_HEIGHT=$height ASTERISM_OUTPUT_COUNT=$output_count
          "$root/desktop/asterism-apply-outputs.sh" || true
          exit 0
        fi
      fi
    done
    asterism_log WARN "timed out waiting to capture plasmashell.env"
  ) &
  disown || true
fi

exec dbus-run-session startplasma-wayland
