# RESTORE

Module: `spatial/restore.py`

## Purpose

Orchestrate capture/restore of presentation + World poses for stable display IDs.

- Wait for WebSocket shell bridge before restore
- Snapshot: capture + live World xf when World
- Restore: seed map → set-presentation → (World) wait UO → direct-restore
- No hand fallback during normal startup

## CLI

Prefer `scripts/asterism-spatial` (service-facing).  
See [ASTERISM-SPATIAL.md](ASTERISM-SPATIAL.md).
