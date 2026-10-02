#!/usr/bin/env bash
# Stage Phase C + optional dashmgr bridge files for one sudo apply.
set -euo pipefail
cd /home/steamos/asterism
OUT=/tmp/asterism-dashmgr-patch-out
rm -rf "$OUT"
mkdir -p "$OUT"

HTML=/opt/steamvr/resources/webinterface/dashboard/systemui.html
CHUNK=/opt/steamvr/resources/webinterface/dashboard/chunk~8012d0c89.js
TAG='<script defer="defer" src="asterism_shell.js?contenthash=asterism2"></script>'

cp -a patches/asterism_shell.js "$OUT/asterism_shell.js"
cp -a "$HTML" "$OUT/systemui.html"
cp -a "$CHUNK" "$OUT/chunk~8012d0c89.js"

python3 - "$OUT/systemui.html" "$TAG" <<'PY'
import sys
path, tag = sys.argv[1], sys.argv[2]
text = open(path, "r", encoding="utf-8", errors="surrogateescape").read()
if "asterism_shell.js" not in text:
    i = text.lower().rfind("</body>")
    if i < 0:
        raise SystemExit("no body")
    end = text[i : i + 7]
    text = text[:i] + tag + end + text[i + 7 :]
    open(path, "w", encoding="utf-8", errors="surrogateescape").write(text)
    print("html injected")
else:
    print("html already had inject tag (kept)")
PY

# Dry-run bridge into staged chunk (not live /opt yet)
NEEDLE='window.Dashboard=this,this.m_dashboardThumbnailsChangedEventHandle='
BRIDGE='window.Dashboard=this,window.__ASTERISM_STEAMVR||(window.__ASTERISM_STEAMVR={version:1,yWq:i.yWq,getFramesForSummonKey:function(e){return M.JJ.GetFramesWithAssociatedSummonKeys(e)||[]}}),this.m_dashboardThumbnailsChangedEventHandle='
python3 - "$OUT/chunk~8012d0c89.js" "$NEEDLE" "$BRIDGE" <<'PY'
import sys, hashlib
path, needle, bridge = sys.argv[1], sys.argv[2], sys.argv[3]
data = open(path, "rb").read().decode("utf-8", "surrogateescape")
print("stock_sha", hashlib.sha256(open("/opt/steamvr/resources/webinterface/dashboard/chunk~8012d0c89.js","rb").read()).hexdigest())
print("needle_count", data.count(needle))
if data.count(needle) != 1:
    raise SystemExit("bad needle")
data = data.replace(needle, bridge, 1)
open(path, "w", encoding="utf-8", errors="surrogateescape").write(data)
print("staged_chunk_sha", hashlib.sha256(open(path,"rb").read()).hexdigest())
print("bridge_present", bridge in data)
PY

cat > "$OUT/APPLY.sh" <<'EOS'
#!/usr/bin/env bash
set -euo pipefail
OUT=/tmp/asterism-dashmgr-patch-out
DASH=/opt/steamvr/resources/webinterface/dashboard
# Backup first via Asterism tooling if available
if [ -x /home/steamos/asterism/scripts/backup-steamvr-ui.sh ]; then
  /home/steamos/asterism/scripts/backup-steamvr-ui.sh || true
fi
install -m 0644 "$OUT/asterism_shell.js" "$DASH/asterism_shell.js"
install -m 0644 "$OUT/systemui.html" "$DASH/systemui.html"
# Phase 2 chunk bridge (skip if you only want Phase 1 shell):
install -m 0644 "$OUT/chunk~8012d0c89.js" "$DASH/chunk~8012d0c89.js"
mkdir -p /home/steamos/.local/state/asterism
date -Iseconds > /home/steamos/.local/state/asterism/ui-patch-installed
date -Iseconds > /home/steamos/.local/state/asterism/dashmgr-bridge-installed
echo "OK installed. Clear htmlcache + restart SteamVR."
EOS
chmod +x "$OUT/APPLY.sh"

echo "STAGED $OUT"
ls -la "$OUT"
sha256sum "$OUT"/*
echo
echo "Apply with: sudo /tmp/asterism-dashmgr-patch-out/APPLY.sh"
