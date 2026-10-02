# DISPLAYS

Module: `display/displays.py`

## Purpose

Persistent Linux display topology schema and validation. Multi-display requires identical resolution on every enabled output (gamescope PerWindow). Spatial dock modes live in [LAYOUT.md](LAYOUT.md).

## Schema

`~/.config/asterism/displays.json` — `version`, `displays[]` with `id`, `enabled`, `primary`, `resolution`, `scale`, `rotation`.
