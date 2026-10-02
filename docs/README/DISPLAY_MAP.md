# DISPLAY_MAP

Module: `spatial/display_map.py`

## Purpose

Single authoritative map:

```
display-N
  -> Nth enabled Asterism virtual display
  -> corresponding Gamescope PerWindow key (screen_keys)
  -> Dashboard Frame via GetFramesWithAssociatedSummonKeys
```

Runtime keys (`asterism.desktop.app.2`) are **not** stable identity.

## API

- `map_displays_to_overlays(keys=..., displays=...)`
- `overlay_key_for_display(display_id, ...)`
- `display_id_for_overlay(overlay_key, ...)`

Pass `keys=` in unit tests to avoid calling `vrcmd`.

CLI: `asterism-dashmgr map`
