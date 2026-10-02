#!/usr/bin/env bash
# Stage (do NOT auto-apply) dashmgr bridge v2: UndockedOverlay registry +
# applyWorldTransformForSummonKey / getLiveWorldTransformForSummonKey.
#
# Base: currently bridged live chunk (v1)
#   SHA256 272c1e40f75bafe28a7108485295681ffdac2a322a6a10f3e2d35278d596dfd9
# SteamVR build: 1790822802
#
# Usage (on Frame):
#   bash scripts/stage-steamvr-dashmgr-bridge-v2.sh
#   # review /tmp/asterism-dashmgr-bridge-v2/
#   # sudo APPLY.sh only after manual review
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
DASH=${STEAMVR_WEBUI:-/opt/steamvr/resources/webinterface/dashboard}
CHUNK=$DASH/chunk~8012d0c89.js
EXPECTED_BUILD=1790822802
EXPECTED_V1_SHA=272c1e40f75bafe28a7108485295681ffdac2a322a6a10f3e2d35278d596dfd9
STAGE=${ASTERISM_BRIDGE_V2_STAGE:-/tmp/asterism-dashmgr-bridge-v2}

sha() { sha256sum "$1" | awk '{print $1}'; }

if [ ! -f "$CHUNK" ]; then
  echo "STOP: missing $CHUNK (run on Frame with SteamVR installed)" >&2
  exit 2
fi

live_sha=$(sha "$CHUNK")
if [ "$live_sha" != "$EXPECTED_V1_SHA" ]; then
  echo "STOP: chunk is not the known v1 bridged hash" >&2
  echo "  expected $EXPECTED_V1_SHA" >&2
  echo "  actual   $live_sha" >&2
  exit 2
fi

# Exact needles (each must appear once in the v1 bridged chunk)
BRIDGE_V1='window.__ASTERISM_STEAMVR||(window.__ASTERISM_STEAMVR={version:1,yWq:i.yWq,getFramesForSummonKey:function(e){return M.JJ.GetFramesWithAssociatedSummonKeys(e)||[]}}),this.m_dashboardThumbnailsChangedEventHandle='

BRIDGE_V2='window.__ASTERISM_STEAMVR=Object.assign(window.__ASTERISM_STEAMVR||{},{version:2,yWq:i.yWq,_uo:(window.__ASTERISM_STEAMVR&&window.__ASTERISM_STEAMVR._uo)||{},getFramesForSummonKey:function(e){return M.JJ.GetFramesWithAssociatedSummonKeys(e)||[]},applyWorldTransformForSummonKey:function(e,t){var r=M.JJ.GetFramesWithAssociatedSummonKeys(e)||[],n=r[0];if(!n||!n.docking)return{ok:!1,error:"no frame"};if(String(e).indexOf("asterism.desktop")!==0)return{ok:!1,error:"non-asterism"};var a={translation:{x:+(t.translation&&t.translation.x),y:+(t.translation&&t.translation.y),z:+(t.translation&&t.translation.z)},rotation:{w:+(t.rotation&&t.rotation.w),x:+(t.rotation&&t.rotation.x),y:+(t.rotation&&t.rotation.y),z:+(t.rotation&&t.rotation.z)}};t.scale!=null&&(a.scale="object"==typeof t.scale?{x:+t.scale.x,y:+t.scale.y,z:+t.scale.z}:+t.scale),n.docking.m_mapLastRelativeTransformForDockLocation.set(i.yWq.World,a);var s=(window.__ASTERISM_STEAMVR._uo||{})[n.frameID];return s&&"function"==typeof s.setState?(s.setState({xfTransform:a}),{ok:!0,path:"setState+map",frameID:String(n.frameID),live:!0}):{ok:!0,path:"map-only",frameID:String(n.frameID),live:!1}},getLiveWorldTransformForSummonKey:function(e){var r=M.JJ.GetFramesWithAssociatedSummonKeys(e)||[],n=r[0];if(!n)return{ok:!1,error:"no frame"};if(String(e).indexOf("asterism.desktop")!==0)return{ok:!1,error:"non-asterism"};var s=(window.__ASTERISM_STEAMVR._uo||{})[n.frameID],o=s&&s.state&&s.state.xfTransform;if(!o)return{ok:!1,error:"no live xfTransform",frameID:n.frameID!=null?String(n.frameID):null,dockLocation:n.docking&&n.docking.dockLocation};return{ok:!0,frameID:String(n.frameID),dockLocation:n.docking&&n.docking.dockLocation,xfTransform:{translation:{x:+o.translation.x,y:+o.translation.y,z:+o.translation.z},rotation:{w:+o.rotation.w,x:+o.rotation.x,y:+o.rotation.y,z:+o.rotation.z},scale:o.scale!=null&&"object"==typeof o.scale?{x:+o.scale.x,y:+o.scale.y,z:+o.scale.z}:o.scale}}}),this.m_dashboardThumbnailsChangedEventHandle='

MOUNT_OLD='componentDidMount(){const e=this.props.frame;this.m_NudgeReactionHandle='
MOUNT_NEW='componentDidMount(){const e=this.props.frame;var _A=window.__ASTERISM_STEAMVR=window.__ASTERISM_STEAMVR||{};_A._uo=_A._uo||{},e&&null!=e.frameID&&(_A._uo[e.frameID]=this),this.m_NudgeReactionHandle='

UNMOUNT_OLD='componentWillUnmount(){var e,t,r,n;null===(e=this.m_NudgeReactionHandle)||void 0===e||e.call(this),null===(t=this.m_DockLocationReactionHandle)'
UNMOUNT_NEW='componentWillUnmount(){var e,t,r,n;try{var _f=this.props&&this.props.frame,_A=window.__ASTERISM_STEAMVR;_A&&_A._uo&&_f&&null!=_f.frameID&&_A._uo[_f.frameID]===this&&delete _A._uo[_f.frameID]}catch(_e){}null===(e=this.m_NudgeReactionHandle)||void 0===e||e.call(this),null===(t=this.m_DockLocationReactionHandle)'

rm -rf "$STAGE"
mkdir -p "$STAGE"

python3 - "$CHUNK" "$STAGE" "$BRIDGE_V1" "$BRIDGE_V2" "$MOUNT_OLD" "$MOUNT_NEW" "$UNMOUNT_OLD" "$UNMOUNT_NEW" <<'PY'
import hashlib, sys
from pathlib import Path

src, stage, b1, b2, m_old, m_new, u_old, u_new = sys.argv[1:9]
data = Path(src).read_bytes().decode("utf-8", "surrogateescape")
checks = [
    ("bridge_v1", b1, 1),
    ("mount", m_old, 1),
    ("unmount", u_old, 1),
]
for name, needle, want in checks:
    c = data.count(needle)
    print(f"count {name}={c} (want {want})")
    if c != want:
        raise SystemExit(f"STOP: {name} needle count={c}")

new = data.replace(b1, b2, 1)
new = new.replace(m_old, m_new, 1)
new = new.replace(u_old, u_new, 1)
if new.count("applyWorldTransformForSummonKey") < 1:
    raise SystemExit("STOP: applyWorldTransform missing after patch")
if "version:2" not in new:
    raise SystemExit("STOP: version:2 missing")

out = Path(stage) / "chunk~8012d0c89.js"
out.write_text(new, encoding="utf-8", errors="surrogateescape")
h = hashlib.sha256(out.read_bytes()).hexdigest()
(Path(stage) / "HASHES.txt").write_text(
    f"base_v1_sha={hashlib.sha256(Path(src).read_bytes()).hexdigest()}\n"
    f"staged_v2_sha={h}\n"
    f"bridge_api=version:2,_uo,getFramesForSummonKey,applyWorldTransformForSummonKey,getLiveWorldTransformForSummonKey\n",
    encoding="utf-8",
)
print("staged", out)
print("staged_v2_sha", h)
PY

cat > "$STAGE/NEEDLES.txt" <<EOF
EXPECTED_BUILD=$EXPECTED_BUILD
BASE_V1_SHA=$EXPECTED_V1_SHA
BRIDGE_V1 (count=1):
$BRIDGE_V1

MOUNT_OLD (count=1):
$MOUNT_OLD

UNMOUNT_OLD (count=1):
$UNMOUNT_OLD
EOF

cat > "$STAGE/APPLY.sh" <<'EOF'
#!/usr/bin/env bash
# MANUAL apply only — DO NOT USE: v2 caused a giant black rectangle on load.
# Prefer shell-only React fiber direct-restore on chunk v1.
# Kept for forensic re-staging / hash reproduction only.
set -euo pipefail
STAGE=$(cd "$(dirname "$0")" && pwd)
DASH=/opt/steamvr/resources/webinterface/dashboard
CHUNK=$DASH/chunk~8012d0c89.js
EXPECTED_V1=272c1e40f75bafe28a7108485295681ffdac2a322a6a10f3e2d35278d596dfd9
STAGED=$STAGE/chunk~8012d0c89.js
READONLY_WAS_DISABLED=0

sha() { sha256sum "$1" | awk '{print $1}'; }

cleanup() {
  if [ "$READONLY_WAS_DISABLED" = 1 ] && command -v steamos-readonly >/dev/null 2>&1; then
    echo "Re-enabling steamos-readonly..."
    sudo steamos-readonly enable
  fi
}
# Trap BEFORE any readonly disable
trap cleanup EXIT

echo "STOP: bridge v2 is known-broken (black rectangle on SteamVR load)." >&2
echo "Refusing APPLY. Use shell-only fiber path or staged v2.1 only after review." >&2
exit 3

echo "Preflight: live chunk must still be v1 bridged ($EXPECTED_V1)"
live=$(sha "$CHUNK")
test "$live" = "$EXPECTED_V1"

if command -v steamos-readonly >/dev/null 2>&1; then
  echo "Disabling steamos-readonly (interactive sudo)..."
  sudo steamos-readonly disable
  READONLY_WAS_DISABLED=1
  sudo touch "$DASH/.asterism-write-test"
  sudo rm -f "$DASH/.asterism-write-test"
fi

BK=$HOME/.local/share/asterism/backups/bridge-v2-$(date +%Y%m%dT%H%M%S)
mkdir -p "$BK"
cp -a "$CHUNK" "$BK/chunk~8012d0c89.js"
echo "backup $BK"

sudo install -m 0644 "$STAGED" "$CHUNK"
echo "installed sha=$(sha "$CHUNK")"
grep -F 'applyWorldTransformForSummonKey' "$CHUNK" >/dev/null
grep -F 'version:2' "$CHUNK" >/dev/null
echo "OK. Clear htmlcache and restart SteamVR."
EOF
chmod +x "$STAGE/APPLY.sh"

# Copy needle doc into repo-friendly stage note
cp -a "$STAGE/HASHES.txt" "$ROOT/patches/dashmgr-bridge-v2-HASHES.txt" 2>/dev/null || true
mkdir -p "$ROOT/patches/dashmgr-bridge-v2"
cp -a "$STAGE/NEEDLES.txt" "$ROOT/patches/dashmgr-bridge-v2/NEEDLES.txt"
cp -a "$STAGE/APPLY.sh" "$ROOT/patches/dashmgr-bridge-v2/APPLY.sh.example"
cp -a "$STAGE/HASHES.txt" "$ROOT/patches/dashmgr-bridge-v2/HASHES.txt" 2>/dev/null || \
  echo "HASHES produced only on Frame (no local chunk)" > "$ROOT/patches/dashmgr-bridge-v2/HASHES.txt"

echo
echo "Staged at $STAGE"
cat "$STAGE/HASHES.txt"
echo
echo "DO NOT auto-deploy. Review APPLY.sh then run manually with sudo."
