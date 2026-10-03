# _VERIFY_UNDOCKED_RENDER_DIAG

Script: `test/test_undocked_render_diag.py`

## Purpose

No-SteamVR regression for Case A/B World diagnostics:

- shell markers for `inspect-undocked-render` / `force-dashboard-render`
- known-safe `renderUndockedLocalFrameTransforms` source gate
- per-element inert `elementTypeDiag` (`typeKind` / `typeSourcePreview` ≤3000 / mention flags)
- must not invoke `element.type` or mount
- `asterism-dashmgr` CLI wiring
- dashmgr enqueue: Asterism overlay key required for inspect; force needs none

## Run

```bash
python3 test/test_undocked_render_diag.py
```
