# ASTERISM-DASHBOARD

Module: `dashboard/asterism-dashboard.py`

## Purpose

Control plane + supervisor: start desktop with SteamVR, visibility IPC/HTTP, crash recovery rate limit, stop desktop when SteamVR dies. `restart-desktop` over the Unix socket (not HTTP).

## Visibility vs layout

`show` / `hide` / `toggle` / `focus_desktop_overlay` / steamvr-up are **visibility only**. They must not spawn `asterism-layout apply`. Layout restore is owned solely by `desktop/asterism-session.sh` when a new gamescope creates PerWindow overlays (eliminates theater→dashboard→world races).

## Dashboard Manager bridge (experimental)

Loopback:

- HTTP `127.0.0.1:47831` — CLI/debug (`/dashmgr/enqueue`, `/dashmgr/request`, `/status`)
- WebSocket `ws://localhost:47832` (bound `127.0.0.1`) — systemui shell (CSP allows `ws://localhost:*`)

Internal FIFO queue (`collections.deque`). CLI enqueues over HTTP; systemui consumes over WebSocket.

Queue helpers declare module state correctly; covered by `test/test_dashmgr_queue.py`.

Supported diagnostic cmds include `inspect-undocked-render`,
`inspect-undocked-instance`, `clear-just-floated`, and `force-dashboard-render`
(Case A/B World missing-UO triage + exact World nudge suppress; not generic float).

See [ASTERISM-DASHMGR.md](ASTERISM-DASHMGR.md), [ASTERISM_WS.md](ASTERISM_WS.md), [../dashboard-state/MAP_RESTORE.md](../dashboard-state/MAP_RESTORE.md).
