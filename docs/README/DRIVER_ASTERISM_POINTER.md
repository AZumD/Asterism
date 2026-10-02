# DRIVER_ASTERISM_POINTER

Source: `pointer/driver/driver_asterism_pointer.cpp`  
Install: `pointer/driver/install.sh`

## Status

**Legacy / experimental fallback.** Not part of Dashboard Manager persistence.
Do not auto-invoke.

## Purpose

SteamVR external driver that exposes a virtual controller. `asterism-place`
drives it over `@asterism_pointer` to laser-grab floating dashboard panels.

## Install

```
pointer/driver/install.sh install    # copies to ~/.local/share/asterism/asterism_pointer + vrpathreg
pointer/driver/install.sh uninstall
pointer/driver/install.sh status
```

SteamVR only loads external drivers at startup — **restart SteamVR** after
install or uninstall.
