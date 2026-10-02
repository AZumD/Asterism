# _VERIFY_OWNERSHIP_BOUNDARY

Script: `test/test_ownership_boundary.sh`

## Purpose

Offline checks that Phase 1–3 ownership-boundary instrumentation is wired:

- session sole layout-apply owner + flock
- dashboard visibility-only (no apply spawn)
- Desktop Settings dock load from `layout.json`
- `asterism-layout live` + inspect helper present
- experimental Gamescope scaffolding present

Also runs `test_layout.py` / `test_desktop_settings.py` (includes `screen_dock` + ComboBox load assertions).
