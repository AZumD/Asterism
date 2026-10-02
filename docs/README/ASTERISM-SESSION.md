# ASTERISM-SESSION

Module: `desktop/asterism-session.sh` / `desktop/asterism-session-inner.sh` (+ `systemd/asterism-desktop.service`)

## Purpose

One gamescope OpenVR dashboard overlay (`asterism.desktop` / name `Desktop`) hosting nested Plasma.

## Notes

- Requires live `vrserver` + `vrcompositor`.
- Resolution capped for gamescope OpenVR buffer.
- Plasma config isolated under `~/.config/asterism/plasma`.
- Clean stop via systemd SIGTERM (`KillMode=mixed`).
