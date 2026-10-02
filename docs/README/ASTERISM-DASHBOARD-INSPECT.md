# ASTERISM-DASHBOARD-INSPECT

Script: `scripts/asterism-dashboard-inspect`

## Purpose

Read-only diagnostic for Asterism display ↔ Gamescope overlay mapping and
Dashboard Manager architecture summary.

Live `presentation` / `xfTransform` / `frameID` fields are **null** until a
systemui bridge exists — those values live only inside SteamVR dashboard JS.

## Usage

```
asterism-dashboard-inspect
asterism-dashboard-inspect --architecture
```

See [../DASHBOARD_MANAGER.md](../DASHBOARD_MANAGER.md).
