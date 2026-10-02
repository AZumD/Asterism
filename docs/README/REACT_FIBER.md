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
