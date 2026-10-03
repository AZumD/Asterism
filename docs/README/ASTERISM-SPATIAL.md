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
POST /show
set-presentation world
wait World + inspect-undocked-instance (weak mount)

# Phase 1 — initialize pose (xf may be null at cold mount)
direct-restore(P)
verify get-live-world == P              # intermediate

POST /hide                              # Valve runs normal float lifecycle / nudge
wait inspect-just-floated: justFloatedFromDashboard == false

# Phase 2 — persisted pose wins after nudge
direct-restore(P)
verify get-live-world == P              # SUCCESS criterion
```

A mounted `UndockedOverlay` may exist at cold startup with
`state.xfTransform` undefined. Null `xfTransform` is **not** evidence the
component is unmounted. Valve's nudge reaction no-ops while xf is null, so
phase-1 direct-restore is required before hide.

Live-proven: clearing `justFloatedFromDashboard` before hide is **wrong** —
MobX reacts to the true→false transition and still applies the local
`(0,+0.06,-0.06)` nudge. Automatic restore never calls `clear-just-floated`;
it lets Valve consume the flag via hide, then re-applies P.

Without a saved World transform: Dashboard→show→World→wait weak mount→hide.
No invent pose, no clear flag, no final direct-restore.

No hand/controller fallback on normal startup.
