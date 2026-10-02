# LAYOUT

Module: `layout/layout.py`  
CLI: `scripts/asterism-layout`

## Purpose

Persist VR panel dock mode (`dashboard` / `theater` / `world`) and planned poses in `~/.config/asterism/layout.json`. Pattern from FrameTop `layout/ft_layout.py` gamescope path ([AZumD/frametop](https://github.com/AZumD/frametop)).

## Behaviour

- **Sole startup owner:** `desktop/asterism-session.sh` runs one `asterism-layout apply` when gamescope creates overlays (`ASTERISM_LAYOUT_OWNER=asterism-session`). Dashboard show/focus/steamvr-up are visibility-only and must not spawn apply (avoids theater→dashboard→world races).
- Concurrent applies: non-blocking flock on `layout.apply.lock` + generation file under `~/.local/state/asterism/`.
- `apply` restores dock modes only (theater→dashboard→world float dance). It does **not** laser-grab by default — auto place was stealing the dashboard laser.
- Absolute place (`asterism-place` / `asterism-layout place`) is **opt-in** (`--place` or `ASTERISM_PLACE_ON_APPLY=1`) until ownership is proven (see `docs/OWNERSHIP_BOUNDARY.md`).
- `asterism-layout live` — read-only OpenVR transform type / absolute inspect for live PerWindow overlays.
- `desktop/asterism-apply-outputs.sh` places KWin outputs edge-to-edge so panels do not share pixels.

## Usage

```
asterism-layout show|sync|init|keys|get-dock INDEX
asterism-layout set-dock INDEX world|theater|dashboard
asterism-layout apply [--wait SECONDS] [--place]
asterism-layout place
asterism-layout release-pointer
asterism-layout live
```
