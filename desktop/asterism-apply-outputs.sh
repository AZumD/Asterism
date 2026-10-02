#!/usr/bin/env bash
# Place nested KWin outputs side-by-side with no overlap (fixes bleed between displays).
# Runs inside the Asterism nested Plasma session (asterism_nested Wayland).
set -euo pipefail
root=${ASTERISM_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
# shellcheck disable=SC1091
. "$root/scripts/_env.sh"

width=${ASTERISM_WIDTH:-1280}
height=${ASTERISM_HEIGHT:-800}
count=${ASTERISM_OUTPUT_COUNT:-1}
width=${width//$'\r'/}; height=${height//$'\r'/}; count=${count//$'\r'/}
[[ "$count" =~ ^[1-9][0-9]*$ ]] || count=1

if [ "$count" -lt 2 ]; then
  asterism_log INFO "apply-outputs: single output; nothing to place"
  exit 0
fi

# Prefer displays.json enabled order / widths when available.
mapfile -t widths < <(python3 - "$ASTERISM_CONFIG_DIR/displays.json" "$width" <<'PY' || true
import json, sys
from pathlib import Path
fallback = int(sys.argv[2])
p = Path(sys.argv[1])
try:
    d = json.loads(p.read_text())
except Exception:
    print(fallback); raise SystemExit(0)
enabled = [x for x in d.get("displays", []) if x.get("enabled", True)]
if not enabled:
    print(fallback); raise SystemExit(0)
enabled.sort(key=lambda x: (not x.get("primary", False), x.get("id", "")))
for x in enabled:
    w = (x.get("resolution") or [fallback, 800])[0]
    print(int(w))
PY
)

if [ "${#widths[@]}" -lt 2 ]; then
  widths=()
  for _ in $(seq 1 "$count"); do widths+=("$width"); done
fi

# Wait for kscreen / outputs
for _ in $(seq 1 60); do
  if command -v kscreen-doctor >/dev/null && kscreen-doctor -o 2>/dev/null | grep -q 'WL-'; then
    break
  fi
  sleep 0.5
done

# Strip ANSI, collect WL-* names in order.
mapfile -t outs < <(
  kscreen-doctor -o 2>/dev/null \
    | sed 's/\x1b\[[0-9;]*m//g' \
    | sed -n 's/.*\(WL-[0-9][0-9]*\).*/\1/p' \
    | awk '!seen[$0]++' \
    | head -n "$count"
)

if [ "${#outs[@]}" -lt 2 ]; then
  asterism_log WARN "apply-outputs: fewer than 2 outputs visible (got: ${outs[*]:-none}); skip"
  exit 0
fi

x=0
args=()
i=0
for out in "${outs[@]}"; do
  w=${widths[$i]:-$width}
  args+=("output.${out}.position.${x},0")
  asterism_log INFO "apply-outputs: ${out} -> ${x},0 (width=$w)"
  x=$((x + w))
  i=$((i + 1))
done

if kscreen-doctor "${args[@]}" 2>/tmp/asterism-kscreen.err; then
  asterism_log INFO "apply-outputs: kscreen-doctor OK (${#outs[@]} outputs, span=${x}x${height})"
else
  asterism_log WARN "apply-outputs: kscreen-doctor failed: $(tr '\n' ' ' </tmp/asterism-kscreen.err)"
  # Fallback: numeric output ids 1..N
  x=0
  args=()
  i=0
  for n in $(seq 1 "${#outs[@]}"); do
    w=${widths[$i]:-$width}
    args+=("output.${n}.position.${x},0")
    x=$((x + w))
    i=$((i + 1))
  done
  if kscreen-doctor "${args[@]}" 2>/tmp/asterism-kscreen2.err; then
    asterism_log INFO "apply-outputs: kscreen-doctor OK via numeric ids"
  else
    asterism_log WARN "apply-outputs: numeric fallback failed: $(tr '\n' ' ' </tmp/asterism-kscreen2.err)"
    exit 1
  fi
fi
