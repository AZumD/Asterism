#!/usr/bin/env bash
# Asterism nested desktop session — SteamVR-session infrastructure.
# One gamescope OpenVR dashboard overlay named "Desktop" hosting nested Plasma.
set -euo pipefail

root=${ASTERISM_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
# shellcheck disable=SC1091
. "$root/scripts/_env.sh"

conf=$ASTERISM_CONFIG_DIR/asterism.conf
WIDTH=1280 HEIGHT=800 OVERLAY_KEY=asterism.desktop OVERLAY_NAME=Desktop PHYS_WIDTH=1.2
# shellcheck disable=SC1090
if [ -f "$conf" ]; then
  # shellcheck disable=SC1091
  . <(tr -d '\r' < "$conf")
fi

# Prefer displays.json primary resolution when present
if [ -f "$ASTERISM_CONFIG_DIR/displays.json" ] && command -v python3 >/dev/null; then
  eval "$(python3 - "$ASTERISM_CONFIG_DIR/displays.json" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])
try:
    d=json.loads(p.read_text())
except Exception:
    raise SystemExit(0)
displays=[x for x in d.get("displays",[]) if x.get("enabled",True)]
if not displays:
    raise SystemExit(0)
prim=next((x for x in displays if x.get("primary")), displays[0])
res=prim.get("resolution") or [1280,800]
print(f"WIDTH={int(res[0])}")
print(f"HEIGHT={int(res[1])}")
print(f"OUTPUT_COUNT={len(displays)}")
PY
)" || true
fi

width=${ASTERISM_WIDTH:-$WIDTH}
height=${ASTERISM_HEIGHT:-$HEIGHT}
overlay_key=${ASTERISM_OVERLAY_KEY:-$OVERLAY_KEY}
overlay_name=${ASTERISM_OVERLAY_NAME:-$OVERLAY_NAME}
phys_width=${ASTERISM_PHYS_WIDTH:-$PHYS_WIDTH}
output_count=${OUTPUT_COUNT:-1}
width=${width//$'\r'/}; height=${height//$'\r'/}
overlay_key=${overlay_key//$'\r'/}; overlay_name=${overlay_name//$'\r'/}
phys_width=${phys_width//$'\r'/}; output_count=${output_count//$'\r'/}

log=$ASTERISM_LOG_DIR/desktop.log
exec >>"$log" 2>&1

asterism_log INFO "asterism-session start key=$overlay_key name=$overlay_name ${width}x${height} outputs=$output_count"

if [ $((width * height)) -gt $((1920 * 1080)) ]; then
  asterism_log ERROR "resolution ${width}x${height} exceeds gamescope OpenVR buffer; abort"
  exit 1
fi

for var in $(compgen -e); do
  case $var in
    LD_LIBRARY_PATH|LD_PRELOAD|STEAM_*|Steam*|SRT_*|PRESSURE_VESSEL_*|MANGOHUD_*| \
    ENABLE_VK_LAYER_VALVE_steam_overlay_*|STEAMVIDEOTOKEN|QT_IM_MODULE|GTK_IM_MODULE|XMODIFIERS)
      unset "$var" || true ;;
  esac
done
# shellcheck disable=SC1091
[ -f /usr/share/deckard/mesavars.sh ] && { set -a; . /usr/share/deckard/mesavars.sh; set +a; }

export ENABLE_GAMESCOPE_WSI=1
export GAMESCOPE_MANGOAPP_SOCKET_DISABLE=1
export ASTERISM_OUTPUT_COUNT=$output_count
export ASTERISM_WIDTH=$width
export ASTERISM_HEIGHT=$height

# Wait for SteamVR processes (WantedBy can race ahead of vrserver readiness).
for _ in $(seq 1 60); do
  if pgrep -x vrserver >/dev/null && pgrep -x vrcompositor >/dev/null; then
    break
  fi
  sleep 0.5
done
if ! pgrep -x vrserver >/dev/null || ! pgrep -x vrcompositor >/dev/null; then
  asterism_log ERROR "SteamVR (vrserver/vrcompositor) not running after wait; abort desktop start"
  exit 1
fi

# Do NOT exit 0 if a leftover gamescope matches — Type=simple would mark the unit
# inactive and SteamVR/WantedBy races would leave the desktop "started" then gone.
if pgrep -f "[g]amescope .*--vr-overlay-key ${overlay_key}" >/dev/null; then
  asterism_log WARN "stale gamescope for $overlay_key still present; sending SIGTERM before start"
  pkill -TERM -f "[g]amescope .*--vr-overlay-key ${overlay_key}" 2>/dev/null || true
  for _ in $(seq 1 40); do
    pgrep -f "[g]amescope .*--vr-overlay-key ${overlay_key}" >/dev/null || break
    sleep 0.25
  done
  pkill -KILL -f "[g]amescope .*--vr-overlay-key ${overlay_key}" 2>/dev/null || true
fi

inner=$root/desktop/asterism-session-inner.sh
chmod +x "$inner" "$0"

cleanup() { asterism_log INFO "asterism-session stopping (signal)"; }
trap cleanup EXIT

# Stable overlay key (no PerWindow) so shell ShowDashboardOverlay(asterism.desktop) works.
# Do NOT enable control-bar-close: close must not terminate the desktop session.
gs_args=(
  --backend openvr
  -W "$width" -H "$height" -w "$width" -h "$height"
  --vr-overlay-key "$overlay_key"
  --vr-overlay-explicit-name "$overlay_name"
  --vr-overlay-default-name "$overlay_name"
  --vr-overlay-physical-width "$phys_width"
  --vr-overlay-show-immediately
  --vr-overlay-enable-click-stabilization
  --vr-overlay-enable-control-bar
  --vr-overlay-enable-control-bar-keyboard
  --expose-wayland
  --cursor-hotspot 5,3
  --cursor /usr/share/steamos/steamos-cursor.png
)

# Multiple enabled displays: PerWindow + KWin output-count (same pixel size; gamescope limit).
if [ "${output_count:-1}" -gt 1 ]; then
  gs_args+=(--virtual-connector-strategy PerWindow)
  asterism_log INFO "multi-display: PerWindow strategy outputs=$output_count"
fi

# Topology sync only — do NOT mutate VR dock/presentation here.
# asterism-spatial.service is the sole owner of startup presentation + World pose
# restore (and ExecStop snapshot). Racing legacy layout dock mutations against
# spatial restore caused theater→dashboard→world fights.
if [ -x "$root/scripts/asterism-layout" ]; then
  (
    export XDG_RUNTIME_DIR=/run/user/$(id -u)
    export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
    "$root/scripts/asterism-layout" sync >/dev/null 2>&1 || true
  ) &
  disown || true
fi

# Optional experimental Gamescope (owner-transform proof). Stock path remains default.
# ASTERISM_GAMESCOPE_BIN / ASTERISM_OPENVR_CTRL come from asterism.conf when set.
gamescope_bin=${ASTERISM_GAMESCOPE_BIN:-gamescope}
export ASTERISM_OPENVR_CTRL=${ASTERISM_OPENVR_CTRL:-0}
# Fast owner-proof path: LD_PRELOAD into stock gamescope (same process / OpenVR client).
# Does not modify /usr gamescope. Unset ASTERISM_OPENVR_CTRL to recover.
owner_so=${ASTERISM_OPENVR_OWNER_SO:-$root/pointer/helper/build/asterism-openvr-owner.so}
if [ "${ASTERISM_OPENVR_CTRL:-0}" = "1" ] || [ "${ASTERISM_OPENVR_CTRL:-0}" = "true" ]; then
  if [ -f "$owner_so" ]; then
    export LD_PRELOAD="$owner_so${LD_PRELOAD:+:$LD_PRELOAD}"
    asterism_log INFO "ASTERISM_OPENVR_CTRL=1 LD_PRELOAD=$owner_so"
  else
    asterism_log WARN "ASTERISM_OPENVR_CTRL=1 but owner so missing: $owner_so"
  fi
fi
asterism_log INFO "gamescope_bin=$gamescope_bin ASTERISM_OPENVR_CTRL=$ASTERISM_OPENVR_CTRL"
# Safety: never silently fall back if an experimental path is configured but missing.
if [ -n "${ASTERISM_GAMESCOPE_BIN:-}" ] && [ ! -x "$gamescope_bin" ]; then
  asterism_log ERROR "ASTERISM_GAMESCOPE_BIN not executable: $gamescope_bin — refusing start (fix conf to recover stock)"
  exit 1
fi

# Clear stale owner socket before exec so a dead inode cannot fake readiness.
rm -f "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/asterism/gamescope-openvr.sock" 2>/dev/null || true

exec "$gamescope_bin" "${gs_args[@]}" -- "$inner"
