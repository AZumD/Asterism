# Ownership boundary — spatial persistence investigation

**Status:** Phase 1–3 complete on Frame (2026-10-02).  
**Decision gate result: B — Gamescope owner transform path is blocked.**

## Central question

Can the Gamescope process that called `CreateDashboardOverlay` successfully
`SetOverlayTransformAbsolute` after SteamVR moves that panel to World?

| Result | Meaning |
|--------|---------|
| A | Owner path works |
| **B** | **PermissionDenied / WrongTransformType — Dashboard Manager owns placement** |
| C | Inconclusive |

## Phase 1 — single restore owner

Sole owner: `desktop/asterism-session.sh` (`ASTERISM_LAYOUT_OWNER=asterism-session`).  
Dashboard `show`/`focus`/`steamvr-up` are visibility-only. Apply uses flock + generation.  
`test/test_ownership_boundary.sh` → ALL_OK.

## Phase 1 — Desktop Settings dock ComboBox

`_load_dock_combo()` loads `layout.screen_dock(index)` from `layout.json`.

## Phase 2 — live OpenVR inspect (external client)

Artifacts: `docs/live-inspect/20261002T180243Z_*.json`

| State | transform_type | absolute | error |
|-------|----------------|----------|-------|
| A–E (dashboard / theater / world) | **DashboardTab (5)** | null | **WrongTransformType (18)** |

SteamVR does **not** expose Absolute OpenVR transforms for these panels in any dock mode.

## Phase 3 — Gamescope owner experiment

### Stock gamescope note

`/usr/bin/gamescope` has `cap_sys_nice=eip` (non-dumpable). LD_PRELOAD owner-so was abandoned for the proof.

### Experimental binary

- Path: `~/asterism/gamescope-asterism/out/bin/gamescope` (via `gamescope-wrap`)
- Built from Valve tip `0e590c755e79c23607378495d10ceb4308b01a59` + Asterism OpenVR ctrl patch
- Stock `/usr` binary untouched; Asterism switched back to stock after the proof

### Owner-side result (ONE `set-test-absolute`)

From inside the Gamescope OpenVR client that created the overlay (`docs/live-inspect/owner-setabs.json`):

```json
{
  "set_error": "VROverlayError_PermissionDenied",
  "set_error_code": 12,
  "before": {
    "transform_type": {"id": 5, "name": "DashboardTab"},
    "absolute_error": "VROverlayError_WrongTransformType"
  },
  "after": {
    "transform_type": {"id": 5, "name": "DashboardTab"},
    "absolute_error": "VROverlayError_WrongTransformType"
  }
}
```

| Field | Value |
|-------|-------|
| Transform type before | DashboardTab (5) |
| `SetOverlayTransformAbsolute` | **PermissionDenied (12)** |
| Readback | still DashboardTab / WrongTransformType |
| Visible Absolute move via API | **no** (API rejected) |
| SteamVR overwrite | N/A (set never took) |

## Conclusion

**B. Gamescope owner transform path is blocked.**

Even the process that called `CreateDashboardOverlay` cannot `SetOverlayTransformAbsolute` after world undock; SteamVR returns `PermissionDenied` while the overlay remains `DashboardTab`.

**Do not** add more virtual-controller / Absolute-transform persistence hacks.

Next investigation (separate pass): SteamVR dashboard scene-graph / dock transform mechanism (Dashboard Manager placement), not OpenVR Absolute overlays.

Persistence across SteamVR restart is **not** claimed solved.
