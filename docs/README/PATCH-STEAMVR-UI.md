# PATCH-STEAMVR-UI

Script: `scripts/patch-steamvr-ui.sh`

## Purpose

Version-locked Phase C inject: install `asterism_shell.js` and reference it from `systemui.html`.

## Usage

```
scripts/patch-steamvr-ui.sh --dry-run --yes
scripts/patch-steamvr-ui.sh --yes
scripts/patch-steamvr-ui.sh --status
scripts/patch-steamvr-ui.sh --unpatch --yes
```

## Notes

- Aborts if SteamVR build or stock `ui_targets` hashes drift.
- Creates a fresh backup before first apply.
- Does not restart SteamVR; clear htmlcache and restart manually.
