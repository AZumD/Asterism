# OVERVIEW

Asterism tools and docs for a SteamVR-native Linux desktop on Steam Frame.

## Scripts / modules

| Path | Doc |
|------|-----|
| `scripts/_env.sh` | [SCRIPTS_ENV.md](SCRIPTS_ENV.md) |
| `scripts/backup-steamvr-ui.sh` | [BACKUP-STEAMVR-UI.md](BACKUP-STEAMVR-UI.md) |
| `scripts/restore-steamvr-ui.sh` | [RESTORE-STEAMVR-UI.md](RESTORE-STEAMVR-UI.md) |
| `scripts/recover-asterism.sh` | [RECOVER-ASTERISM.md](RECOVER-ASTERISM.md) |
| `scripts/asterism-status.sh` | [ASTERISM-STATUS.md](ASTERISM-STATUS.md) |
| `scripts/asterism-ctl.sh` | [ASTERISM-CTL.md](ASTERISM-CTL.md) |
| `scripts/patch-steamvr-ui.sh` | [PATCH-STEAMVR-UI.md](PATCH-STEAMVR-UI.md) |
| `scripts/asterism-displayctl` | [ASTERISM-DISPLAYCTL.md](ASTERISM-DISPLAYCTL.md) |
| `install.sh` | [INSTALL.md](INSTALL.md) |
| `dashboard/asterism-dashboard.py` | [ASTERISM-DASHBOARD.md](ASTERISM-DASHBOARD.md) |
| `dashboard/asterism_ws.py` | [ASTERISM_WS.md](ASTERISM_WS.md) |
| `desktop/asterism-session.sh` | [ASTERISM-SESSION.md](ASTERISM-SESSION.md) |
| `display/displays.py` | [DISPLAYS.md](DISPLAYS.md) |
| `layout/layout.py` | [LAYOUT.md](LAYOUT.md) |
| `scripts/asterism-layout` | [ASTERISM-LAYOUT.md](ASTERISM-LAYOUT.md) |
| `pointer/helper/asterism-overlay-inspect.cpp` | [ASTERISM-OVERLAY-INSPECT.md](ASTERISM-OVERLAY-INSPECT.md) |
| `pointer/helper/asterism-place.cpp` | [ASTERISM-PLACE.md](ASTERISM-PLACE.md) (**legacy** fallback) |
| `gamescope-asterism/` + `scripts/asterism-gamescope-*.sh` | [ASTERISM-GAMESCOPE.md](ASTERISM-GAMESCOPE.md) |
| `scripts/asterism-dashboard-inspect` | [ASTERISM-DASHBOARD-INSPECT.md](ASTERISM-DASHBOARD-INSPECT.md) |
| `scripts/asterism-dashmgr` | [ASTERISM-DASHMGR.md](ASTERISM-DASHMGR.md) |
| `scripts/patch-steamvr-dashmgr-bridge.sh` | [PATCH-STEAMVR-DASHMGR-BRIDGE.md](PATCH-STEAMVR-DASHMGR-BRIDGE.md) |
| `scripts/patch-steamvr-taskbar-order.sh` | [PATCH-STEAMVR-TASKBAR-ORDER.md](PATCH-STEAMVR-TASKBAR-ORDER.md) (PoC Dt reorder) |
| `scripts/stage-steamvr-dashmgr-bridge-v2.sh` | [STAGE-STEAMVR-DASHMGR-BRIDGE-V2.md](STAGE-STEAMVR-DASHMGR-BRIDGE-V2.md) (broken; do not apply) |
| `scripts/stage-steamvr-dashmgr-bridge-v2.1.sh` | [STAGE-STEAMVR-DASHMGR-BRIDGE-V2.1.md](STAGE-STEAMVR-DASHMGR-BRIDGE-V2.1.md) (contingency) |
| `spatial/react_fiber.py` | [REACT_FIBER.md](REACT_FIBER.md) |
| `spatial/spatial_state.py` | [SPATIAL_STATE.md](SPATIAL_STATE.md) |
| `spatial/display_map.py` | [DISPLAY_MAP.md](DISPLAY_MAP.md) |
| `spatial/restore.py` | [RESTORE.md](RESTORE.md) |
| `scripts/asterism-spatial` | [ASTERISM-SPATIAL.md](ASTERISM-SPATIAL.md) |
| `systemd/asterism-spatial.service` | [ASTERISM-SPATIAL.md](ASTERISM-SPATIAL.md) |
| `docs/DASHBOARD_MANAGER.md` | SteamVR Dashboard Manager spatial model |
| `docs/dashboard-state/MAP_RESTORE.md` | Restart persistence proven; direct xf staged |
| `test/test_ownership_boundary.sh` | [_VERIFY_OWNERSHIP_BOUNDARY.md](_VERIFY_OWNERSHIP_BOUNDARY.md) |
| `test/test_dashboard_manager_docs.sh` | [_VERIFY_DASHBOARD_MANAGER_DOCS.md](_VERIFY_DASHBOARD_MANAGER_DOCS.md) |
| `test/test_dashmgr_bridge_docs.sh` | [_VERIFY_DASHMGR_BRIDGE_DOCS.md](_VERIFY_DASHMGR_BRIDGE_DOCS.md) |
| `test/test_dashmgr_queue.py` | [_VERIFY_DASHMGR_QUEUE.md](_VERIFY_DASHMGR_QUEUE.md) |
| `test/test_spatial_persistence.py` | [_VERIFY_SPATIAL_PERSISTENCE.md](_VERIFY_SPATIAL_PERSISTENCE.md) |
| `test/test_fiber_direct_restore.py` | [_VERIFY_FIBER_DIRECT_RESTORE.md](_VERIFY_FIBER_DIRECT_RESTORE.md) |
| `test/test_undocked_render_diag.py` | [_VERIFY_UNDOCKED_RENDER_DIAG.md](_VERIFY_UNDOCKED_RENDER_DIAG.md) |
| `test/test_spatial_lifecycle.py` | [_VERIFY_SPATIAL_LIFECYCLE.md](_VERIFY_SPATIAL_LIFECYCLE.md) |
| `test/_deploy_shell_ws_live.sh` | [_DEPLOY_SHELL_WS_LIVE.md](_DEPLOY_SHELL_WS_LIVE.md) |
| `test/_probe_taskbar.sh` | [_PROBE_TASKBAR.md](_PROBE_TASKBAR.md) (temporary taskbar RE) |
| `test/test_taskbar_order_model.py` | [TEST_TASKBAR_ORDER_MODEL.md](TEST_TASKBAR_ORDER_MODEL.md) |
| `test/_verify_taskbar_order.sh` | [PATCH-STEAMVR-TASKBAR-ORDER.md](PATCH-STEAMVR-TASKBAR-ORDER.md) |
| `pointer/driver/` (`asterism_pointer`) | [DRIVER_ASTERISM_POINTER.md](DRIVER_ASTERISM_POINTER.md) (**legacy** fallback) |
| `test/test_place_wiring.sh` | [_VERIFY_PLACE.md](_VERIFY_PLACE.md) |
| `scripts/asterism-vrsettings.sh` | [ASTERISM-VRSETTINGS.md](ASTERISM-VRSETTINGS.md) |
| `desktop/asterism-apply-outputs.sh` | [ASTERISM-APPLY-OUTPUTS.md](ASTERISM-APPLY-OUTPUTS.md) |
| `desktop-settings/` (GTK3 topology GUI) | [DESKTOP-SETTINGS.md](DESKTOP-SETTINGS.md) |
| `desktop-settings/asterism-desktop-settings` | [ASTERISM-DESKTOP-SETTINGS.md](ASTERISM-DESKTOP-SETTINGS.md) |
| `desktop-settings/asterism-shell-env.sh` | [ASTERISM-SHELL-ENV.md](ASTERISM-SHELL-ENV.md) |
| `test/_verify_desktop_settings.sh` | [_VERIFY_DESKTOP_SETTINGS.md](_VERIFY_DESKTOP_SETTINGS.md) |
| `test/_verify_restart_and_autostart.sh` | [_VERIFY_RESTART_AND_AUTOSTART.md](_VERIFY_RESTART_AND_AUTOSTART.md) |
| `test/_verify_layout_outputs.sh` | [_VERIFY_LAYOUT_OUTPUTS.md](_VERIFY_LAYOUT_OUTPUTS.md) |
| `test/test_vrsettings.py` | [_VERIFY_VRSETTINGS.md](_VERIFY_VRSETTINGS.md) |
| `compatibility/manifest.json` | [MANIFEST.md](MANIFEST.md) |

Architecture: [../../DEVELOPMENT.md](../../DEVELOPMENT.md).
