#!/usr/bin/env bash
# Inspect systemui for shell-control injection points (read-only).
set -euo pipefail
JS=/opt/steamvr/resources/webinterface/dashboard/systemui.js
CHUNK=/opt/steamvr/resources/webinterface/dashboard/chunk~8012d0c89.js
python3 <<'PY'
import pathlib,re
js=pathlib.Path("/opt/steamvr/resources/webinterface/dashboard/systemui.js").read_text(errors="ignore")
ch=pathlib.Path("/opt/steamvr/resources/webinterface/dashboard/chunk~8012d0c89.js").read_text(errors="ignore")
for label,d in [("systemui",js),("chunk8012",ch)]:
    print("===",label,"len",len(d),"===")
    for term in ["FrameMenu","QuickAccessMenu","Library","Settings","Hamburger","NavButton","BottomBar","Toolbar","RunningApp","CloseOverlay","LaunchApplication","ShowDashboard","fetch(","XMLHttpRequest","127.0.0.1","localhost"]:
        print(f"  {term}: {d.count(term)}")
# snippets around FrameMenu / Library nav
for pat in [r".{0,60}FrameMenu.{0,200}", r".{0,80}Library.{0,120}", r".{0,60}ShowDashboard.{0,100}", r".{0,80}LaunchApplication.{0,150}"]:
    m=re.search(pat, js)
    if m: print("SYS", m.group(0)[:220].replace("\n"," "))
    m=re.search(pat, ch)
    if m: print("CHK", m.group(0)[:220].replace("\n"," "))
# look for icon names / desktop string
for pat in [r"desktop[^\"']{0,40}", r"IconDesktop", r"\"Desktop\""]:
    ms=list(re.finditer(pat, js, re.I))
    print("desktop-like in systemui", len(ms))
    for m in ms[:5]:
        print(" ", js[max(0,m.start()-40):m.start()+80].replace("\n"," ")[:140])
PY
echo "=== version/hashes ==="
cat /opt/steamvr/bin/version.txt
sha256sum /opt/steamvr/resources/webinterface/dashboard/systemui.js /opt/steamvr/resources/webinterface/dashboard/systemui.html
