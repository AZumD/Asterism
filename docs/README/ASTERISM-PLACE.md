# ASTERISM-PLACE

Binary: `pointer/helper/build/asterism-place`  
Source: `pointer/helper/asterism-place.cpp`

## Status

**Legacy / experimental fallback.** Not part of the intended Dashboard Manager
persistence architecture (OpenVR Absolute is blocked; see
[../DASHBOARD_MANAGER.md](../DASHBOARD_MANAGER.md)). Kept for diagnostics; do
not auto-invoke from layout apply.

## Purpose

Place Asterism gamescope PerWindow overlays in world space via virtual-controller
laser grab. SteamVR denies external `SetOverlayTransformAbsolute` on gamescope
dashboard overlays.

## Commands

```
asterism-place head
asterism-place measure <overlay_key>
asterism-place place <overlay_key> <x> <y> <z> <yaw> <pitch> [roll]
asterism-place release
```

`place` takes head-relative metres / degrees (same as `layout.json`).  
`release` only talks to the driver socket (no OpenVR init) and is safe to run when the laser is stuck.

Layout apply does **not** call `place` by default (`ASTERISM_PLACE_ON_APPLY=0`). Use `asterism-layout place` or `apply --place` explicitly.

## Build

```
pointer/helper/build.sh
```

Requires `libopenvr_api.so` and the virtual controller driver installed
(`pointer/driver/install.sh install`), then a SteamVR restart.
