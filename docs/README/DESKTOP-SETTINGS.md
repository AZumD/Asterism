# DESKTOP-SETTINGS

App: `desktop-settings/asterism_desktop_settings.py`  
Launcher: `desktop-settings/asterism-desktop-settings`  
Desktop entry: `desktop-settings/asterism-desktop-settings.desktop`

## Purpose

Boring GUI for display topology (`~/.config/asterism/displays.json`). Talks to `displays.py` / `asterism-displayctl`. Explicit restart for compositor changes.

## Stack

- **GTK3 + PyGObject** on the SteamOS host (Frame ships this; **not** tkinter — `libtk` is missing).
- Host wrapper mirrors FrameTop's `ft-display-settings` + `ft-shell-env` pattern ([AZumD/frametop](https://github.com/AZumD/frametop)): attaches to nested Plasma via `…/asterism_nested/plasmashell.env` when launched from SSH.
- v0.1 covers FrameTop's Screens-tab concerns only (count / resolution / scale / rotation / primary / restart). No spatial Layout/Visibility/Background.

## Usage

```
asterism-desktop-settings
# or Applications → Asterism Desktop Settings (inside the VR desktop)
```

From SSH, the launcher finds nested `plasmashell` and exports its Wayland/X11/DBus env (same idea as FrameTop's plasmashell.env). Restart desktop is detached via `systemd-run --user`.
