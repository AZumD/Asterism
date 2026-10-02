# ASTERISM-DASHBOARD

Module: `dashboard/asterism-dashboard.py`

## Purpose

Control plane + supervisor: start desktop with SteamVR, visibility IPC/HTTP, crash recovery rate limit, stop desktop when SteamVR dies. `restart-desktop` over the Unix socket (not HTTP). After SteamVR comes back it ensures the desktop and **restores `layout.json` dock modes** (world/theater/dashboard) — it must not force-dock to the dashboard.
