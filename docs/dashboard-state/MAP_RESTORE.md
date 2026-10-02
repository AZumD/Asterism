# DASHBOARD Manager map restore — investigation notes

**Date:** 2026-10-02  
**Related:** [DASHBOARD_MANAGER.md](../DASHBOARD_MANAGER.md), commit `1c93c7f`

## Phase 1 — `window.Dashboard` reachability

`componentDidMount` sets `window.Dashboard = this` (React class `Bt`).

Static inspection of `chunk~8012d0c89.js`:

| Reachable from `window.Dashboard`? | Symbol |
|------------------------------------|--------|
| Yes (method) | `onVrCmdDockOverlayRequested` (presentation via mailbox path) |
| **No** | `M.JJ` / `GetFramesWithAssociatedSummonKeys` (module closure) |
| **No** | `frame.docking.m_mapLastRelativeTransformForDockLocation` |
| Other globals | `LegacyDashboardStore` (popover store, not frames), `dashboardActionStore`, `globalActions` |

**Conclusion:** `asterism_shell.js` alone **cannot** resolve `asterism.desktop.app.N` → Frame / remembered transform. A minimal chunk bridge exposing `getFramesForSummonKey` is required (Phase 2).

## Critical Valve behavior — World map vs Dashboard→World

`UndockedOverlay.setInitialTransformForLocation` (chunk):

```text
r = map.get(currentDockLocation)
n = r && (loc == LeftHand || loc == RightHand)
if (loc != World || (prev != LeftHand && prev != RightHand) || (n = true), n)
  setState({ xfTransform: r })   // uses map
else switch(loc):
  World → requestSGTransform(Dashboard dock SGID)  // IGNORES map[World]
```

Therefore:

- Grab-end **does** write `map.set(World, xf)` (confirmed in `endFloatingWindowMoveInternal`).
- **Dashboard → World does NOT consume `map[World]`.**
- **LeftHand/RightHand → World DOES force-consume `map[World]`.**

Preferred same-session proof (`SetDockLocation(Dashboard)` → `SetDockLocation(World)`) is expected to **fail** to restore pose even with a seeded map. Next Valve-native candidate (not yet proven live): seed `map[World]` then `LeftHand` → `World`.

## Phase 2 — minimal bridge (ready, hash-gated)

Script: `scripts/patch-steamvr-dashmgr-bridge.sh`

- Build gate: `1790822802`
- Stock chunk SHA256: `4a33b035cadd9ee3c709247a20c8d6b8f983c9f62b18cb8b328e13383c04378b`
- Exact needle (count must be 1):  
  `window.Dashboard=this,this.m_dashboardThumbnailsChangedEventHandle=`
- Inserts:  
  `window.__ASTERISM_STEAMVR={version:1,yWq:i.yWq,getFramesForSummonKey:(e)=>M.JJ.GetFramesWithAssociatedSummonKeys(e)||[]}`

No docking behavior change. Recovery: `scripts/restore-steamvr-ui.sh`.

## Loopback IPC

`asterism_shell.js` ↔ `http://127.0.0.1:47831/dashmgr/*` ↔ `asterism-dashboard.py`

Commands: `probe`, `list`, `capture`, `seed-world`, `set-presentation`  
CLI: `scripts/asterism-dashmgr`

PNA: vrwebhelper enables `BlockInsecurePrivateNetworkRequests`; HTTP responses include `Access-Control-Allow-Private-Network: true`.

## Live proof status

Requires writing `/opt/steamvr/...` (sudo). Stage payload:

```bash
bash test/_stage_dashmgr_patch.sh
sudo /tmp/asterism-dashmgr-patch-out/APPLY.sh
rm -rf ~/.cache/SteamVR/htmlcache
systemctl --user restart steamvr.service asterism-dashboard.service
```

Until applied: Phase 3–6 capture/restore not executable from this agent session.

### Staged hashes (Frame `/tmp/asterism-dashmgr-patch-out`, 2026-10-02)

| File | SHA256 |
|------|--------|
| stock chunk (live) | `4a33b035cadd9ee3c709247a20c8d6b8f983c9f62b18cb8b328e13383c04378b` |
| staged bridged chunk | `272c1e40f75bafe28a7108485295681ffdac2a322a6a10f3e2d35278d596dfd9` |
| staged systemui.html | `b28803f21ac998906f85ab36e6b0dd75ffd43b2d1ba4fc5dd46ef7bbd3d627ef` |
| staged asterism_shell.js | `4d006bece0214a955bdcd4f363dfc45850f3934e202e49f1ffa8fd6a7faccf42` |

## Transport update (2026-10-02 evening)

HTTP poll to `127.0.0.1:47831` is **CSP-blocked**. systemui now uses:

`ws://localhost:47832` → minimal RFC6455 server in `dashboard/asterism_ws.py`

CLI path unchanged: HTTP enqueue → FIFO → WebSocket → shell.

### Shell-only live stage (`/tmp/asterism-shell-ws-stage`)

| File | SHA256 |
|------|--------|
| live bridged chunk (must stay) | `272c1e40f75bafe28a7108485295681ffdac2a322a6a10f3e2d35278d596dfd9` |
| new `asterism_shell.js` | `102fadb99395482467dcd89cbb01c0217adb1d7654e7bebf3b30eee6f8b303cb` |
| new `systemui.html` (contenthash=asterism3) | `710a96000789c73bafcf55ac40a8dad3ef9150c4361e47e2ae1529618af9eac5` |

Apply (sudo required; chunk untouched):

```bash
bash ~/asterism/test/_deploy_shell_ws_live.sh
# or manually:
# sudo install -m 0644 /tmp/asterism-shell-ws-stage/asterism_shell.js /opt/steamvr/resources/webinterface/dashboard/
# sudo install -m 0644 /tmp/asterism-shell-ws-stage/systemui.html /opt/steamvr/resources/webinterface/dashboard/
# rm -rf ~/.cache/SteamVR/htmlcache && systemctl --user restart steamvr.service
```
