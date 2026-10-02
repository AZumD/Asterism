#!/usr/bin/env bash
set -euo pipefail
python3 <<'PY'
import pathlib,re
js=pathlib.Path("/opt/steamvr/resources/webinterface/dashboard/systemui.js").read_text(errors="ignore")
# VRClient methods used
print("VRClient.", sorted(set(re.findall(r"VRClient\.([A-Za-z0-9_]+)", js)))[:60])
print("VRDashboardManager.", sorted(set(re.findall(r"VRDashboardManager\.([A-Za-z0-9_]+)", js)))[:40])
print("VROverlay.", sorted(set(re.findall(r"VROverlay\.([A-Za-z0-9_]+)", js)))[:40])
# context of the Steam/Desktop list
i=js.find('["Steam","Desktop"')
print("list ctx", js[i:i+500])
# RunningApp in chunk
ch=pathlib.Path("/opt/steamvr/resources/webinterface/dashboard/chunk~8012d0c89.js").read_text(errors="ignore")
print("RunningApp ctxs:")
for m in re.finditer("RunningApp", ch):
    print(repr(ch[max(0,m.start()-80):m.start()+120].replace("\n"," "))[:180])
    break
# control bar close / quit overlay
for term in ["control-bar","ControlBar","CloseButton","QuitOverlay","DismissOverlay","bCanClose","can_close","close_overlay"]:
    print(term, ch.count(term), js.count(term))
PY
# gamescope help for close
gamescope --help 2>&1 | rg -i 'control-bar|close|modal|dashboard' | head -20
