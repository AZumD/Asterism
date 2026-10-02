# PATCH-STEAMVR-DASHMGR-BRIDGE

Script: `scripts/patch-steamvr-dashmgr-bridge.sh`

## Purpose

Hash-gated, exact-string minimal exposure of Frame lookup for Asterism:

`window.__ASTERISM_STEAMVR = { yWq, getFramesForSummonKey }` (bridge **v1**, live)

Does not change Valve docking behavior. Restart World-pose persistence via map
seed + LeftHand→World is **proven**. For direct `xfTransform` restore (v2), see
[STAGE-STEAMVR-DASHMGR-BRIDGE-V2.md](STAGE-STEAMVR-DASHMGR-BRIDGE-V2.md).

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
