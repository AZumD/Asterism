# ASTERISM-DASHMGR

Script: `scripts/asterism-dashmgr`

## Purpose

CLI for the experimental Dashboard Manager loopback bridge (shell ↔ asterism-dashboard).

## Commands

```
asterism-dashmgr probe
asterism-dashmgr list
asterism-dashmgr capture asterism.desktop.app.2
asterism-dashmgr seed-world asterism.desktop.app.2 transform.json
asterism-dashmgr set-presentation asterism.desktop.app.2 world
```

Requires injected `asterism_shell.js` (+ optional chunk bridge) and SteamVR systemui loaded.
See [../dashboard-state/MAP_RESTORE.md](../dashboard-state/MAP_RESTORE.md).
