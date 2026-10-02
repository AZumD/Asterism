# SteamVR Dashboard Manager — spatial ownership model

**Status (2026-10-02):** Read-only reverse engineering of installed SteamVR UI on Frame.  
**No Valve files were patched in this pass.**  
Related: [OWNERSHIP_BOUNDARY.md](OWNERSHIP_BOUNDARY.md) (OpenVR Absolute path = dead end, commit `57012ce`).

## Verdict (this pass)

**Conclusion B:** Dashboard Manager state is **readable only inside systemui JS**. Presentation can already be mutated from outside via `vrcmd --dock-overlay`. **World pose** (`xfTransform` / last-relative map) is **not** exposed outside systemui — a **minimal SteamVR UI bridge** is required before any restore proof.

Do **not** claim pose persistence is solved.

---

## 1. Architecture

### Files

| Path | Role |
|------|------|
| `chunk~8012d0c89.js` | Main dashboard UI: frames, docking, UndockedOverlay, grab/snap, theater |
| `systemui.js` | Shell / entry; hosts `window.Dashboard` |
| `localization/dashboard_english.json` | `#FloatInWorld`, `#ReturnToDashboard`, `#ViewInTheater`, controller dock strings |
| `vrcmd` | Sends mailbox `vrcmd_dock_overlay` with `{overlay_key, dock_location}` |

Search artifacts: `docs/dashboard-state/_search/`.

### Object model

```
Dashboard (window.Dashboard / Bt)
  └─ Frame manager M.JJ
       ├─ frames[]
       ├─ frames_local_undocked[]   ← undocked panels get UndockedOverlay (St)
       ├─ GetFrame / GetFrameWithTabId / GetFramesWithAssociatedSummonKeys
       └─ GetDockLocationTransformID(location) / RegisterFrameDockLocation / _setDockLocation

Frame
  ├─ frameID
  ├─ associatedSummonOverlayKeys[] / activePage.summonOverlayKey  ← links to overlay key
  ├─ docking (component)
  │    ├─ dockLocation          ← presentation enum yWq
  │    ├─ m_mapLastRelativeTransformForDockLocation  ← remembered poses
  │    ├─ SetDockLocation / SetInTheater / SetBeingDragged / …
  │    └─ panelTranslationForResizeOrigin / mainPanelOrigin
  ├─ size.scaleForActivePage
  ├─ curvature.curvatureTransformOriginID
  └─ frameControlsTransformID / activePage.mainPanelSGID

UndockedOverlay (React component St)
  └─ state.xfTransform { translation, rotation }  ← live spatial pose in scene graph
  └─ renders <dLy transform={xfTransform}> scene-graph nodes
```

### DashboardTab overlay vs spatial frame

Gamescope `CreateDashboardOverlay` → OpenVR type stays **DashboardTab**.  
SteamVR wraps that overlay content inside a **Frame** + scene-graph (`dLy` nodes, SGIDs).  
**Spatial placement is Frame/scene-graph state, not OpenVR Absolute transform.**

---

## 2. Presentation state

Enum (minified `yWq` / `l.yWq`):

| Name | UI |
|------|-----|
| `Dashboard` | Dock on Dashboard / Return to Dashboard |
| `World` | Float in World |
| `Theater` | View in Theater |
| `LeftHand` / `RightHand` | Dock on controllers |
| `Boot` | boot path |

**Where it lives:** `frame.docking.dockLocation` (MobX computed over frame-manager dock registration).

**Not** `GetOverlayTransformType` (always DashboardTab).

Controller docking uses the **same** `SetDockLocation` model.

### Call chain — presentation change

```
UI button (#FloatInWorld etc.)
  → frame.docking.SetDockLocation(yWq.*)
      → (optional) VRClient.ShowDashboardOverlay when docking to Dashboard
      → JJ._setDockLocation(frameID, location)
      → SetJustFloatedFromDashboard(location == World)

OR

vrcmd --dock-overlay <location> <overlay_key>
  → mailbox "vrcmd_dock_overlay"
  → Dashboard.onVrCmdDockOverlayRequested
      → resolve frame via GetFramesWithAssociatedSummonKeys(overlay_key)
      → frame.docking.SetDockLocation(...)
```

`onVrCmdDockOverlayRequested` maps strings: `dashboard|lefthand|righthand|theater|world`.

---

## 3. World pose

| Property | Location | Shape |
|----------|----------|-------|
| Live pose | `UndockedOverlay.state.xfTransform` | `{ translation:{x,y,z}, rotation:(quat/euler helpers) }` |
| Remembered | `docking.m_mapLastRelativeTransformForDockLocation.get(location)` | same transform object, keyed by dock location |
| Written when | `endFloatingWindowMoveInternal` | for World / LeftHand / RightHand |
| Theater initial | `bt(frame)` using `GetStoredTransform` / `CalcDashboardTransform` / head pose | not Absolute OpenVR |
| World initial (no memory) | `requestSGTransform(GetDockLocationTransformID(Dashboard))` | may warn `Failed to get SGTransform in setInitialTransformForLocation` |
| Resize | reaction adjusts `xfTransform` via `MultiplyTransforms` + panel height delta | |
| Scale | `frame.size.scaleForActivePage` (+ dashboardScale) | |
| Curvature | `frame.curvature.curvatureTransformOriginID` | |

Scene-graph helpers: `VRHTML.NextSGID`, `requestSGTransform`, `requestSGTransformRelative`, `MultiplyTransforms`, `ChangeBasis`, `GetPose`.

---

## 4. Identity

| ID | Stable? | Role |
|----|---------|------|
| `display-1` / `display-2` | **Yes (Asterism)** | Persist against these |
| `asterism.desktop.app.N` | **No** | Gamescope PerWindow runtime key |
| `frame.frameID` | Runtime (systemui session) | Dashboard Manager frame |
| `summonOverlayKey` / `associatedSummonOverlayKeys` | Runtime link | Maps overlay key → frame |
| SGID / `GetDockLocationTransformID` | Runtime | Scene-graph node ids (`xf…` random strings also used) |
| Overlay handle | Runtime | OpenVR handle via GetOverlayInfo |

**Startup mapping Asterism should use:**

```
display-N  →  N-th enabled display  →  N-th PerWindow key from screen_keys()
           →  Dashboard frame via GetFramesWithAssociatedSummonKeys(overlay_key)
```

---

## 5. Mutation path summary

| Action | Callable outside systemui? |
|--------|----------------------------|
| Set presentation (dashboard/world/theater/hands) | **Yes** — `vrcmd --dock-overlay` (mailbox) |
| Read presentation / frameID / xfTransform | **No** — needs systemui bridge |
| Set world pose | **Only inside systemui** today (grab path / setState xfTransform) |
| Read SGTransform | Inside systemui via `uS7.requestSGTransform` |

No public VRHTML “SetWorldPose(overlayKey, xf)” found in the UI surface.

---

## 6. Restart behavior (inferred + prior Asterism observation)

- OpenVR overlay keys are **recreated** by Gamescope → new handles.
- Dashboard **frames** are rebuilt when systemui starts → new `frameID` / SGIDs.
- `m_mapLastRelativeTransformForDockLocation` is **in-memory MobX** → lost on SteamVR/systemui restart unless Valve persists it elsewhere (no durable dock/pose store found in user config for Asterism overlays).
- Presentation often appears as Dashboard after restart even when Asterism `layout.json` says world — consistent with **new frame defaulting to Dashboard** and Asterism only re-driving `vrcmd --dock-overlay` (pose never restored).

Live Phase 4/6 JSON diffs of `xfTransform` were **not** captured this pass (requires bridge). Prior headset symptom already shows pose loss across restart.

---

## 7. Conclusion

**B. Dashboard Manager state is readable but restore path requires a minimal SteamVR UI bridge.**

- Presentation mutation path: already known (`vrcmd` / SetDockLocation).
- Pose read/write: trapped in systemui (`xfTransform` + last-relative map).
- OpenVR Absolute: ruled out (`57012ce`).

---

## 8. Recommended next experiment

**STOP before implementing persistence.** Propose a **hash-gated, backup-first, ~minimal systemui patch** that exposes a local Unix socket (or mailbox dump) from `window.Dashboard` / `M.JJ.frames`:

For each frame with Asterism summon keys, serialize:

```json
{
  "frameID": "...",
  "overlay_keys": ["asterism.desktop.app.2"],
  "dockLocation": "World",
  "xfTransform": { "translation": {...}, "rotation": {...} },
  "lastRelative": { "World": {...} },
  "scale": ...,
  "curvature_origin_id": "..."
}
```

Then **one** controlled proof: capture → move → restore via the same JS setters Valve uses (`SetDockLocation` + set xfTransform / map entry) — no loops.

Until that bridge exists, `asterism-dashboard-inspect` reports live pose fields as `null`.

**2026-10-02 update:** Phase 1 confirmed `window.Dashboard` alone cannot resolve Frames.
Minimal chunk bridge + `asterism_shell.js` loopback IPC are implemented; see
[dashboard-state/MAP_RESTORE.md](dashboard-state/MAP_RESTORE.md).
Also: Valve **ignores** `map[World]` on Dashboard→World; only hand→World consumes it.

---

## Legacy tooling

`asterism_pointer` / `asterism-place` = **legacy / experimental fallback**. Not part of Dashboard Manager persistence architecture. Do not auto-invoke.
