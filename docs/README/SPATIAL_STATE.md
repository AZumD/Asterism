# SPATIAL_STATE

Module: `spatial/spatial_state.py`

## Purpose

Asterism-owned presentation + per-dock transforms keyed by stable display IDs.

Path: `~/.local/state/asterism/spatial-state.json`  
Override: `ASTERISM_SPATIAL_PATH`

## Schema v2

```json
{
  "version": 2,
  "displays": {
    "display-1": {
      "presentation": "world",
      "transforms": {
        "world": { "translation": {}, "rotation": {}, "scale": {} },
        "dashboard": {},
        "theater": {}
      }
    }
  }
}
```

Only observed transforms are stored. Atomic write + optional directory fsync.

## Migration

Schema v1 `{ "worldTransform": ... }` loads as `transforms.world`.
Writes always emit version 2.
