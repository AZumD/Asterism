#!/usr/bin/env bash
# Stage (do NOT apply) dashmgr bridge v2.1 — CONTINGENCY ONLY.
#
# Prefer shell-only React fiber direct-restore on chunk v1.
# Use this ONLY if live fiber lookup fails on Frame.
#
# Differences from broken v2 (SHA 83a3bcbf...):
# - NO unconditional UndockedOverlay lifecycle registration for all frames
# - Register/unregister ONLY when frame summon keys start with asterism.desktop
# - Unregister only if registry[frameID] === this
# - Bridge API still purpose-built (no eval)
#
# Base: v1 bridged chunk
#   SHA256 272c1e40f75bafe28a7108485295681ffdac2a322a6a10f3e2d35278d596dfd9
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
DASH=${STEAMVR_WEBUI:-/opt/steamvr/resources/webinterface/dashboard}
CHUNK=$DASH/chunk~8012d0c89.js
EXPECTED_V1_SHA=272c1e40f75bafe28a7108485295681ffdac2a322a6a10f3e2d35278d596dfd9
STAGE=${ASTERISM_BRIDGE_V21_STAGE:-/tmp/asterism-dashmgr-bridge-v2.1}

sha() { sha256sum "$1" | awk '{print $1}'; }

if [ ! -f "$CHUNK" ]; then
  echo "STOP: missing $CHUNK" >&2
  exit 2
fi
live_sha=$(sha "$CHUNK")
if [ "$live_sha" != "$EXPECTED_V1_SHA" ]; then
  echo "STOP: need live v1 chunk $EXPECTED_V1_SHA (got $live_sha)" >&2
  exit 2
fi

BRIDGE_V1='window.__ASTERISM_STEAMVR||(window.__ASTERISM_STEAMVR={version:1,yWq:i.yWq,getFramesForSummonKey:function(e){return M.JJ.GetFramesWithAssociatedSummonKeys(e)||[]}}),this.m_dashboardThumbnailsChangedEventHandle='

# v2.1 API: same apply helpers; version 2.1 marker string
BRIDGE_V21='window.__ASTERISM_STEAMVR=Object.assign(window.__ASTERISM_STEAMVR||{},{version:"2.1",yWq:i.yWq,_uo:(window.__ASTERISM_STEAMVR&&window.__ASTERISM_STEAMVR._uo)||{},getFramesForSummonKey:function(e){return M.JJ.GetFramesWithAssociatedSummonKeys(e)||[]},applyWorldTransformForSummonKey:function(e,t){var r=M.JJ.GetFramesWithAssociatedSummonKeys(e)||[],n=r[0];if(!n||!n.docking)return{ok:!1,error:"no frame"};if(String(e).indexOf("asterism.desktop")!==0)return{ok:!1,error:"non-asterism"};var a={translation:{x:+(t.translation&&t.translation.x),y:+(t.translation&&t.translation.y),z:+(t.translation&&t.translation.z)},rotation:{w:+(t.rotation&&t.rotation.w),x:+(t.rotation&&t.rotation.x),y:+(t.rotation&&t.rotation.y),z:+(t.rotation&&t.rotation.z)}};t.scale!=null&&(a.scale="object"==typeof t.scale?{x:+t.scale.x,y:+t.scale.y,z:+t.scale.z}:+t.scale),n.docking.m_mapLastRelativeTransformForDockLocation.set(i.yWq.World,a);var s=(window.__ASTERISM_STEAMVR._uo||{})[n.frameID];return s&&"function"==typeof s.setState?(s.setState({xfTransform:a}),{ok:!0,path:"setState+map",frameID:String(n.frameID),live:!0}):{ok:!0,path:"map-only",frameID:String(n.frameID),live:!1}},getLiveWorldTransformForSummonKey:function(e){var r=M.JJ.GetFramesWithAssociatedSummonKeys(e)||[],n=r[0];if(!n)return{ok:!1,error:"no frame"};if(String(e).indexOf("asterism.desktop")!==0)return{ok:!1,error:"non-asterism"};var s=(window.__ASTERISM_STEAMVR._uo||{})[n.frameID],o=s&&s.state&&s.state.xfTransform;if(!o)return{ok:!1,error:"no live xfTransform",frameID:n.frameID!=null?String(n.frameID):null,dockLocation:n.docking&&n.docking.dockLocation};return{ok:!0,frameID:String(n.frameID),dockLocation:n.docking&&n.docking.dockLocation,xfTransform:{translation:{x:+o.translation.x,y:+o.translation.y,z:+o.translation.z},rotation:{w:+o.rotation.w,x:+o.rotation.x,y:+o.rotation.y,z:+o.rotation.z},scale:o.scale!=null&&"object"==typeof o.scale?{x:+o.scale.x,y:+o.scale.y,z:+o.scale.z}:o.scale}}}),this.m_dashboardThumbnailsChangedEventHandle='

MOUNT_OLD='componentDidMount(){const e=this.props.frame;this.m_NudgeReactionHandle='
# Asterism-only registration
MOUNT_NEW='componentDidMount(){const e=this.props.frame;try{var _ks=(e&&e.associatedSummonOverlayKeys)||[],_sk=e&&e.activePage&&e.activePage.summonOverlayKey,_ok=(_sk&&String(_sk).indexOf("asterism.desktop")===0)||_ks.some(function(k){return String(k).indexOf("asterism.desktop")===0});if(_ok&&e&&null!=e.frameID){var _A=window.__ASTERISM_STEAMVR=window.__ASTERISM_STEAMVR||{};_A._uo=_A._uo||{},_A._uo[e.frameID]=this}}catch(_e){}this.m_NudgeReactionHandle='

UNMOUNT_OLD='componentWillUnmount(){var e,t,r,n;null===(e=this.m_NudgeReactionHandle)||void 0===e||e.call(this),null===(t=this.m_DockLocationReactionHandle)'
UNMOUNT_NEW='componentWillUnmount(){var e,t,r,n;try{var _f=this.props&&this.props.frame,_A=window.__ASTERISM_STEAMVR;_A&&_A._uo&&_f&&null!=_f.frameID&&_A._uo[_f.frameID]===this&&delete _A._uo[_f.frameID]}catch(_e){}null===(e=this.m_NudgeReactionHandle)||void 0===e||e.call(this),null===(t=this.m_DockLocationReactionHandle)'

rm -rf "$STAGE"
mkdir -p "$STAGE"

python3 - "$CHUNK" "$STAGE" "$BRIDGE_V1" "$BRIDGE_V21" "$MOUNT_OLD" "$MOUNT_NEW" "$UNMOUNT_OLD" "$UNMOUNT_NEW" <<'PY'
import hashlib, sys
from pathlib import Path
src, stage, b1, b2, m_old, m_new, u_old, u_new = sys.argv[1:9]
data = Path(src).read_bytes().decode("utf-8", "surrogateescape")
for name, needle, want in [("bridge_v1", b1, 1), ("mount", m_old, 1), ("unmount", u_old, 1)]:
    c = data.count(needle)
    print(f"count {name}={c}")
    if c != want:
        raise SystemExit(f"STOP: {name} count={c}")
new = data.replace(b1, b2, 1).replace(m_old, m_new, 1).replace(u_old, u_new, 1)
# Ensure only intended markers
assert new.count(m_old) == 0
assert new.count("asterism.desktop") >= 2
assert 'version:"2.1"' in new or "version:\"2.1\"" in new
out = Path(stage) / "chunk~8012d0c89.js"
out.write_text(new, encoding="utf-8", errors="surrogateescape")
h = hashlib.sha256(out.read_bytes()).hexdigest()
base = hashlib.sha256(Path(src).read_bytes()).hexdigest()
(Path(stage) / "HASHES.txt").write_text(
    f"base_v1_sha={base}\nstaged_v2_1_sha={h}\n",
    encoding="utf-8",
)
print("staged_v2_1_sha", h)
PY

mkdir -p "$ROOT/patches/dashmgr-bridge-v2.1"
cp -a "$STAGE/HASHES.txt" "$ROOT/patches/dashmgr-bridge-v2.1/HASHES.txt"
cat > "$ROOT/patches/dashmgr-bridge-v2.1/NEEDLES.txt" <<EOF
CONTINGENCY ONLY — prefer shell React fiber on v1.
BASE_V1_SHA=$EXPECTED_V1_SHA
Broken v2 SHA (do not use): 83a3bcbf43f179b290614af038835395226b0d8b54aaf188ce1a44c540a8aa2a
MOUNT gates on asterism.desktop summon keys before _uo registration.
EOF

cat > "$STAGE/APPLY.sh" <<'EOF'
#!/usr/bin/env bash
# CONTINGENCY manual apply — only if shell fiber path fails live.
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
    sudo steamos-readonly enable
  fi
}
trap cleanup EXIT
echo "Preflight v1..."
test "$(sha "$CHUNK")" = "$EXPECTED_V1"
if command -v steamos-readonly >/dev/null 2>&1; then
  sudo steamos-readonly disable
  READONLY_WAS_DISABLED=1
  sudo touch "$DASH/.asterism-write-test"
  sudo rm -f "$DASH/.asterism-write-test"
fi
BK=$HOME/.local/share/asterism/backups/bridge-v2.1-$(date +%Y%m%dT%H%M%S)
mkdir -p "$BK"
cp -a "$CHUNK" "$BK/"
sudo install -m 0644 "$STAGED" "$CHUNK"
echo "installed $(sha "$CHUNK")"
echo "Clear htmlcache + restart SteamVR manually."
EOF
chmod +x "$STAGE/APPLY.sh"
cp -a "$STAGE/APPLY.sh" "$ROOT/patches/dashmgr-bridge-v2.1/APPLY.sh.example"

echo "Staged v2.1 at $STAGE (DO NOT auto-apply). Prefer shell fiber on v1."
cat "$STAGE/HASHES.txt"
