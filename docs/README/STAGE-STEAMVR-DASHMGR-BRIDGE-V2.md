# STAGE-STEAMVR-DASHMGR-BRIDGE-V2

Script: `scripts/stage-steamvr-dashmgr-bridge-v2.sh`

## Purpose

Stage (not auto-apply) chunk bridge **v2** on top of live v1:

Base SHA256: `272c1e40f75bafe28a7108485295681ffdac2a322a6a10f3e2d35278d596dfd9`  
Build: `1790822802`

Adds:

- UndockedOverlay `_uo[frameID]` register on mount / clear on unmount
- `applyWorldTransformForSummonKey(overlayKey, transform)` — map[World] + `setState({xfTransform})`
- `getLiveWorldTransformForSummonKey` — read-only live pose snapshot

Asterism overlay keys only. No eval / arbitrary mutation API.

## Usage (Frame)

```bash
bash scripts/stage-steamvr-dashmgr-bridge-v2.sh
# review /tmp/asterism-dashmgr-bridge-v2/HASHES.txt
# sudo /tmp/asterism-dashmgr-bridge-v2/APPLY.sh   # manual only
```

Direct restore remains **unproven** until headset-validated.
