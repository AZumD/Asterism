# ASTERISM-GAMESCOPE

Tree: `gamescope-asterism/`  
Scripts: `scripts/asterism-gamescope-build.sh`, `asterism-gamescope-patch.py`, `asterism-gamescope-ctrl.sh`, `asterism-owner-transform-proof.sh`

## Purpose

Side-by-side experimental Gamescope for the owner-transform proof. **Never overwrites stock `/usr` Gamescope.**

When `ASTERISM_OPENVR_CTRL=1`, the patched OpenVR backend listens on `$XDG_RUNTIME_DIR/asterism/gamescope-openvr.sock` for `inspect` / `set-test-absolute` (one set = one `SetOverlayTransformAbsolute`).

See [gamescope-asterism/README.md](../../gamescope-asterism/README.md) and [../OWNERSHIP_BOUNDARY.md](../OWNERSHIP_BOUNDARY.md).
