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

POST /hide
wait geometry settle via inspect-world-lifecycle
  (World + mountedWeak + !beingDragged + stable panel/scale)

if justFloatedFromDashboard:
  clear-just-floated                    # INTENTIONAL: consumes stale cold-start one-shot
  wait flag false + post-float settle   # nudge may move xf — expected

# Phase 2 — persisted pose wins after nudge
direct-restore(P)
stable verify get-live-world == P       # SUCCESS: consecutive samples
```

A mounted `UndockedOverlay` may exist at cold startup with
`state.xfTransform` undefined. Null xf ≠ unmounted. Phase-1 direct-restore
is required before hide so Valve's nudge reaction can run.

Live-proven:

- Waiting for `justFloatedFromDashboard` to become false by itself after hide
  can hang forever on cold start.
- Clearing the flag **before** hide is wrong (MobX still nudges).
- Clearing the flag **after** hide + geometry settle is correct for exact
  restore: it deliberately triggers the local `(0,+0.06,-0.06)` nudge, then
  phase-2 re-applies P.

`clear-just-floated` remains a general diagnostic, and is also used narrowly
by exact persisted World restoration in that post-hide window only.

Without a saved World transform: Dashboard→show→World→wait weak mount→hide.
No invent pose, no clear flag, no final direct-restore.

No hand/controller fallback on normal startup.
