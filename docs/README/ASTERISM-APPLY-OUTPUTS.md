# ASTERISM-APPLY-OUTPUTS

Script: `desktop/asterism-apply-outputs.sh`

## Purpose

After nested Plasma is up, run `kscreen-doctor` so each KWin output sits edge-to-edge (`0,0`, `W,0`, …) with no horizontal overlap. Fixes the “second display shows part of the first” bleed when KWin leaves a stale origin (e.g. `1280,0` after a 1280→1920 resolution change).
