# REACT_FIBER

Module: `spatial/react_fiber.py`  
Shell: `patches/asterism_shell.js` (`findLiveUndockedOverlayForFrame`)

## Purpose

Locate live `UndockedOverlay` class instances via
`window.Dashboard._reactInternals` without Valve chunk lifecycle patches.

Walk only `fiber.child` / `fiber.sibling`, capped (default 8000), with a
visited set. **Weak identity** (`findMountedUndockedOverlayForFrame` / `inspect-undocked-instance`
/ World readiness / `direct-restore`):

- `typeof setState === "function"`
- `props.frame.frameID` equals target
- `state.xfTransform` may be null/undefined

**Strict identity** (`find-live-uo` / `get-live-world` verify):

- weak identity **and** `state.xfTransform != null`

UndockedOverlay constructs with `state.xfTransform = undefined`;
`componentDidMount` later calls `setInitialTransformForLocation(undefined)`.
Automatic World restore therefore initializes via `setState({ xfTransform: P })`
on a weak-mounted instance when Asterism has a saved World transform P.

Never serialize React instances over the wire — diagnostics only.

## Diagnostics

| Command | Role |
| --- | --- |
| `inspect-undocked-render <key>` | Safe `renderUndockedLocalFrameTransforms` + inert type metadata |
| `inspect-undocked-instance <key>` | Weak fiber walk (primary+alternate); readiness signal |
| `find-live-uo <key>` | Strict diagnostic (mounted + non-null xf) |
| `direct-restore` | Weak mount + `map[World]=P` + `setState`; reports `initializedFromNull` |
| `inspect-just-floated` | Read-only float lifecycle flags (auto-restore waits after hide) |
| `clear-just-floated` | Diagnostic only — not used by automatic restore |
| `get-live-world` | Strict live pose verify (pre-hide intermediate + final post-hide) |

Live finding: a mounted UndockedOverlay may exist at cold startup with
`state.xfTransform` undefined. Null xfTransform is not evidence of unmounted.

Covered by `test/test_undocked_render_diag.py`, `test/test_fiber_direct_restore.py`,
`test/test_spatial_lifecycle.py`.
