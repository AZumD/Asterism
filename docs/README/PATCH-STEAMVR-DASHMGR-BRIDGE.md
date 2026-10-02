# PATCH-STEAMVR-DASHMGR-BRIDGE

Script: `scripts/patch-steamvr-dashmgr-bridge.sh`

## Purpose

Hash-gated, exact-string minimal exposure of Frame lookup for Asterism:

`window.__ASTERISM_STEAMVR = { yWq, getFramesForSummonKey }`

Does not change Valve docking behavior. Use only after Phase 1 proves `window.Dashboard` cannot resolve Frames.

## Usage

```
scripts/patch-steamvr-dashmgr-bridge.sh --dry-run
scripts/patch-steamvr-dashmgr-bridge.sh --yes
scripts/patch-steamvr-dashmgr-bridge.sh --status
scripts/patch-steamvr-dashmgr-bridge.sh --unpatch --yes
```

## Safety

- SteamVR build must be `1790822802`
- Stock chunk SHA256 must match compatibility manifest
- Needle must appear exactly once
- Fresh `backup-steamvr-ui.sh` before apply
- Restore via `restore-steamvr-ui.sh`
