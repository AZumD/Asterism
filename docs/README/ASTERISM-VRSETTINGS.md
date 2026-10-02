# ASTERISM-VRSETTINGS

Script: `scripts/asterism-vrsettings.sh`

## Purpose

Widen SteamVR’s floating overlay drag-resize range in the **user** `steamvr.vrsettings` (not `/opt/steamvr`).

Stock defaults:

```
dashboard.scaleSliderMin = 0.75
dashboard.scaleSliderMax = 1.5
```

Asterism install sets roughly `0.40` … `4.0` so world-window grab-resize can grow much larger (same idea as FrameTop’s multi-metre panel widths on ft-screens).

Also raise gamescope starting size via `PHYS_WIDTH` in `asterism.conf` (default **2.5** m).

## Usage

```
scripts/asterism-vrsettings.sh status
scripts/asterism-vrsettings.sh --yes install
scripts/asterism-vrsettings.sh --yes uninstall
```

Restart SteamVR (or at least re-undock the panel) after changing slider limits.
