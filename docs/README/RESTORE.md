# RESTORE

Module: `spatial/restore.py`

## Purpose

Orchestrate capture/restore of World poses for stable display IDs.

- Wait for WebSocket shell bridge before restore
- Prefer `direct-restore` (bridge v2); optional `--hand-fallback`
- Missing Frame / corrupt pose skips that display only

## CLI

```
asterism-dashmgr save-world display-1
asterism-dashmgr restore-display display-1
asterism-dashmgr restore-display display-1 --hand-fallback
asterism-dashmgr direct-restore asterism.desktop.app.2 /tmp/world-P.json
asterism-dashmgr restore-via-hand asterism.desktop.app.2 /tmp/world-P.json
```

`restore-via-hand` is diagnostic only (proven LeftHand→World oracle).
