# REACT_FIBER

Module: `spatial/react_fiber.py`  
Shell: `patches/asterism_shell.js` (`findLiveUndockedOverlayForFrame`)

## Purpose

Locate live `UndockedOverlay` class instances via
`window.Dashboard._reactInternals` without Valve chunk lifecycle patches.

Walk only `fiber.child` / `fiber.sibling`, capped (default 8000), with a
visited set. Match structural signature:

- `typeof setState === "function"`
- `props.frame.frameID` equals target
- `state.xfTransform` present

Never serialize React instances over the wire — diagnostics only.

## Case A / Case B diagnostics

When `dockLocationName == World` but fiber has no matching `UndockedOverlay`:

| Command | Role |
| --- | --- |
| `inspect-undocked-render <key>` | Call `renderUndockedLocalFrameTransforms` only if source is known-safe; report `targetPresent` plus per-element inert `type*` / `propsKeys` / source-mention flags (never invoke `element.type`) |
| `force-dashboard-render` | `Dashboard.forceUpdate()` once (diagnostic; not auto-persistence) |
| `find-live-uo <key>` | Fiber walk — was a live UO mounted? |

Interpretation: `targetPresent=true` + fiber absent → Case A (React invalidation). `targetPresent=false` → Case B (Frame Manager bookkeeping; do not chase re-render hacks).

Covered by `test/test_undocked_render_diag.py`.
