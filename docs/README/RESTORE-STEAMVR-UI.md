# RESTORE-STEAMVR-UI

Script: `scripts/restore-steamvr-ui.sh`

## Purpose

Restore Valve SteamVR UI files from an Asterism backup. Default: most recent backup.

## Usage

```
scripts/restore-steamvr-ui.sh --dry-run
scripts/restore-steamvr-ui.sh --yes
scripts/restore-steamvr-ui.sh --yes 20261002T153000
```

## Notes

- Validates backup SHA256 before writing.
- Prints the file list before restore.
- May use `sudo` when `/opt/steamvr` is not writable.
- Does not require the SteamVR UI to be functioning.
