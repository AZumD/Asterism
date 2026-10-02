# Gamescope owner-transform experiment (Asterism)

**Stock system Gamescope is never overwritten.** This tree builds a side-by-side
binary used only when `ASTERISM_GAMESCOPE_BIN` points at it.

## Question

Can the Gamescope process that called `CreateDashboardOverlay` successfully
`SetOverlayTransformAbsolute` on that overlay after SteamVR moves it to World?

## Build (on Frame)

```bash
~/asterism/scripts/asterism-gamescope-build.sh
```

Clones Valve gamescope under `gamescope-asterism/src`, runs
`scripts/asterism-gamescope-patch.py` (idempotent string-anchor hooks for the
Unix control socket), builds to a private prefix.

Produces: `~/asterism/gamescope-asterism/out/gamescope`

## Enable

In `~/.config/asterism/asterism.conf`:

```bash
ASTERISM_GAMESCOPE_BIN=$HOME/asterism/gamescope-asterism/out/gamescope
ASTERISM_OPENVR_CTRL=1
```

Restart **only** the Asterism desktop (`asterism-ctl restart-desktop`).

## Control socket

When `ASTERISM_OPENVR_CTRL=1`, the experimental backend listens on:

```
$XDG_RUNTIME_DIR/asterism/gamescope-openvr.sock
```

Commands (text, one line):

```
inspect
set-test-absolute <overlay-key> <x> <y> <z> <yaw> <pitch> <roll>
```

Helper:

```bash
~/asterism/scripts/asterism-gamescope-ctrl.sh inspect
~/asterism/scripts/asterism-gamescope-ctrl.sh set-test-absolute asterism.desktop.app.2 0 0 -1.5 0 0 0
```

## Disable / recover

```bash
# comment out or remove ASTERISM_GAMESCOPE_BIN from asterism.conf
~/asterism/scripts/asterism-ctl.sh restart-desktop
```

`recover-asterism.sh` remains unchanged and does not touch this binary.

## Upstream note

Stock `OpenVRBackend.cpp` creates dashboard overlays and never sets absolute
transforms — SteamVR Dashboard Manager owns placement. This experiment only
proves whether the *creating client* is allowed to write Absolute after undock.
