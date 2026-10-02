# ASTERISM-SPATIAL

Script: `scripts/asterism-spatial`  
Unit: `systemd/asterism-spatial.service`

## Purpose

Automatic VR presentation + World-pose persistence across SteamVR restart and
device reboot. Sole owner of startup presentation restore.

## Schema

`~/.local/state/asterism/spatial-state.json` (schema **v2**):

```json
{
  "version": 2,
  "displays": {
    "display-1": {
      "presentation": "world",
      "transforms": {
        "world": { "translation": {...}, "rotation": {...}, "scale": {...} }
      }
    }
  }
}
```

v1 `worldTransform` migrates to `transforms.world` on load; writes are always v2.

## Commands

```
asterism-spatial status
asterism-spatial snapshot-display display-1
asterism-spatial snapshot-all
asterism-spatial restore-display display-1
asterism-spatial restore-all
```

## Lifecycle

```
SteamVR start
  -> asterism-dashboard
  -> asterism-desktop
  -> asterism-spatial ExecStart restore-all

SteamVR stop
  -> asterism-spatial ExecStop snapshot-all (TimeoutStopSec=20, best-effort)
  -> desktop / dashboard stop
```

`asterism-session.sh` may run `asterism-layout sync` only — **not** `apply`.

## Snapshot algorithm

capture → save presentation → merge remembered transforms → if World,
`get-live-world` overrides `transforms.world` → atomic save.

## Restore algorithm

seed presentation transform (if any) → `set-presentation` → for World wait
live UO → `direct-restore`. No hand fallback on normal startup.
