# ASTERISM-LAYOUT

Script: `scripts/asterism-layout`

## Purpose

CLI for `layout/layout.py` — restore dock/theater/world after desktop/SteamVR start.

`apply` restores dock modes only. Laser place is separate (`place` / `apply --place`) because the virtual controller otherwise hijacks the laser on restart.

See [LAYOUT.md](LAYOUT.md).
