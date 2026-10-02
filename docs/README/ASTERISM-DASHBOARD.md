# ASTERISM-DASHBOARD

Module: `dashboard/asterism-dashboard.py`

## Purpose

Control plane + supervisor: start desktop with SteamVR, visibility IPC/HTTP, crash recovery rate limit, stop desktop when SteamVR dies. `restart-desktop` over the Unix socket (not HTTP).

## Visibility vs layout

`show` / `hide` / `toggle` / `focus_desktop_overlay` / steamvr-up are **visibility only**. They must not spawn `asterism-layout apply`. Layout restore is owned solely by `desktop/asterism-session.sh` when a new gamescope creates PerWindow overlays (eliminates theater→dashboard→world races).
