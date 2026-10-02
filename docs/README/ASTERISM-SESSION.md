# ASTERISM-SESSION

Module: `desktop/asterism-session.sh` / `desktop/asterism-session-inner.sh` (+ `systemd/asterism-desktop.service`)

## Purpose

One gamescope OpenVR dashboard overlay (`asterism.desktop` / name `Desktop`) hosting nested Plasma.

## Notes

- Requires live `vrserver` + `vrcompositor` (waits briefly — WantedBy can race ahead of SteamVR).
- Resolution capped for gamescope OpenVR buffer.
- Plasma config isolated under `~/.config/asterism/plasma`.
- Nested runtime: `/run/user/$UID/asterism_nested` (captures `plasmashell.env` for SSH launchers — FrameTop pattern).
- After Plasma starts: `asterism-apply-outputs.sh` places KWin outputs edge-to-edge.
- **Sole layout-apply owner:** one background `asterism-layout apply --wait 90` when this session starts gamescope. Dashboard must not also apply.
- Optional experimental Gamescope via `ASTERISM_GAMESCOPE_BIN` + `ASTERISM_OPENVR_CTRL` in `asterism.conf` (stock PATH gamescope remains default; missing experimental binary aborts start).
- Never exits 0 on a leftover gamescope match (that would deactivate Type=simple); stale processes are SIGTERM'd first.
- Clean stop via systemd SIGTERM (`KillMode=mixed`).
