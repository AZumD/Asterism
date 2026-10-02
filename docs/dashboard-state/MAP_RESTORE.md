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

## Direct World restore (staged, unproven live)

Target path (bridge v2 — stage only until headset-validated):

```
saved P
  -> map.set(World, P)
  -> UndockedOverlay.setState({ xfTransform: P })
  -> dockLocation remains World
```

Staging script: `scripts/stage-steamvr-dashmgr-bridge-v2.sh`  
Exposes only:

- `getFramesForSummonKey`
- `applyWorldTransformForSummonKey`
- `getLiveWorldTransformForSummonKey`
- `_uo` registry (UndockedOverlay instances by frameID)

CLI experimental: `asterism-dashmgr direct-restore <overlay-key> <transform.json>`  
Diagnostic: `asterism-dashmgr restore-via-hand <overlay-key> <transform.json>`

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
