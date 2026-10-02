# ASTERISM-OVERLAY-INSPECT

Binary: `pointer/helper/asterism-overlay-inspect.cpp`  
Built by: `pointer/helper/build.sh` → `pointer/helper/build/asterism-overlay-inspect`

## Purpose

**Read-only** OpenVR helper used by `asterism-layout live`. Reports transform type, absolute matrix (or exact `EVROverlayError`), visibility, and width for each Asterism PerWindow overlay key.

Does not call `SetOverlayTransformAbsolute` or dock APIs.

## Usage

```
asterism-overlay-inspect json asterism.desktop.app.1 [...]
# or via:
asterism-layout live
```
