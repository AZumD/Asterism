# ASTERISM-LAYOUT

Script: `scripts/asterism-layout`

## Purpose

CLI for `layout/layout.py` — restore dock/theater/world after desktop/SteamVR start.

`apply` restores dock modes only. Laser place is separate (`place` / `apply --place`) because the virtual controller otherwise hijacks the laser on restart.

**Startup ownership:** only `desktop/asterism-session.sh` runs `apply` when a new desktop overlay set is created. Dashboard `show`/`focus` never apply. Concurrent applies are rejected via flock + generation.

## Commands

```
asterism-layout show|sync|init|keys|get-dock INDEX
asterism-layout set-dock INDEX world|theater|dashboard
asterism-layout apply [--wait SECONDS] [--place]
asterism-layout place|release-pointer
asterism-layout live            # read-only OpenVR transform inspect (JSON)
asterism-layout inspect-live    # alias for live
```

See [LAYOUT.md](LAYOUT.md) and [../../OWNERSHIP_BOUNDARY.md](../OWNERSHIP_BOUNDARY.md).
