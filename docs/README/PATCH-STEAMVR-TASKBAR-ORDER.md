# PATCH-STEAMVR-TASKBAR-ORDER

Script: `scripts/patch-steamvr-taskbar-order.sh`

## Purpose

**Reversible PoC:** reorder SystemUI dashboard-bar tab **publish** order so
Asterism display overlays (`icon.overlay` starting with
`asterism.desktop.app.`) sit immediately after Steam and before normal
appid tabs.

Does **not** recreate buttons, change click handlers, visibility, `+`, or
GamepadUI `Nt()`. GamepadUI keeps Steam in the left bookend and preserves
published order for all other tabs.

Layers on the known-safe dashmgr bridge **v1** chunk. Does not regenerate or
remove `__ASTERISM_STEAMVR`.

## Conceptual buckets (`Dt` / `Pt`)

| Order | Predicate |
|------:|-----------|
| 0 | `icon.enum == 14` (Steam) |
| 1 | `icon.overlay` starts with `asterism.desktop.app.` |
| 2 | `icon.enum == 33` (appid) |
| 3 | other `icon.overlay` (excludes Asterism) |
| 4 | `icon.enum == 15` (Display) |
| 5 | `icon.hwnd` |

Within a bucket: existing `tab_id` ascending.

## Hashes (build `1790822802`)

| | SHA256 |
|--|--------|
| Required **input** (bridged v1) | `272c1e40f75bafe28a7108485295681ffdac2a322a6a10f3e2d35278d596dfd9` |
| Expected **output** | `047c1d4ef8110849da024ed34948370dc92f572bc06e4c1de3f5b81fc4bccb8e` |

Needles: `patches/taskbar-order/NEEDLES.txt`, `HASHES.txt`.

## Usage (Frame)

```bash
# Dry-run (no write)
scripts/patch-steamvr-taskbar-order.sh --dry-run

# Apply (sudo / steamos-readonly)
scripts/patch-steamvr-taskbar-order.sh --yes

# Status
scripts/patch-steamvr-taskbar-order.sh --status

# Rollback PoC only (keeps bridge v1)
scripts/patch-steamvr-taskbar-order.sh --unpatch --yes
```

After apply: clear SteamVR htmlcache and restart SteamVR, then:

```bash
scripts/asterism-dashmgr probe
scripts/asterism-dashmgr probe-taskbar
bash test/_verify_taskbar_order.sh
```

## Safety

- Exact input SHA gate (bridged v1 only)
- Exact `OLD_DT` / `NEW_DT` single-occurrence replace
- Verifies bridge v1 needle + `version:1` before and after
- Chunk-only backup under `~/.local/share/asterism/backups/taskbar-order-*`
- `steamos-readonly` re-enabled on exit
- Does not touch `systemui.html` or Steam `steamui`

## Rollback

```bash
scripts/patch-steamvr-taskbar-order.sh --unpatch --yes
# or restore the script’s backup:
# sudo install -m 0644 ~/.local/share/asterism/backups/taskbar-order-*/chunk~8012d0c89.js \
#   /opt/steamvr/resources/webinterface/dashboard/chunk~8012d0c89.js
```

## Related

- Offline model: [TEST_TASKBAR_ORDER_MODEL.md](TEST_TASKBAR_ORDER_MODEL.md)
- Live probe: [_PROBE_TASKBAR.md](_PROBE_TASKBAR.md)
- Bridge (must remain): [PATCH-STEAMVR-DASHMGR-BRIDGE.md](PATCH-STEAMVR-DASHMGR-BRIDGE.md)
