#!/usr/bin/env bash
set -euo pipefail
OUT=~/asterism/docs/dashboard-state/_search
python3 <<'PY'
import re, json
from pathlib import Path
D = Path("/opt/steamvr/resources/webinterface/dashboard")
OUT = Path.home() / "asterism/docs/dashboard-state/_search"
chunk = (D/"chunk~8012d0c89.js").read_text(encoding="utf-8", errors="ignore")

# Extract onVrCmdDockOverlayRequested function body by searching method definition patterns
for pat in [
    r"onVrCmdDockOverlayRequested[=:]?\s*(?:function)?\s*\([^)]*\)\s*\{",
    r"onVrCmdDockOverlayRequested\(([^)]*)\)\{",
    r"_setDockLocation[=:]",
    r"RegisterFrameDockLocation",
    r"m_mapLastRelativeTransformForDockLocation\.set",
    r"endFloatingWindowMove",
    r"startFloatingWindowMove",
]:
    print("PAT", pat, "count", len(re.findall(pat, chunk)))

# Dump large windows around specific unique strings
for key, rad in [
    ("onVrCmdDockOverlayRequested=", 4000),
    ("onVrCmdDockOverlayRequested(", 4000),
    ("_setDockLocation", 4000),
    ("m_mapLastRelativeTransformForDockLocation.set", 3000),
    ("endFloatingWindowMove", 4000),
    ("RegisterFrameDockLocation", 3000),
    ("GetDockLocationTransformID(e)", 2500),
]:
    i = chunk.find(key)
    print(key, "at", i)
    if i>=0:
        (OUT/f"30_{re.sub('[^A-Za-z0-9]+','_',key)[:40]}.js.txt").write_text(chunk[max(0,i-500):i+rad])

# Module 4367 likely exports yW enum - find in chunk by webpack module id
# Look for "World:" near "Theater:" "LeftHand:" "Dashboard:"
for m in re.finditer(r"\{[^}]{0,40}Dashboard[^}]{0,200}World[^}]{0,200}Theater[^}]{0,200}\}", chunk):
    s=m.group(0)
    if "LeftHand" in s or "RightHand" in s or re.search(r":\d", s):
        print("ENUM CAND", s[:300])
        (OUT/"31_dock_enum_object.js.txt").write_text(s)
        break

# Broader search for enum-like
for m in re.finditer(r"(LeftHand|RightHand|Dashboard|World|Theater|Boot)\s*:\s*(\d+)", chunk):
    pass
pairs = re.findall(r"(LeftHand|RightHand|Dashboard|World|Theater|Boot)\s*:\s*(\d+)", chunk)
from collections import Counter
print("enum-like pairs", Counter(pairs).most_common(20))

# Find webpack export yW =
for m in re.finditer(r"yW[=:]", chunk):
    ctx = chunk[m.start():m.start()+300]
    if "Dashboard" in ctx or "World" in ctx or "{" in ctx:
        print("yW ctx", ctx[:250])
        (OUT/"32_yW_export.js.txt").write_text(chunk[max(0,m.start()-100):m.start()+800])
        break

# Also search libraries folder for openvr/vrhtml bindings
lib = D/"libraries"
if lib.is_dir():
    for p in lib.rglob("*"):
        if p.is_file() and p.suffix in {".js",".json"}:
            t=p.read_text(encoding="utf-8", errors="ignore")
            if "requestSGTransform" in t or "GetStoredTransform" in t or "yWq" in t:
                print("LIB HIT", p.name, "len", len(t))

print("DONE")
PY
