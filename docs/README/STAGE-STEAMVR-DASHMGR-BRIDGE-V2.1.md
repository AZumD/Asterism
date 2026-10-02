# STAGE-STEAMVR-DASHMGR-BRIDGE-V2.1

Script: `scripts/stage-steamvr-dashmgr-bridge-v2.1.sh`

## Purpose

**Contingency only.** Prefer shell React-fiber direct-restore on chunk bridge v1.

Stages a narrower Valve patch than broken v2 (`83a3bcbf…`):

- Asterism-only `_uo` registration (summon key prefix `asterism.desktop`)
- unregister only when `registry[frameID] === this`
- purpose-built apply/get helpers

Do **not** apply unless live fiber lookup fails.
