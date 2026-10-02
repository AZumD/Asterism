#!/usr/bin/env bash
set -euo pipefail
python3 <<'PY'
import pathlib,re
js=pathlib.Path("/opt/steamvr/resources/webinterface/dashboard/systemui.js").read_text(errors="ignore")
ch=pathlib.Path("/opt/steamvr/resources/webinterface/dashboard/chunk~8012d0c89.js").read_text(errors="ignore")
# Find context around Desktop summon / Jump / dashboardBar
for label,d in [("systemui",js),("chunk",ch)]:
    print("====",label,"====")
    for term in ["Jump_To_DashboardBar","Summon","AssociatedSummon","dashboardBar","RunningApp","CloseDashboard","DestroyOverlay","HideOverlay","ShowDashboardOverlay","overlayKey","Desktop"]:
        idxs=[m.start() for m in re.finditer(re.escape(term), d)]
        print(term, len(idxs))
        for i in idxs[:2]:
            print(" ",repr(d[max(0,i-70):i+160].replace("\n"," "))[:200])
# Find 127.0.0.1 context in chunk
i=ch.find("127.0.0.1")
print("127 context", repr(ch[max(0,i-100):i+150]))
# VRHTML usage
for m in re.finditer(r"VRHTML\.[A-Za-z0-9_.]+", js):
    pass
methods=sorted(set(re.findall(r"VRHTML\.([A-Za-z0-9_]+)", js)))
print("VRHTML methods systemui", methods[:40])
methods2=sorted(set(re.findall(r"VRHTML\.([A-Za-z0-9_.]+)", ch)))
print("VRHTML chunk sample", methods2[:50])
# Browser bind / SteamClient
print("SteamClient count", ch.count("SteamClient"), js.count("SteamClient"))
print("VRClient count", ch.count("VRClient"), js.count("VRClient"))
PY
