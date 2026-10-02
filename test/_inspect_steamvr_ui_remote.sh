#!/usr/bin/env bash
# Read-only SteamVR UI inspection for Asterism (run on Steam Frame via SSH).
set -euo pipefail

ROOT=/opt/steamvr/resources/webinterface
echo "=== versions ==="
cat /opt/steamvr/bin/version.txt
grep -E '^(BUILD_ID|VERSION_ID|VARIANT_ID)=' /etc/os-release

echo "=== sha256 (likely patch targets) ==="
sha256sum \
  "$ROOT/dashboard/systemui.html" \
  "$ROOT/dashboard/systemui.js" \
  "$ROOT/dashboard/chunk~2e670652e.js" \
  "$ROOT/dashboard/chunk~8012d0c89.js"

python3 <<'PY'
import pathlib, re
root = pathlib.Path("/opt/steamvr/resources/webinterface/dashboard")
files = [
    "systemui.js",
    "chunk~2e670652e.js",
    "chunk~8012d0c89.js",
    "libraries/libraries~989880c99.js",
]
terms = [
    "QuickAccess", "QuickAccessMenu", "FrameMenu", "Fan", "fan",
    "Performance", "Slider", "VRWebUI", "vrwebui", "PostMessage",
    "RunProcess", "ExecProcess", "spawn", "RegisterForMessages",
    "BrowserBridge", "ShowDashboard", "HideDashboard", "Desktop",
]
for fname in files:
    p = root / fname
    d = p.read_text(errors="ignore")
    print(f"\n--- {fname} ({len(d)} bytes) ---")
    for t in terms:
        c = d.count(t)
        if c:
            print(f"  {t}: {c}")
    for label, pat in [
        ("QuickAccessMenu ctx", r".{0,100}QuickAccessMenu.{0,250}"),
        ("VRWebUI ctx", r".{0,80}VRWebUI.{0,180}"),
    ]:
        m = re.search(pat, d)
        if m:
            s = m.group(0).replace("\n", " ")
            print(f"  {label}: {s[:220]}")

print("\n=== fan search all dashboard js ===")
for p in sorted(root.glob("*.js")):
    d = p.read_text(errors="ignore")
    if re.search(r"\bfan\b|FanSpeed|fan_control|FanControl", d, re.I):
        print("  fan-like:", p.name)
PY

echo "=== plugin / extension hints ==="
rg -l -i "CreateDashboardOverlay|dashboard overlay|external overlay" /opt/steamvr/tools /opt/steamvr/resources 2>/dev/null | head -15 || true

echo "=== vrwebhelper user-data / cache ==="
du -sh "$HOME/.cache/SteamVR/htmlcache" 2>/dev/null || true

echo "=== user-owned steamvr web overrides? ==="
find "$HOME" -path "*webinterface/dashboard/systemui.js" 2>/dev/null | head

echo "=== openvr overlay API sample ==="
ls /opt/steamvr/tools/hellovr_vulkan_linux 2>/dev/null | head
