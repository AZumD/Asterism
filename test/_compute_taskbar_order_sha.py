#!/usr/bin/env python3
"""Compute SHA of chunk after Asterism-specific Dt reorder (offline)."""
from pathlib import Path
import hashlib
import sys

OLD = (
    "Dt=[e=>{var t;return 14==(null===(t=e.icon())||void 0===t?void 0:t.enum())},"
    "e=>{var t;return 33==(null===(t=e.icon())||void 0===t?void 0:t.enum())},"
    "e=>{var t;return null!=(null===(t=e.icon())||void 0===t?void 0:t.overlay())},"
    "e=>{var t;return 15==(null===(t=e.icon())||void 0===t?void 0:t.enum())},"
    "e=>{var t;return null!=(null===(t=e.icon())||void 0===t?void 0:t.hwnd())}];"
)
NEW = (
    "Dt=[e=>{var t;return 14==(null===(t=e.icon())||void 0===t?void 0:t.enum())},"
    'e=>{var t;return null!=(null===(t=e.icon())||void 0===t?void 0:t.overlay())&&0===String(t.overlay()).indexOf("asterism.desktop.app.")},'
    "e=>{var t;return 33==(null===(t=e.icon())||void 0===t?void 0:t.enum())},"
    'e=>{var t;return null!=(null===(t=e.icon())||void 0===t?void 0:t.overlay())&&0!==String(t.overlay()).indexOf("asterism.desktop.app.")},'
    "e=>{var t;return 15==(null===(t=e.icon())||void 0===t?void 0:t.enum())},"
    "e=>{var t;return null!=(null===(t=e.icon())||void 0===t?void 0:t.hwnd())}];"
)
BRIDGE = (
    "window.__ASTERISM_STEAMVR||(window.__ASTERISM_STEAMVR={version:1,yWq:i.yWq,"
    "getFramesForSummonKey:function(e){return M.JJ.GetFramesWithAssociatedSummonKeys(e)||[]}})"
)

path = Path(
    sys.argv[1]
    if len(sys.argv) > 1
    else "/opt/steamvr/resources/webinterface/dashboard/chunk~8012d0c89.js"
)
raw = path.read_bytes()
text = raw.decode("utf-8", "surrogateescape")
print("input sha", hashlib.sha256(raw).hexdigest())
print("old count", text.count(OLD))
if text.count(OLD) != 1:
    raise SystemExit("old needle count != 1")
out = text.replace(OLD, NEW, 1)
out_b = out.encode("utf-8", "surrogateescape")
print("output sha", hashlib.sha256(out_b).hexdigest())
print("len delta", len(out_b) - len(raw))
print("bridge still", BRIDGE in out)
print("version:1 still", "version:1" in out)
assert OLD not in out
assert NEW in out
assert BRIDGE in out
out_path = Path("/tmp/chunk-taskbar-order.js")
out_path.write_bytes(out_b)
print("wrote", out_path, out_path.stat().st_size)
