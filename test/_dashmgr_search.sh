#!/usr/bin/env bash
# Read-only search of SteamVR dashboard webinterface for Dashboard Manager clues.
set -euo pipefail
D=/opt/steamvr/resources/webinterface/dashboard
OUT=~/asterism/docs/dashboard-state/_search
mkdir -p "$OUT"
cd "$D"

echo "=== dashboard dir listing ===" | tee "$OUT/00_listing.txt"
ls -la | tee -a "$OUT/00_listing.txt"
du -sh . 2>/dev/null | tee -a "$OUT/00_listing.txt"

# ripgrep if available, else grep -R
search() {
  local pat=$1
  local file=$2
  if command -v rg >/dev/null; then
    rg -n --no-heading -i -e "$pat" --glob '*.js' --glob '*.html' --glob '*.json' --glob '*.css' . 2>/dev/null | head -n 80
  else
    grep -RIn --include='*.js' --include='*.html' --include='*.json' "$pat" . 2>/dev/null | head -n 80
  fi
}

patterns=(
  'setInitialTransformForLocation'
  'SGTransform'
  'Failed to get SGTransform'
  'Invalid transform ID'
  'dock-overlay'
  'DockOverlay'
  'Float in World'
  'Return to Dashboard'
  'transformId'
  'transformID'
  'DashboardTab'
  'View in Theater'
  'Multitasking'
  'SceneGraph'
  'sceneGraph'
  'LeftController'
  'RightController'
  'dockOverlay'
  'overlayKey'
  'VRHTML'
  'DashboardManager'
  'dashboardManager'
)

for pat in "${patterns[@]}"; do
  safe=$(echo "$pat" | tr -c 'A-Za-z0-9._-' '_')
  echo "=== SEARCH: $pat ===" | tee "$OUT/search_${safe}.txt"
  search "$pat" | tee -a "$OUT/search_${safe}.txt" || true
  echo | tee -a "$OUT/search_${safe}.txt"
done

# Also dump file names containing interesting words
echo "=== filenames ===" | tee "$OUT/01_filenames.txt"
find . -iname '*dashboard*' -o -iname '*overlay*' -o -iname '*scene*' -o -iname '*transform*' -o -iname '*dock*' 2>/dev/null | head -100 | tee -a "$OUT/01_filenames.txt"

# Count hits for key strings across all JS
echo "=== hit counts ===" | tee "$OUT/02_counts.txt"
for pat in setInitialTransformForLocation SGTransform transformId DashboardManager dock-overlay Float World Theater; do
  c=$(grep -RIn --include='*.js' -c "$pat" . 2>/dev/null | awk -F: '{s+=$NF} END {print s+0}')
  echo "$pat: $c" | tee -a "$OUT/02_counts.txt"
done

echo DONE
