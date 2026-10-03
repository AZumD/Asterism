# ASTERISM-DASHMGR

Script: `scripts/asterism-dashmgr`

## Purpose

CLI for the Dashboard Manager bridge.

Path:

```
asterism-dashmgr
  -> HTTP 127.0.0.1:47831 /dashmgr/request
  -> FIFO queue in asterism-dashboard
  -> WebSocket ws://localhost:47832
  -> asterism_shell.js in systemui
  -> result store
  -> CLI response
```

## Commands

```
asterism-dashmgr probe
asterism-dashmgr list
asterism-dashmgr map
asterism-dashmgr capture asterism.desktop.app.2
asterism-dashmgr seed-world asterism.desktop.app.2 transform.json
asterism-dashmgr set-presentation asterism.desktop.app.2 world
asterism-dashmgr direct-restore asterism.desktop.app.2 transform.json
asterism-dashmgr restore-via-hand asterism.desktop.app.2 transform.json
asterism-dashmgr get-live-world asterism.desktop.app.2
asterism-dashmgr find-live-uo asterism.desktop.app.2
asterism-dashmgr inspect-undocked-render asterism.desktop.app.2
asterism-dashmgr inspect-undocked-instance asterism.desktop.app.2
asterism-dashmgr inspect-just-floated asterism.desktop.app.2
asterism-dashmgr clear-just-floated asterism.desktop.app.2
asterism-dashmgr force-dashboard-render
asterism-dashmgr save-world display-1
asterism-dashmgr restore-display display-1 [--hand-fallback]
```

- `direct-restore` uses **weak** mounted fiber identity + `setState({xfTransform:P})` (may initialize from null). Requires World docking.
- `find-live-uo` **strict** fiber match (requires non-null `xfTransform`) — diagnostic only; not used for World readiness.
- `inspect-just-floated` read-only: `justFloatedFromDashboard` + `isActiveDashboardFrame` (auto-restore waits for flag false after hide).
- `clear-just-floated` diagnostic only — **not** used by automatic restore (true→false itself triggers Valve's MobX nudge).
- `inspect-undocked-render` invokes `Dashboard.renderUndockedLocalFrameTransforms` only when its source matches the known safe `frames_local_undocked.map(createElement({frame}))` shape; returns JSON-safe `{ok,count,frames[],targetFrameID,targetPresent}` plus per-element inert `typeKind` / `typeName` / `typeDisplayName` / `typeSourcePreview` / `propsKeys` / mention flags (never React elements; never invokes `element.type`). Distinguishes Case A (in `frames_local_undocked`, fiber missing) vs Case B (never in the undocked list).
- `inspect-undocked-instance` weak fiber walk (`setState` + matching `frameID` only) across `_reactInternals` and `.alternate`; reports mounted candidates even when `xfTransform` is still undefined. Read-only; does not change `find-live-uo` / direct-restore.
- `force-dashboard-render` calls `Dashboard.forceUpdate()` if present — diagnostic only; not wired into automatic persistence.
- `restore-via-hand` is the proven diagnostic oracle (LeftHand→World).
- `save-world` / `restore-display` use stable `display-N` + `spatial-state.json`.

Requires injected `asterism_shell.js` (WebSocket client) and the chunk bridge
(`window.__ASTERISM_STEAMVR`) for Frame lookup.
