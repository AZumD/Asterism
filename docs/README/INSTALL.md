# INSTALL

Script: `install.sh`

## Purpose

Preflight + compatibility gate + SteamVR UI backup + install user units for Phase B. Does **not** patch Valve UI files.

## Usage

```
./install.sh --dry-run --yes
./install.sh --yes
```

## Notes

- Aborts if SteamVR build id or UI hashes drift from `compatibility/manifest.json`.
- Safe to re-run; backup dirs are timestamped and never overwritten.
- Installs `asterism-desktop-settings` → GTK3 Desktop Settings (not FrameTop's distrobox UI).
- Widens floating overlay resize via user `steamvr.vrsettings` (`asterism-vrsettings.sh`).
