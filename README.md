# Asterism

Experimental SteamVR-native Linux desktop for Valve Steam Frame.

SteamVR stays the primary shell. Asterism adds a persistent Linux desktop **into** that shell.

## Quick start (Frame)

```bash
cd ~/asterism
./install.sh --yes
# Phase C shell button (needs sudo once):
sudo ./scripts/patch-steamvr-ui.sh --yes
rm -rf ~/.cache/SteamVR/htmlcache
# Then restart SteamVR manually when ready.
```

## Control

```bash
asterism-ctl show|hide|toggle|status
asterism-ctl stop-desktop   # admin/recovery only
asterism-displayctl list
```

## Docs

[DEVELOPMENT.md](DEVELOPMENT.md) · [docs/README/OVERVIEW.md](docs/README/OVERVIEW.md)
