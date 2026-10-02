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
asterism-dashmgr capture asterism.desktop.app.2
asterism-dashmgr seed-world asterism.desktop.app.2 transform.json
asterism-dashmgr set-presentation asterism.desktop.app.2 world
```

Requires injected `asterism_shell.js` (WebSocket client) and the chunk bridge
(`window.__ASTERISM_STEAMVR`) for Frame lookup.
