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
  -> asterism-spatial ExecStart=- restore-all
     (leading '-' keeps unit active/exited even if restore fails,
      so ExecStop stays armed; diagnostics in spatial-last-restore.json)

SteamVR stop
  -> asterism-spatial ExecStop snapshot-all (TimeoutStopSec=20, WS wait 3s)
     each successful display is saved atomically before the next
  -> desktop / dashboard stop
```

`asterism-session.sh` may run `asterism-layout sync` only — **not** `apply`.

## Snapshot algorithm

capture → save presentation → merge remembered transforms → if World,
`get-live-world` overrides `transforms.world` → atomic save.

## Restore algorithm

**Dashboard / Theater:** seed (if any) → `set-presentation` → validate capture.

**World (WORLD MATERIALIZATION):** Valve only mounts `UndockedOverlay` after a
real Dashboard→World transition while the dashboard is shown; `map[World]` alone
is not enough.

```
seed-presentation-transform(world, P)   # if transforms.world exists
set-presentation dashboard
POST /show                              # visibility/materialization only
set-presentation world
wait dockLocation==World AND inspect-undocked-instance (weak mount)
direct-restore(P)                       # if transforms.world exists; may init null xf
verify get-live-world == P              # strict path
clear-just-floated                      # suppress Valve post-float nudge
POST /hide                              # best-effort; never masks primary error
verify get-live-world == P again        # final hidden-dashboard pose must match P
```

A mounted `UndockedOverlay` may exist at cold startup with
`state.xfTransform` undefined. Null `xfTransform` is **not** evidence the
component is unmounted. Readiness uses weak identity; `find-live-uo` stays
strict (mounted + non-null xf) for diagnostics only.

Valve applies a one-shot local nudge `(0, +0.06, -0.06)` (rotated by current
xf rotation) when `justFloatedFromDashboard` is consumed on Dashboard hide.
Asterism clears that flag **only** when restoring an exact persisted World
transform P — not for generic World presentation without saved pose.

Without a saved World transform, materialize only — do not invent a pose and
do not clear the float flag (preserve normal Valve behavior).

No hand/controller fallback on normal startup.
