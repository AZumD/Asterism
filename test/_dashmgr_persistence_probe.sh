#!/usr/bin/env bash
set -euo pipefail
OUT=~/asterism/docs/dashboard-state/_search
python3 <<'PY'
import re, json, os, subprocess
from pathlib import Path

OUT = Path.home() / "asterism/docs/dashboard-state/_search"
D = Path("/opt/steamvr/resources/webinterface/dashboard")
chunk = (D/"chunk~8012d0c89.js").read_text(encoding="utf-8", errors="ignore")

# Find _setDockLocation implementation
i = chunk.find("_setDockLocation")
(OUT/"33__setDockLocation_impl.js.txt").write_text(chunk[max(0,i-200):i+3500])

# Find GetDockLocationTransformID implementation  
for key in ["GetDockLocationTransformID", "RegisterFrameDockLocation", "frames_local_undocked"]:
    i = chunk.find(key)
    print(key, i)
    if i>=0:
        (OUT/f"34_{key}.js.txt").write_text(chunk[max(0,i-200):i+2500])

# Search vrsettings / config for dock-related keys on disk
candidates = []
for root in [Path.home()/".config/openvr", Path.home()/".steam", Path.home()/".local/share/Steam", Path("/opt/steamvr")]:
    if not root.exists():
        continue
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".vrsettings", ".json", ".vrmanifest", ".txt"}:
            continue
        if p.stat().st_size > 5_000_000:
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if re.search(r"dockLocation|FloatInWorld|xfTransform|frameID|LastRelativeTransform|dashboard.*world", t, re.I):
            candidates.append(str(p))
(OUT/"35_disk_state_candidates.txt").write_text("\n".join(candidates[:100]))
print("disk candidates", len(candidates))
for c in candidates[:20]:
    print(" ", c)

# vrcmd help for dock-overlay
env = os.environ.copy()
env["LD_LIBRARY_PATH"] = "/opt/steamvr/bin/linuxarm64:" + env.get("LD_LIBRARY_PATH","")
try:
    out = subprocess.check_output(["/opt/steamvr/bin/linuxarm64/vrcmd","--help"], env=env, stderr=subprocess.STDOUT, text=True, errors="ignore")
except subprocess.CalledProcessError as e:
    out = e.output or str(e)
(OUT/"36_vrcmd_help.txt").write_text(out)
print("vrcmd help lines", len(out.splitlines()))

# Check for chrome remote debugging on vrwebhelper
try:
    out = subprocess.check_output(["ps","-ef"], text=True, errors="ignore")
    lines = [ln for ln in out.splitlines() if "vrwebhelper" in ln.lower() or "systemui" in ln.lower()]
    (OUT/"37_vrwebhelper_procs.txt").write_text("\n".join(lines))
    print("vrwebhelper procs", len(lines))
    for ln in lines[:10]:
        print(ln[:200])
except Exception as e:
    print(e)

print("DONE")
PY
