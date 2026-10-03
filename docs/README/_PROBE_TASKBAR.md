# _PROBE_TASKBAR

Script: `test/_probe_taskbar.sh`

## Purpose

**TEMPORARY** read-only helper for Steam Frame taskbar order.

Dumps how SystemUI publishes dashboard-bar tabs (consumed by Steam
`valve.steam.gamepadui.bar`), including Asterism display identity via
`icon.overlay` / `summonOverlayKey` (`asterism.desktop.app.N`).

Reports `publishedOrder` with kinds such as `steam`, `asterism-display`,
`appid`, `overlay` using the PoC publish-bucket model.

Does **not** reorder UI. Apply order via
[PATCH-STEAMVR-TASKBAR-ORDER.md](PATCH-STEAMVR-TASKBAR-ORDER.md).

## Usage (Frame)

```bash
bash test/_probe_taskbar.sh
# or:
./scripts/asterism-dashmgr probe-taskbar
```

Requires injected `asterism_shell.js` with `probe-taskbar` and a running
`asterism-dashboard` HTTP/WebSocket bridge.
