# Asterism

Experimental SteamVR-native Linux desktop environment for the Valve Steam Frame.

**SteamVR remains the primary shell.** Asterism adds Linux desktop functionality *into* that shell (dashboard overlay), rather than layering a spatial desktop beside it.

## Status

Milestone 0 (safety/recovery) + Phase B (dashboard overlay PoC) — **no Valve UI file patches**.

## Install (on the Steam Frame)

```bash
# From a PC with SSH host "frame", or clone on-device:
cd ~/asterism
./install.sh
```

## Control

```bash
asterism-ctl show      # start nested desktop + show SteamVR dashboard
asterism-ctl hide      # hide SteamVR dashboard (session may keep running)
asterism-ctl toggle
asterism-ctl status
asterism-ctl stop-desktop
```

## Recovery (SSH)

```bash
~/asterism/scripts/recover-asterism.sh --yes --no-restart
~/asterism/scripts/asterism-status.sh
```

## Docs

- [DEVELOPMENT.md](DEVELOPMENT.md)
- [docs/README/OVERVIEW.md](docs/README/OVERVIEW.md)
