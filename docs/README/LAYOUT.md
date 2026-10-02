# LAYOUT

Module: `layout/layout.py`  
CLI: `scripts/asterism-layout`

## Purpose

Persist VR panel dock mode (`dashboard` / `theater` / `world`) and planned poses in `~/.config/asterism/layout.json`. Pattern from FrameTop `layout/ft_layout.py` gamescope path ([AZumD/frametop](https://github.com/AZumD/frametop)).

## Behaviour

- On desktop start / SteamVR-up: `asterism-layout apply` restores each screen’s dock mode only (theater→dashboard→world float dance). It does **not** laser-grab by default — auto place was stealing the dashboard laser and shoving panels around without landing on the saved poses.
- Absolute place (`asterism-place` / `asterism-layout place`) is **opt-in** (`--place` or `ASTERISM_PLACE_ON_APPLY=1`) until the grab path is reliable.
- `asterism-layout release-pointer` force-hides the virtual controller if the laser is stuck.
- `desktop/asterism-apply-outputs.sh` places KWin outputs edge-to-edge so panels do not share pixels.

## Usage

```
asterism-layout show|sync|init|keys
asterism-layout set-dock INDEX world|theater|dashboard
asterism-layout apply [--wait SECONDS] [--place]
asterism-layout place
asterism-layout release-pointer
```
