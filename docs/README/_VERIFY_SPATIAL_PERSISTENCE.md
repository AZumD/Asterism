# _VERIFY_SPATIAL_PERSISTENCE

Script: `test/test_spatial_persistence.py`

## Purpose

No-SteamVR unit tests for:

- probe JSON serializability / shell sanitize path
- spatial-state load/save / atomic write / corrupt handling
- stable display → runtime key mapping
- multi-display state
- non-Asterism overlay rejection for new cmds
- deploy script must not harvest FrameTop credentials

## Run

```bash
python3 test/test_spatial_persistence.py
python3 test/test_dashmgr_queue.py
```
