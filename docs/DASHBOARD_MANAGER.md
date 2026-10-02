# SteamVR Dashboard Manager — spatial ownership model

**Status (2026-10-03):** Live bridge + restart persistence proven via map injection.  
Related: [OWNERSHIP_BOUNDARY.md](OWNERSHIP_BOUNDARY.md), [dashboard-state/MAP_RESTORE.md](dashboard-state/MAP_RESTORE.md).

## Verdict

**Conclusion B still holds for ownership:** spatial pose lives in Dashboard Manager / systemui, not OpenVR Absolute.

**Persistence status:**

> **World-pose persistence across a SteamVR restart is proven via external
> Asterism state + Dashboard Manager map injection.**

Proven path: seed `map[World]` then **LeftHand → World** (diagnostic).  
Direct live `UndockedOverlay.state.xfTransform` restore while remaining docked to World is **implemented as staged bridge v2** and is **not live-proven yet**.

Restart evidence:

| | Before restart | After restart |
|--|----------------|---------------|
| frameID | `1177500003` | `174400003` |
| rememberedTransforms | map[World]=P | `{}` |
| world | P | `null` |

External re-seed of P into the new Frame + LeftHand→World **visibly** restored the panel; post-capture matched P.

---

## 1. Architecture

### Files

| Path | Role |
|------|------|
| `chunk~8012d0c89.js` | Frames, docking, UndockedOverlay, grab/snap |
| `systemui.js` | Shell / entry; hosts `window.Dashboard` |
| `asterism_shell.js` | Injected WS client + Asterism-only pose commands |
| `vrcmd` | Presentation via mailbox `vrcmd_dock_overlay` |

### Object model

```
Dashboard (window.Dashboard / Bt)
  └─ Frame manager M.JJ
       ├─ frames[] / frames_local_undocked[]
       ├─ GetFramesWithAssociatedSummonKeys
       └─ GetDockLocationTransformID / _setDockLocation

Frame
  ├─ frameID                          ← runtime only
  ├─ associatedSummonOverlayKeys[]
  └─ docking
       ├─ dockLocation                ← yWq presentation
       ├─ m_mapLastRelativeTransformForDockLocation
       └─ SetDockLocation

UndockedOverlay (React)
  └─ state.xfTransform                ← live rendered World pose
```

### DashboardTab vs spatial frame

Gamescope `CreateDashboardOverlay` → OpenVR type stays **DashboardTab**.  
Spatial placement is Frame / scene-graph state, **not** OpenVR Absolute.

---

## 2. Presentation

Enum `yWq`: Dashboard, World, Theater, LeftHand, RightHand, Boot.

Mutable outside systemui via `vrcmd --dock-overlay` / `SetDockLocation`.

---

## 3. World pose

| Property | Location |
|----------|----------|
| Live | `UndockedOverlay.state.xfTransform` |
| Remembered | `docking.m_mapLastRelativeTransformForDockLocation` |
| Written on grab end | `endFloatingWindowMoveInternal` |

### Valve gate

- Dashboard→World **ignores** `map[World]`
- LeftHand/RightHand→World **consumes** `map[World]`

### Asterism restore paths

| Path | Command | Status |
|------|---------|--------|
| Diagnostic | `restore-via-hand` (seed + LeftHand→World) | **Proven** across restart |
| Preferred | `direct-restore` (map + `setState(xfTransform)`) | Staged; **unproven live** |

---

## 4. Identity

| ID | Stable? |
|----|---------|
| `display-N` | **Yes** — persist against these |
| `asterism.desktop.app.N` | No — runtime Gamescope key |
| `frameID` / SGID / handle | No — recreated every SteamVR start |

Mapping: `spatial/display_map.py`  
`display-N` → Nth enabled display → Nth `screen_keys()` overlay → Frame via bridge.

---

## 5. Persistence file

`~/.local/state/asterism/spatial-state.json` (atomic writes).  
Exact Valve transform preserved. Not merged into FrameTop-style layout.json yet.

---

## 6. Capture / startup (MVP)

- **Capture:** explicit `asterism-dashmgr save-world display-N` after a World move. Prefer hooking `endFloatingWindowMoveInternal` later; no high-frequency polling.
- **Startup:** wait for WS shell bridge + runtime overlays; map displays; load spatial-state; restore each pose (direct first). Missing Frame / corrupt pose → skip that display; SteamVR remains usable.

---

## 7. Bridge surface

`window.__ASTERISM_STEAMVR` (purpose-built only):

- v1 (live): `yWq`, `getFramesForSummonKey`
- v2 (staged): + `_uo`, `applyWorldTransformForSummonKey`, `getLiveWorldTransformForSummonKey`

No `eval`, no arbitrary object traversal, no general remote execution.

---

## Legacy tooling

`asterism_pointer` / `asterism-place` = **legacy**. Not part of Dashboard Manager persistence.
