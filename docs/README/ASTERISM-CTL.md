# ASTERISM-CTL

Script: `scripts/asterism-ctl.sh`

## Purpose

IPC client: `show` / `hide` / `toggle` / `status` / `ping` (visibility).  
`restart-desktop` stops and starts the nested session (applies topology).  
`stop-desktop` is **admin/recovery only**.

Forces the real user D-Bus (`/run/user/$UID/bus`) so it works from nested Plasma SSH/settings.
