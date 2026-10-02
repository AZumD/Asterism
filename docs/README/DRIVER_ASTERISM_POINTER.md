# DRIVER_ASTERISM_POINTER

Source: `pointer/driver/driver_asterism_pointer.cpp`  
Install: `pointer/driver/install.sh`

## Purpose

SteamVR external driver that exposes a virtual controller. `asterism-place`
drives it over the abstract datagram socket `@asterism_pointer` to laser-grab
and move floating dashboard panels (gamescope PerWindow desktops).

Adapted from FrameTop `ft_pointer` ([AZumD/frametop](https://github.com/AZumD/frametop));
Asterism-owned binary and socket name — no FrameTop runtime dependency.

## Install

```
pointer/driver/install.sh install    # copies to ~/.local/share/asterism/asterism_pointer + vrpathreg
pointer/driver/install.sh uninstall
pointer/driver/install.sh status
```

SteamVR only loads external drivers at startup — **restart SteamVR** after
install or uninstall.
