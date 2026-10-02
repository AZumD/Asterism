# Asterism DEVELOPMENT

## Architecture

Three separate states:

| State | Meaning |
|-------|---------|
| SteamVR session | `vrserver` / `vrcompositor` / `steamvr.service` |
| Desktop session | gamescope + nested Plasma (`asterism-desktop.service`) |
| Desktop visibility | Whether the Desktop dashboard overlay is focused/shown |

```
SteamVR starts
    ↓
asterism-dashboard.service  (WantedBy/BindsTo steamvr)
    ↓ ensure desktop once
asterism-desktop.service    (WantedBy/BindsTo steamvr, Restart=on-failure)
    ↓
gamescope --backend openvr --vr-overlay-key asterism.desktop
    ↓
nested Plasma (stays alive while SteamVR runs)

Shell "Desktop" control / asterism-ctl show|hide|toggle
    → visibility/focus only (vrcmd + ShowDashboardOverlay)
    → NEVER starts/stops Plasma on the happy path
```

## Lifecycle

**What starts the desktop:** `asterism-dashboard` when SteamVR becomes healthy, and systemd `WantedBy=steamvr.service` on `asterism-desktop`.

**What keeps it alive:** systemd `Restart=on-failure` (rate-limited) + dashboard supervisor crash-recovery; hide does not stop it.

**What stops it:** SteamVR going down (`BindsTo=steamvr.service`), dashboard exit, or **admin** `asterism-ctl stop-desktop` / recover script.

**When hidden:** Plasma apps and gamescope stay running; only dashboard focus is cleared (`vrcmd --hidedashboard`).

| Command | Behavior |
|---------|----------|
| `show` | Focus Desktop overlay; crash-recover desktop if missing |
| `hide` | Hide dashboard; keep session |
| `toggle` | Visibility only |
| `status` | `steamvr_running`, `desktop_running`, `desktop_visible` |
| `stop-desktop` | **Admin/debug/recovery only** — terminates session |

## Process / service layout

| Unit / process | Role |
|----------------|------|
| `asterism-dashboard.service` | IPC + HTTP control; supervisor |
| `asterism-desktop.service` | Persistent gamescope + Plasma |
| `asterism-displayctl` | Display topology backend |
| Desktop Settings | GUI over displayctl |

Logs: `~/.local/state/asterism/logs/`  
Config: `~/.config/asterism/` (`displays.json`, `asterism.conf`)  
Socket: `$XDG_RUNTIME_DIR/asterism/control.sock`  
HTTP: `http://127.0.0.1:47831` (for shell inject; may be blocked by private-network rules)

## SteamVR / OpenVR integration

| Point | Mechanism |
|-------|-----------|
| Overlay key | `asterism.desktop` (stable; PerWindow only if multiple enabled displays) |
| Friendly name | `Desktop` |
| Shell control (Phase C) | Inject `asterism_shell.js` via `systemui.html` → `VRHTML.VRClient.ShowDashboardOverlay` + optional HTTP `/show` |
| Show/hide | `vrcmd --showdashboard` / `--hidedashboard`; dock-overlay best-effort |
| Input | SteamVR laser → gamescope VR mouse |
| Close button | `--vr-overlay-enable-control-bar-close` **not** set |

### Running-app representation

SteamVR may still list the gamescope Desktop overlay like a dashboard surface. We deliberately do **not** enable the control-bar **close** button. Fully suppressing the normal tab/app chrome is deferred if it requires deeper Valve UI patches — document as follow-up. Closing/hiding via Asterism shell paths must not kill the session.

## Display topology (Desktop Settings v0.1)

Config: `~/.config/asterism/displays.json` — outputs only (no spatial pose/curve/anchors).

```bash
asterism-displayctl list|--json
asterism-displayctl add [--resolution WxH]
asterism-displayctl remove ID
asterism-displayctl set ID resolution|scale|rotation|enabled VALUE
asterism-displayctl set-primary ID
asterism-displayctl apply   # stage; requires desktop restart
asterism-desktop-settings   # GTK3 GUI (host)
asterism-ctl restart-desktop
```

Apply stages config; **Restart desktop** is explicit (confirms apps may close). GUI is GTK3/PyGObject — Frame has no `libtk`, and we do not pull FrameTop's distrobox+PySide6 settings stack. Restart uses the **real user D-Bus** (nested Plasma's private bus cannot reach systemd).

After SteamVR comes back, the dashboard ensures the desktop and restores dock modes from `layout.json` (does **not** force dashboard dock).


## Phase C patch safety

```bash
scripts/patch-steamvr-ui.sh --dry-run --yes
scripts/patch-steamvr-ui.sh --yes          # after backup + hash gate
scripts/patch-steamvr-ui.sh --status
scripts/patch-steamvr-ui.sh --unpatch --yes
```

Stock hashes: `compatibility/manifest.json`. Patched hashes: `compatibility/patched-hashes.json`.

After patch: clear `~/.cache/SteamVR/htmlcache` and **manually** restart SteamVR.

## Borrowed from FrameTop (concepts only)

Reference: [AZumD/frametop](https://github.com/AZumD/frametop).

gamescope OpenVR overlays, nested Plasma wrapper, `BindsTo`/`Requisite` vs SteamVR, SIGTERM-before-kill, hash-gated patching, display persistence, Desktop Settings host launcher + Screens-tab topology + restart-desktop confirm, KWin edge-to-edge outputs, `layout.json` dock/theater/world restore via `vrcmd` + world place via `asterism-place` / `asterism_pointer` (FrameTop `ft-layout` / `ft-pointer` place pattern). **No FrameTop runtime dependency** (no distrobox, no PySide6/Kirigami, no `ft_*` binaries).

## Recovery

```bash
~/asterism/scripts/recover-asterism.sh --yes --no-restart
~/asterism/scripts/asterism-status.sh
```

Recover restores Valve UI if a Phase C patch marker exists and removes `asterism_shell.js`.

## Disable Asterism

```bash
~/asterism/scripts/recover-asterism.sh --yes --no-restart
systemctl --user disable asterism-dashboard.service asterism-desktop.service
rm -f ~/.config/systemd/user/asterism-*.service ~/.local/bin/asterism-ctl
systemctl --user daemon-reload
```
