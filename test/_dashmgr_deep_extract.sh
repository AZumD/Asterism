#!/usr/bin/env bash
# Deep read-only extraction of Dashboard Manager / SGTransform paths from SteamVR UI.
set -euo pipefail
OUT=~/asterism/docs/dashboard-state/_search
mkdir -p "$OUT"
python3 <<'PY'
import pathlib, re, json, collections
from pathlib import Path

D = Path("/opt/steamvr/resources/webinterface/dashboard")
OUT = Path.home() / "asterism/docs/dashboard-state/_search"
OUT.mkdir(parents=True, exist_ok=True)

files = sorted(D.rglob("*"))
js_files = [p for p in files if p.suffix in {".js", ".html", ".json"} and p.is_file()]

def load(p):
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return ""

# Index all texts
texts = {p: load(p) for p in js_files}

patterns = [
    r"setInitialTransformForLocation",
    r"SGTransform",
    r"Failed to get SGTransform",
    r"Invalid transform ID",
    r"transformId",
    r"transformID",
    r"VRDashboardManager",
    r"DashboardManager",
    r"dockOverlay",
    r"DockOverlay",
    r"dock-overlay",
    r"Float in World",
    r"Return to Dashboard",
    r"View in Theater",
    r"Theater",
    r"Multitasking",
    r"LeftController",
    r"RightController",
    r"DashboardTab",
    r"SceneGraph",
    r"sceneGraph",
    r"overlayKey",
    r"overlayHandle",
    r"VRHTML",
    r"VRClient",
    r"SetOverlayTransform",
    r"presentation",
    r"locationType",
    r"LocationType",
    r"EDashboard",
    r"DashboardLocation",
    r"Grab",
    r"curvature",
    r"scaleSlider",
]

hits = collections.defaultdict(list)
for pat in patterns:
    rx = re.compile(pat)
    for p, t in texts.items():
        for m in rx.finditer(t):
            start = max(0, m.start() - 180)
            end = min(len(t), m.end() + 220)
            ctx = t[start:end].replace("\n", "\\n")
            hits[pat].append({"file": str(p.relative_to(D)), "pos": m.start(), "ctx": ctx})

summary = {k: len(v) for k, v in hits.items()}
(OUT / "03_hit_summary.json").write_text(json.dumps(summary, indent=2))
print("HIT SUMMARY")
for k, n in sorted(summary.items(), key=lambda x: -x[1]):
    if n:
        print(f"  {n:4d}  {k}")

# Dump rich contexts for the critical ones
critical = [
    "setInitialTransformForLocation",
    "SGTransform",
    "Failed to get SGTransform",
    "Invalid transform ID",
    "VRDashboardManager",
    "transformId",
    "transformID",
    "dockOverlay",
    "DockOverlay",
    "LocationType",
    "locationType",
    "EDashboard",
]
report = []
for pat in critical:
    for h in hits.get(pat, [])[:30]:
        report.append({"pattern": pat, **h})
(OUT / "04_critical_contexts.json").write_text(json.dumps(report, indent=2))

# Extract VRDashboardManager.Method and VRClient.Method inventories from all JS
methods = collections.defaultdict(set)
for p, t in texts.items():
    for m in re.finditer(r"\b(VRDashboardManager|VRClient|VROverlay|VRHTML|VRSceneGraph)\.([A-Za-z0-9_]+)", t):
        methods[m.group(1)].add(m.group(2))
methods_out = {k: sorted(v) for k, v in methods.items()}
(OUT / "05_api_methods.json").write_text(json.dumps(methods_out, indent=2))
print("\nAPI methods:")
for k, v in methods_out.items():
    print(f"  {k}: {len(v)} methods")
    print("   ", ", ".join(v[:40]))
    if len(v) > 40:
        print("    ...", ", ".join(v[40:80]))

# Localization strings for Float/Theater/Dock
loc = D / "localization" / "dashboard_english.json"
if loc.is_file():
    try:
        data = json.loads(loc.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        data = {}
    interesting = {}
    for k, v in (data.items() if isinstance(data, dict) else []):
        kl = k.lower() + " " + str(v).lower()
        if any(w in kl for w in ["float", "theater", "theatre", "dock", "world", "dashboard", "controller", "multitask", "curve", "resize", "grab"]):
            interesting[k] = v
    (OUT / "06_loc_interesting.json").write_text(json.dumps(interesting, indent=2, ensure_ascii=False))
    print(f"\nlocalization interesting keys: {len(interesting)}")

# Broader window around setInitialTransformForLocation
for p, t in texts.items():
    i = t.find("setInitialTransformForLocation")
    if i >= 0:
        chunk = t[max(0, i - 1500): i + 2500]
        (OUT / "07_setInitialTransform_window.js.txt").write_text(chunk)
        print(f"\nwrote window from {p.name} len={len(chunk)}")
    i = t.find("SGTransform")
    if i >= 0 and "Failed to get SGTransform" in t:
        # find the failed message
        j = t.find("Failed to get SGTransform")
        chunk = t[max(0, j - 1200): j + 1800]
        (OUT / "08_SGTransform_error_window.js.txt").write_text(chunk)
        print(f"wrote SGTransform error window from {p.name}")

# Search for property-like presentation enums near World/Dashboard/Theater
enum_hits = []
for p, t in texts.items():
    for m in re.finditer(r".{0,40}(World|Theater|Dashboard|ControllerLeft|ControllerRight|LeftController|RightController).{0,40}", t):
        s = m.group(0)
        if any(x in s for x in ["Location", "Dock", "Present", "Transform", "Float", "EDash", "eDash", "location"]):
            enum_hits.append({"file": str(p.relative_to(D)), "ctx": s.replace("\n", " ")})
(OUT / "09_enum_like.json").write_text(json.dumps(enum_hits[:200], indent=2))
print(f"enum-like hits: {len(enum_hits)}")

print("\nDONE deep extract")
PY
