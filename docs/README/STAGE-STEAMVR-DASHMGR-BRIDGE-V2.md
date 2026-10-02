# STAGE-STEAMVR-DASHMGR-BRIDGE-V2

Script: `scripts/stage-steamvr-dashmgr-bridge-v2.sh`

## Purpose

**BROKEN — do not apply.** Staged chunk bridge **v2** caused a giant black
rectangle on SteamVR load (SHA `83a3bcbf…`). See
[BRIDGE_V2_BLACK_RECTANGLE.md](../dashboard-state/BRIDGE_V2_BLACK_RECTANGLE.md).

Prefer shell React-fiber direct-restore on v1. Contingency: v2.1.

Historical purpose was staging on base SHA256
`272c1e40f75bafe28a7108485295681ffdac2a322a6a10f3e2d35278d596dfd9`:

- UndockedOverlay `_uo[frameID]` register on mount / clear on unmount
- `applyWorldTransformForSummonKey` / `getLiveWorldTransformForSummonKey`

`APPLY.sh` now **refuses** (exit 3). Forensic re-stage only.
