# Ownership boundary — spatial persistence investigation

**Status:** instrumentation + race fixes landed; live Frame proof pending (host unreachable during this pass).

## Central question

Can the Gamescope process that called `CreateDashboardOverlay` successfully
`SetOverlayTransformAbsolute` after SteamVR moves that panel to World?

| Result | Meaning |
|--------|---------|
| **A** | Owner path works → Gamescope-owned world transform + Asterism persistence |
| **B** | PermissionDenied / WrongTransformType / instant overwrite → Dashboard Manager owns placement |
| **C** | Inconclusive (exact reason required) |

Do **not** claim restart persistence is solved until demonstrated later.

## Phase 1 — single restore owner

**Duplicates removed**

| Former caller | Change |
|---------------|--------|
| `desktop/asterism-session.sh` | **Sole owner** — one `asterism-layout apply --wait 90` when gamescope starts (`ASTERISM_LAYOUT_OWNER=asterism-session`) |
| `dashboard/asterism-dashboard.py` `focus_desktop_overlay` / `show` / steamvr-up | Visibility only — no layout apply |
| `restore_layout()` | Stub returning skip message |

**Locking:** `layout.apply.lock` (fcntl flock, non-blocking skip) + `layout.apply.generation`.

**Rule:** `asterism-ctl show|hide|toggle` never mutate layout.

## Phase 1 — Desktop Settings dock ComboBox

Selecting a display calls `_load_dock_combo()` → `layout.screen_dock(index)` from `layout.json`
(`dashboard` / `theater` / `world`). No longer stuck on ComboBox construction default.

## Phase 2 — read-only live inspect

```
asterism-layout live          # alias: inspect-live
```

Uses `pointer/helper/asterism-overlay-inspect` (OpenVR Overlay app, read-only).

Capture script: `test/capture_live_inspect.sh` → `$ASTERISM_LOG_DIR/live-inspect/`.

### Observations (fill on Frame)

| State | transform_type | absolute readable? | error |
|-------|----------------|--------------------|-------|
| A fresh | | | |
| B dashboard | | | |
| C theater | | | |
| D world float | | | |
| E world moved | | | |

## Phase 3 — Gamescope owner experiment

- Build: `scripts/asterism-gamescope-build.sh` → `gamescope-asterism/out/gamescope`
- Patcher: `scripts/asterism-gamescope-patch.py` (Unix socket `$XDG_RUNTIME_DIR/asterism/gamescope-openvr.sock`)
- Enable via `asterism.conf`: `ASTERISM_GAMESCOPE_BIN=…` + `ASTERISM_OPENVR_CTRL=1`
- Proof: `scripts/asterism-owner-transform-proof.sh`
- Recover: unset `ASTERISM_GAMESCOPE_BIN`, `asterism-ctl restart-desktop`

### Proof row (fill on Frame)

| Field | Value |
|-------|-------|
| Experimental binary | |
| Built-from commit | |
| Transform type before set | |
| `SetOverlayTransformAbsolute` result | |
| Readback | |
| Headset visible move? | |
| Overwritten within 3s? | |
| **Conclusion** | A / B / C |

## Upstream note

Stock Valve `OpenVRBackend.cpp` creates dashboard overlays and never calls
`SetOverlayTransformAbsolute` on them — Dashboard Manager owns placement in the
stock path. The experiment only tests whether the *creating client* is allowed
to write Absolute after undock.
