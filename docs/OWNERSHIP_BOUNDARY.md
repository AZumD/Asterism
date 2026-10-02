# Ownership boundary — spatial persistence investigation

**Status:** Phase 1–2 complete on Frame. Phase 3 experimental Gamescope build in progress (stock `gamescope` has `cap_sys_nice=eip`, which makes LD_PRELOAD into the live process unreliable / non-inspectable).

## Central question

Can the Gamescope process that called `CreateDashboardOverlay` successfully
`SetOverlayTransformAbsolute` after SteamVR moves that panel to World?

| Result | Meaning |
|--------|---------|
| **A** | Owner path works → Gamescope-owned world transform + Asterism persistence |
| **B** | PermissionDenied / WrongTransformType / instant overwrite → Dashboard Manager owns placement |
| **C** | Inconclusive (exact reason required) |

## Phase 1 — single restore owner

**Duplicates removed**

| Former caller | Change |
|---------------|--------|
| `desktop/asterism-session.sh` | **Sole owner** — one `asterism-layout apply --wait 90` when gamescope starts (`ASTERISM_LAYOUT_OWNER=asterism-session`) |
| `dashboard/asterism-dashboard.py` `focus_desktop_overlay` / `show` / steamvr-up | Visibility only — no layout apply |
| `restore_layout()` | Stub returning skip message |

**Locking:** `layout.apply.lock` (fcntl flock, non-blocking skip) + `layout.apply.generation`.

**Rule:** `asterism-ctl show|hide|toggle` never mutate layout.

**Proof:** `test/test_ownership_boundary.sh` → ALL_OK; after dashboard restart, source has no apply spawn.

## Phase 1 — Desktop Settings dock ComboBox

Selecting a display calls `_load_dock_combo()` → `layout.screen_dock(index)` from `layout.json`.

## Phase 2 — live OpenVR inspect (Frame 2026-10-02)

Tool: `asterism-layout live` + `pointer/helper/build/asterism-overlay-inspect`  
Artifacts: `docs/live-inspect/20261002T180243Z_*.json`

| State | visible | transform_type | absolute | absolute_error |
|-------|---------|----------------|----------|----------------|
| A current (configured world) | false | **DashboardTab (5)** | null | **WrongTransformType** |
| B `vrcmd --dock-overlay dashboard` | true | **DashboardTab (5)** | null | **WrongTransformType** |
| C `vrcmd --dock-overlay theater` | true | **DashboardTab (5)** | null | **WrongTransformType** |
| D `vrcmd --dock-overlay world` | true | **DashboardTab (5)** | null | **WrongTransformType** |
| E world idle +3s | true | **DashboardTab (5)** | null | **WrongTransformType** |

### Phase 2 conclusion (external OpenVR client)

SteamVR does **not** change the OpenVR overlay transform type when a Gamescope dashboard panel is “floated” to world/theater/dashboard. From any external Overlay client the type stays `DashboardTab` and `GetOverlayTransformAbsolute` returns `VROverlayError_WrongTransformType` (code 18).

Dock mode changes visibility / dashboard scene-graph placement, **not** the OpenVR Absolute transform API surface.

## Phase 3 — Gamescope owner experiment

### Attempt: LD_PRELOAD into stock gamescope

- Stock `/usr/bin/gamescope` has **`cap_sys_nice=eip`**.
- Live Asterism gamescope process is non-dumpable (`/proc/$pid/maps` Permission denied even for same UID).
- Control socket from preload was stale/racy; **not a valid owner proof**.
- `ASTERISM_OPENVR_CTRL` disabled again for stock recovery.

### Attempt: side-by-side experimental Gamescope (in progress)

- Clone: `gamescope-asterism/src` @ recorded `BUILT_FROM_COMMIT`
- Patcher: `scripts/asterism-gamescope-patch.py` (Unix socket ctrl, no /usr overwrite)
- Build log on Frame: `~/.local/state/asterism/logs/gamescope-build.log`
- Enable via conf when binary ready:
  ```
  ASTERISM_GAMESCOPE_BIN=$HOME/asterism/gamescope-asterism/out/gamescope
  ASTERISM_OPENVR_CTRL=1
  ```
- Proof: `scripts/asterism-owner-transform-proof.sh`

### Proof row (fill when experimental binary runs)

| Field | Value |
|-------|-------|
| Experimental binary | |
| Built-from commit | `0e590c755e79c23607378495d10ceb4308b01a59` (clone tip) |
| Transform type before set | |
| `SetOverlayTransformAbsolute` result | |
| Readback | |
| Headset visible move? | |
| Overwritten within 3s? | |
| **Conclusion** | pending build |

## Interim conclusion

**External Absolute API path is blocked** for Gamescope dashboard overlays (always `DashboardTab` / `WrongTransformType`), matching prior external `PermissionDenied` on SetAbsolute.

**Owner-process SetAbsolute** is not yet proven (Phase 3 build running). Until that returns, do **not** add more virtual-controller persistence hacks.

Likely leaning **B** (Dashboard Manager owns placement) unless owner SetAbsolute succeeds on the experimental uncapped Gamescope.

## Upstream note

Stock Valve `OpenVRBackend.cpp` creates dashboard overlays and never calls `SetOverlayTransformAbsolute` on them.
