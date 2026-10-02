# RESTORE

Module: `spatial/restore.py`

## Purpose

Orchestrate capture/restore of presentation + World poses for stable display IDs.

- Wait for WebSocket shell bridge before restore
- Snapshot: capture + live World xf when World
- World restore uses **WORLD MATERIALIZATION**
  (Dashboard → `/show` → World → wait live UO → `direct-restore` → `/hide`)
- Dashboard/Theater: direct `set-presentation` only
- No hand fallback during normal startup

## CLI

Prefer `scripts/asterism-spatial` (service-facing).  
See [ASTERISM-SPATIAL.md](ASTERISM-SPATIAL.md).
