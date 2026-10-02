#!/usr/bin/env bash
set -euo pipefail
OUT=~/asterism/docs/dashboard-state/_search
python3 <<'PY'
import re, json
from pathlib import Path

D = Path("/opt/steamvr/resources/webinterface/dashboard")
OUT = Path.home() / "asterism/docs/dashboard-state/_search"
chunk = (D / "chunk~8012d0c89.js").read_text(encoding="utf-8", errors="ignore")
systemui = (D / "systemui.js").read_text(encoding="utf-8", errors="ignore")
alljs = chunk + "\n" + systemui
for p in D.glob("chunk*.js"):
    if p.name != "chunk~8012d0c89.js":
        alljs += "\n" + p.read_text(encoding="utf-8", errors="ignore")

def windows(key, radius=2500, limit=5):
    out=[]
    start=0
    while len(out)<limit:
        i=alljs.find(key, start)
        if i<0: break
        out.append(alljs[max(0,i-radius):i+radius])
        start=i+len(key)
    return out

targets = {
    "onVrCmdDockOverlayRequested": 3500,
    "vrcmd_dock_overlay": 2000,
    "GetDockLocationTransformID": 2500,
    "m_mapLastRelativeTransformForDockLocation": 2500,
    "dockLocation": 800,
    "requestSGTransform": 2500,
    "requestSGTransformRelative": 2000,
    "GetFrameWithTabId": 2000,
    "GetFramesWithAssociatedSummonKeys": 2000,
    "associatedSummonOverlayKeys": 2000,
    "SetDockLocation": 2000,
    "setDockLocation": 2000,
    "FloatInWorld": 1500,
    "ShowTheaterScreen": 1500,
    "DockOnDashboard": 1500,
    "yWq": 500,
    "frameID": 800,
    "RegisterForAllOverlayInfo": 2000,
    "GetOverlayInfo": 1500,
}

for key, rad in targets.items():
    wins = windows(key, rad, 3)
    for idx, w in enumerate(wins):
        safe = re.sub(r'[^A-Za-z0-9]+','_', key)[:50]
        (OUT / f"20_{safe}_{idx}.js.txt").write_text(w)
    print(f"{key}: {len(wins)} windows")

# Try to recover enum yWq by looking for assignments like yWq= or Dashboard:0
enum_ctx = []
for m in re.finditer(r"yWq\s*[=:]", alljs):
    enum_ctx.append(alljs[m.start():m.start()+400].replace("\n"," "))
    if len(enum_ctx)>=10: break
# Also LeftHand/RightHand/Theater near numeric enums
for m in re.finditer(r"(Dashboard|World|Theater|LeftHand|RightHand|Boot)\s*:\s*\d+", alljs):
    enum_ctx.append(alljs[max(0,m.start()-80):m.start()+120].replace("\n"," "))
(OUT / "21_enum_candidates.txt").write_text("\n---\n".join(enum_ctx[:40]))

# Find class/store JJ (frame manager) methods via GetFrame*
jj_methods = sorted(set(re.findall(r"M\.JJ\.([A-Za-z0-9_]+)", alljs)))
(OUT / "22_JJ_methods.json").write_text(json.dumps(jj_methods, indent=2))
print("JJ methods", len(jj_methods))
print(jj_methods[:60])

# docking property names
dock_props = sorted(set(re.findall(r"docking\.([A-Za-z0-9_]+)", alljs)))
(OUT / "23_docking_props.json").write_text(json.dumps(dock_props, indent=2))
print("docking props", dock_props)

# frame props
frame_props = sorted(set(re.findall(r"frame\.([A-Za-z0-9_]+)", alljs)))
(OUT / "24_frame_props.json").write_text(json.dumps(frame_props[:200], indent=2))

# uS7 scenegraph service methods
us7 = sorted(set(re.findall(r"uS7\.getInstance\(\)\.([A-Za-z0-9_]+)", alljs)))
us7 += sorted(set(re.findall(r"\.requestSG[A-Za-z0-9_]*", alljs)))
(OUT / "25_scenegraph_calls.json").write_text(json.dumps(sorted(set(us7)), indent=2))
print("scenegraph calls", sorted(set(us7)))

print("DONE")
PY
