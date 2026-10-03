#!/usr/bin/env bash
# Post-deploy checks for taskbar-order PoC (read-only + dashmgr).
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
# shellcheck disable=SC1091
. "$ROOT/scripts/_env.sh"

CHUNK=$STEAMVR_WEBUI/chunk~8012d0c89.js
INPUT_SHA=272c1e40f75bafe28a7108485295681ffdac2a322a6a10f3e2d35278d596dfd9
OUTPUT_SHA=047c1d4ef8110849da024ed34948370dc92f572bc06e4c1de3f5b81fc4bccb8e
BRIDGE_V1='window.__ASTERISM_STEAMVR||(window.__ASTERISM_STEAMVR={version:1,yWq:i.yWq,getFramesForSummonKey:function(e){return M.JJ.GetFramesWithAssociatedSummonKeys(e)||[]}})'

sha() { sha256sum "$1" | awk '{print $1}'; }

echo "== offline model =="
python3 test/test_taskbar_order_model.py

echo "== chunk =="
live=$(sha "$CHUNK")
echo "sha: $live"
if [ "$live" != "$OUTPUT_SHA" ]; then
  echo "FAIL: expected OUTPUT_SHA $OUTPUT_SHA" >&2
  exit 1
fi
grep -Fq "$BRIDGE_V1" "$CHUNK"
grep -Fq 'version:1' "$CHUNK"
grep -Fq 'asterism.desktop.app.' "$CHUNK"
echo "bridge v1 + taskbar-order markers OK"

echo "== patch status =="
"$ROOT/scripts/patch-steamvr-taskbar-order.sh" --status

echo "== dashmgr probe =="
"$ROOT/scripts/asterism-dashmgr" probe | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok") is True, d
r=(d.get("result") or {})
assert r.get("ok") is True, r
p=(r.get("probe") or {})
assert p.get("hasDashboard"), p
assert p.get("hasAsterismBridge"), p
print("probe ok; bridge", p.get("bridgeVersion") or p.get("hasAsterismBridge"))
'

echo "== probe-taskbar (if shell deployed with cmd) =="
if "$ROOT/scripts/asterism-dashmgr" probe-taskbar >/tmp/asterism-probe-taskbar.json 2>/tmp/asterism-probe-taskbar.err; then
  python3 - <<'PY'
import json
d=json.load(open("/tmp/asterism-probe-taskbar.json", encoding="utf-8"))
assert d.get("ok") is True, d
tb=(d.get("result") or {}).get("taskbar") or {}
pub=tb.get("publishedOrder") or tb.get("childrenSortedAsPublished") or []
print("publishedOrder:")
for row in pub:
    if isinstance(row, dict) and "kind" in row:
        print(" ", row.get("kind"), row.get("overlay") or row.get("overlayKey"), row.get("title"))
    else:
        print(" ", row.get("kind"), row.get("overlayKey"), row.get("title"))
asts=[r for r in pub if (r.get("kind") in ("asterism-display","asterism_display"))]
print("asterism-display count", len(asts))
PY
else
  echo "NOTE: probe-taskbar unavailable (redeploy asterism_shell.js); chunk checks still OK"
  cat /tmp/asterism-probe-taskbar.err || true
fi

echo "== overlays (bar present) =="
"$VRCMD" --overlays 2>/dev/null | rg -i 'gamepadui\.bar|asterism\.desktop\.app' || true

echo "VERIFY_OK (visual click-test still required in headset)"
echo "Expected visual: Steam | Asterism displays | apps | + | system"
