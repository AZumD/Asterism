# BACKUP-STEAMVR-UI

Script: `scripts/backup-steamvr-ui.sh`

## Purpose

Copy every SteamVR UI file Asterism may later patch into a timestamped backup under `~/.local/share/asterism/backups/`, with a TSV manifest (path, backup path, SHA256, mode, mtime).

## Usage

```
scripts/backup-steamvr-ui.sh
scripts/backup-steamvr-ui.sh --dry-run
```

## Notes

- Never overwrites an existing backup directory.
- Preserves permissions/timestamps via `cp -a`.
- Refuses to proceed if a listed target is missing.
