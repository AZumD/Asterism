# RECOVER-ASTERISM

Script: `scripts/recover-asterism.sh`

## Purpose

SSH-safe emergency recovery: disable Asterism services, stop processes, restore UI only if a Phase C patch marker exists, clear Asterism runtime, optionally restart SteamVR.

## Usage

```
scripts/recover-asterism.sh --dry-run --yes --no-restart
scripts/recover-asterism.sh --yes --no-restart
scripts/recover-asterism.sh --yes
```

## Notes

- Does not touch FrameTop, reboot, reset the headset, or remove unrelated drivers.
- Prefer `--no-restart` during development.
