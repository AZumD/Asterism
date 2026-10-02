# ASTERISM-DASHBOARD

Module: `dashboard/asterism-dashboard.py`

## Purpose

Control plane + supervisor: start desktop with SteamVR, visibility IPC/HTTP, crash recovery rate limit, stop desktop when SteamVR dies. `restart-desktop` over the Unix socket (not HTTP).

## Visibility vs layout

`show` / `hide` / `toggle` / `focus_desktop_overlay` / steamvr-up are **visibility only**. They must not spawn `asterism-layout apply`. Layout restore is owned solely by `desktop/asterism-session.sh` when a new gamescope creates PerWindow overlays (eliminates theater→dashboard→world races).

## Dashboard Manager bridge (experimental)

Loopback HTTP on `127.0.0.1:47831`:

- `GET /dashmgr/poll` — shell picks up one queued command
- `POST /dashmgr/enqueue` — queue a command (returns id)
- `POST /dashmgr/request` — enqueue+wait (`probe`/`list`/`capture`/`seed-world`/`set-presentation`)
- `POST /dashmgr/result` — shell posts command result
- `GET /dashmgr/result/<id>` — fetch stored result
- `POST /dashmgr/probe` — shell uploads Phase 1 probe JSON

Queue state uses module globals `_DASHMGR_PENDING` / `_DASHMGR_RESULTS` (must be declared
`global` where assigned). Covered by `test/test_dashmgr_queue.py`.

See [ASTERISM-DASHMGR.md](ASTERISM-DASHMGR.md) and [../dashboard-state/MAP_RESTORE.md](../dashboard-state/MAP_RESTORE.md).
