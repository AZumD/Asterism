# SPATIAL_STATE

Module: `spatial/spatial_state.py`

## Purpose

Asterism-owned World pose persistence keyed by stable display IDs
(`display-1`, …), not SteamVR `frameID` / overlay handles.

Path (default): `~/.local/state/asterism/spatial-state.json`  
Override: `ASTERISM_SPATIAL_PATH`

## Schema

```json
{
  "version": 1,
  "displays": {
    "display-1": {
      "presentation": "world",
      "worldTransform": {
        "translation": {"x": 0.0, "y": 0.0, "z": 0.0},
        "rotation": {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0},
        "scale": {"x": 1.0, "y": 1.0, "z": 1.0}
      }
    }
  }
}
```

Exact Valve transform shape. Atomic write (`tempfile` + `os.replace`).  
Corrupt / wrong version → `SpatialStateError`; callers may `load_or_default()`.
