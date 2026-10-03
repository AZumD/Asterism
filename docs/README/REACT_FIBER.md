# REACT_FIBER

Module: `spatial/react_fiber.py`  
Shell: `patches/asterism_shell.js` (`findLiveUndockedOverlayForFrame`)

## Purpose

Locate live `UndockedOverlay` class instances via
`window.Dashboard._reactInternals` without Valve chunk lifecycle patches.

Walk only `fiber.child` / `fiber.sibling`, capped (default 8000), with a
visited set. Strong match (`find-live-uo` / direct-restore) requires:

- `typeof setState === "function"`
- `props.frame.frameID` equals target
- `state.xfTransform` present (non-null)

Weak match (`inspect-undocked-instance`) drops the xfTransform requirement.
UndockedOverlay constructs with `state.xfTransform = undefined` and only fills
it later via `setInitialTransformForLocation`, so strong match alone cannot
distinguish “not mounted” from “mounted, xf still null”.

Never serialize React instances over the wire — diagnostics only.

## Case A / Case B diagnostics

When `dockLocationName == World` but fiber has no matching `UndockedOverlay`:

| Command | Role |
| --- | --- |
| `inspect-undocked-render <key>` | Call `renderUndockedLocalFrameTransforms` only if source is known-safe; report `targetPresent` plus per-element inert `type*` / `propsKeys` / source-mention flags (never invoke `element.type`) |
| `inspect-undocked-instance <key>` | Weak fiber walk on `_reactInternals` + `.alternate` (deduped stateNodes); reports mounted candidates even when `xfTransform` is null |
| `force-dashboard-render` | `Dashboard.forceUpdate()` once (diagnostic; not auto-persistence) |
| `find-live-uo <key>` | Strong fiber walk — requires non-null `xfTransform` (unchanged) |

Interpretation: `targetPresent=true` + weak `candidateCount=0` → not mounted.  
`candidateCount>0` + `xfTransformNullish=true` → mounted but transform uninitialized.  
`targetPresent=false` → Case B (Frame Manager bookkeeping).

Covered by `test/test_undocked_render_diag.py`, `test/test_fiber_direct_restore.py`.
