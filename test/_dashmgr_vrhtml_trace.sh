#!/usr/bin/env bash
set -euo pipefail
OUT=~/asterism/docs/dashboard-state/_search
python3 <<'PY'
import pathlib, re, json
from pathlib import Path

D = Path("/opt/steamvr/resources/webinterface/dashboard")
OUT = Path.home() / "asterism/docs/dashboard-state/_search"
chunk = (D / "chunk~8012d0c89.js").read_text(encoding="utf-8", errors="ignore")
systemui = (D / "systemui.js").read_text(encoding="utf-8", errors="ignore")

# Full VRHTML method inventory
methods = sorted(set(re.findall(r"VRHTML\.([A-Za-z0-9_]+)", chunk + systemui)))
(OUT / "10_vrhtml_all_methods.json").write_text(json.dumps(methods, indent=2))
interesting = [m for m in methods if re.search(r"(Transform|Dock|Frame|Pose|Overlay|Scene|Grab|Theater|World|Location|SG|Stored|Basis|Width|Curv|Scale|Dashboard)", m, re.I)]
(OUT / "11_vrhtml_spatial_methods.json").write_text(json.dumps(interesting, indent=2))
print("spatial-ish VRHTML methods:")
for m in interesting:
    print(" ", m)

# For each spatial method, dump contexts
report = {}
for name in interesting:
    ctxs = []
    for src_name, t in [("chunk~8012d0c89.js", chunk), ("systemui.js", systemui)]:
        for m in re.finditer(re.escape("VRHTML." + name), t):
            s = max(0, m.start()-200); e = min(len(t), m.end()+350)
            ctxs.append({"file": src_name, "pos": m.start(), "ctx": t[s:e].replace("\n"," ")})
            if len(ctxs) >= 8:
                break
    report[name] = ctxs
(OUT / "12_vrhtml_spatial_contexts.json").write_text(json.dumps(report, indent=2))

# Broader windows for key strings
keys = [
    "setInitialTransformForLocation",
    "GetStoredTransform",
    "CalcDashboardTransform",
    "RegisterForFrameDockLocationRequests",
    "NextSGID",
    "MultiplyTransforms",
    "ChangeBasis",
    "DockOverlay",
    "Failed to get SGTransform",
    "Invalid transform ID",
    "Float in World",
    "View in Theater",
    "Return to Dashboard",
]
for key in keys:
    i = chunk.find(key)
    src = chunk
    fname = "chunk"
    if i < 0:
        i = systemui.find(key)
        src = systemui
        fname = "systemui"
    if i < 0:
        # search other chunks
        found = False
        for p in D.glob("chunk*.js"):
            t = p.read_text(encoding="utf-8", errors="ignore")
            i = t.find(key)
            if i >= 0:
                src = t; fname = p.name; found = True; break
        if not found:
            print("MISSING", key)
            continue
    win = src[max(0,i-2000):i+3000]
    safe = re.sub(r"[^A-Za-z0-9]+", "_", key)[:60]
    (OUT / f"13_{safe}.js.txt").write_text(win)
    print(f"window {key} from {fname} @ {i}")

# Localization dump
loc = json.loads((D/"localization"/"dashboard_english.json").read_text(encoding="utf-8", errors="ignore"))
(OUT / "06_loc_interesting.json").write_text(json.dumps({
    k:v for k,v in loc.items()
    if any(w in (k+" "+str(v)).lower() for w in ["float","theater","dock","world","dashboard","controller","multitask","curve","resize","grab","window"])
}, indent=2, ensure_ascii=False))

# strings in vrcmd related to dock
import subprocess
vrcmd = "/opt/steamvr/bin/linuxarm64/vrcmd"
try:
    out = subprocess.check_output(["strings", vrcmd], text=True, errors="ignore")
    lines = [ln for ln in out.splitlines() if re.search(r"dock|theater|world|dashboard|transform|overlay", ln, re.I)]
    (OUT / "14_vrcmd_strings.txt").write_text("\n".join(lines[:400]))
    print("vrcmd string hits", len(lines))
except Exception as e:
    print("vrcmd strings failed", e)

print("DONE")
PY
# pull key windows home via listing
ls -la "$OUT"/13_*.js.txt "$OUT"/11_*.json "$OUT"/10_*.json 2>/dev/null | head
