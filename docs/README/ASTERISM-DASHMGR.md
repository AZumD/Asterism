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
asterism-dashmgr force-dashboard-render
asterism-dashmgr save-world display-1
asterism-dashmgr restore-display display-1 [--hand-fallback]
```

- `direct-restore` prefers shell React-fiber `setState` on chunk **v1**.
- `find-live-uo` reports whether a live UndockedOverlay instance was found (JSON-safe).
- `inspect-undocked-render` invokes `Dashboard.renderUndockedLocalFrameTransforms` only when its source matches the known safe `frames_local_undocked.map(createElement({frame}))` shape; returns JSON-safe `{ok,count,frames[],targetFrameID,targetPresent}` plus per-element inert `typeKind` / `typeName` / `typeDisplayName` / `typeSourcePreview` / `propsKeys` / mention flags (never React elements; never invokes `element.type`). Distinguishes Case A (in `frames_local_undocked`, fiber missing) vs Case B (never in the undocked list).
- `force-dashboard-render` calls `Dashboard.forceUpdate()` if present — diagnostic only; not wired into automatic persistence.
- `restore-via-hand` is the proven diagnostic oracle (LeftHand→World).
- `save-world` / `restore-display` use stable `display-N` + `spatial-state.json`.

Requires injected `asterism_shell.js` (WebSocket client) and the chunk bridge
(`window.__ASTERISM_STEAMVR`) for Frame lookup.
