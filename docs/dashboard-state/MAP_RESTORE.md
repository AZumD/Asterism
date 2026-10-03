# MAP_RESTORE — Dashboard Manager world-pose persistence

**Date:** 2026-10-03  
**Related:** [DASHBOARD_MANAGER.md](../DASHBOARD_MANAGER.md), transport commit `d84dfc8`

## Proven: World-pose persistence across a SteamVR restart

**World-pose persistence across a SteamVR restart is proven via external
Asterism state + Dashboard Manager map injection.**

Live SteamVR build: `1790822802`  
Live bridged chunk SHA256: `272c1e40f75bafe28a7108485295681ffdac2a322a6a10f3e2d35278d596dfd9`  
Live shell SHA256: `102fadb99395482467dcd89cbb01c0217adb1d7654e7bebf3b30eee6f8b303cb`  
Live systemui.html SHA256: `710a96000789c73bafcf55ac40a8dad3ef9150c4361e47e2ae1529618af9eac5`

### Bidirectional bridge (proven)

```
CLI
  -> HTTP 127.0.0.1:47831
  -> Asterism FIFO
  -> WebSocket ws://localhost:47832
  -> injected asterism_shell.js
  -> minimal Valve chunk bridge (getFramesForSummonKey)
  -> Dashboard Manager Frame objects
  -> result over WebSocket
  -> CLI
```

SteamVR CSP allows `ws://localhost:*`. Do **not** return to HTTP polling. Do **not** patch CSP.

### Restart proof (live)

Saved World pose **P** (external file `/tmp/world-P.json`):

- translation ≈ `(0.905, 1.603, -1.164)`
- rotation quat with `w ≈ 0.904`

| Phase | frameID | rememberedTransforms | world |
|-------|---------|----------------------|-------|
| Before SteamVR restart | `1177500003` | map[World] = **P** | P |
| After SteamVR restart | `174400003` | `{}` | `null` |

Then:

1. New Frame docked to LeftHand  
2. Asterism seeded pre-restart **P** into `map[World]`  
3. Asterism transitioned LeftHand → World  
4. Panel **visibly** returned to pre-restart location  
5. Captured `map[World]` matched **P** exactly afterward  

Therefore:

| Capability | Status |
|------------|--------|
| Capture world pose | **PROVEN** |
| Serialize outside SteamVR | **PROVEN** |
| SteamVR loses pose on restart | **PROVEN** |
| Resolve newly-created Frame | **PROVEN** |
| Write saved pose into new Frame | **PROVEN** |
| Visible restore across restart | **PROVEN** (map seed + LeftHand→World) |
| Direct live `xfTransform` restore while staying in World | **NOT proven yet** (staged bridge v2) |

## Valve behavior (critical)

`UndockedOverlay.setInitialTransformForLocation`:

- **Dashboard → World:** ignores `map[World]`; takes transform from Dashboard scene graph  
- **LeftHand/RightHand → World:** consumes `map[World]`  

LeftHand→World is a **test oracle / diagnostic fallback** (`restore-via-hand`).  
It must **not** be the normal startup restore path (visible controller dock, awake controller required).

## Direct World restore (shell-only fiber — unproven live)

**Preferred path (no new Valve chunk patch):**

```
overlayKey
  -> v1 getFramesForSummonKey -> Frame / frameID
  -> Dashboard._reactInternals child/sibling walk
  -> class instance with props.frame.frameID match + state.xfTransform
  -> map.set(World, P) + instance.setState({ xfTransform: P })
  -> dockLocation stays World
```

Broken chunk bridge v2 (`83a3bcbf…`) caused a giant black rectangle **on load**
(before any direct-restore call). Analysis:
[BRIDGE_V2_BLACK_RECTANGLE.md](BRIDGE_V2_BLACK_RECTANGLE.md).

CLI:

- `asterism-dashmgr find-live-uo <overlay-key>`
- `asterism-dashmgr inspect-undocked-render <overlay-key>` (Case A vs B + inert `element.type` source metadata; never invoke/mount)
- `asterism-dashmgr inspect-undocked-instance <overlay-key>` (weak fiber: mounted even if `xfTransform` null; primary+alternate)
- `asterism-dashmgr force-dashboard-render` (diagnostic `Dashboard.forceUpdate` only)
- `asterism-dashmgr direct-restore <overlay-key> <transform.json>` (fiber first)
- `asterism-dashmgr get-live-world <overlay-key>` (after ~1s; setState is async)
- `asterism-dashmgr restore-via-hand …` (proven diagnostic fallback)

Cold automatic World restore live finding:

- Frame may be World + in `frames_local_undocked` + weak-mounted `UndockedOverlay`
  while `state.xfTransform` is still undefined.
- Null `xfTransform` ≠ unmounted. Readiness uses `inspect-undocked-instance`;
  `direct-restore` initializes from saved P; `get-live-world` verifies strictly.
- After restore, `POST /hide` used to apply Valve's one-shot float nudge
  (local `(0,+0.06,-0.06)` rotated by xf rotation) when
  `justFloatedFromDashboard && !isActiveDashboardFrame`. Asterism clears the
  flag via `clear-just-floated` only for exact persisted World P, then
  re-verifies live P after hide.

```
inspect-undocked-instance app.2
direct-restore app.2 P.json
get-live-world app.2
clear-just-floated app.2
# hide
get-live-world app.2              # must still match P
```

Contingency Valve patch (Asterism-only register):  
`scripts/stage-steamvr-dashmgr-bridge-v2.1.sh` — stage only if fiber fails live.

Do **not** claim direct restore is proven until visual/live tested on Frame.

## Persistence model

File: `~/.local/state/asterism/spatial-state.json`  
Keyed by stable Asterism IDs (`display-1`, …), **not** `frameID` / SGID / OpenVR handle.

See `spatial/spatial_state.py`, `spatial/display_map.py`, `spatial/restore.py`.

## Probe

`probe` returns JSON-safe `resolveFramesReport` snapshots only (no raw Frame objects).  
Regression: `test/test_spatial_persistence.py`.

## Phase 1 note (historical)

`window.Dashboard` alone cannot resolve Frames (`M.JJ` closed). Chunk bridge required — now live as v1.
