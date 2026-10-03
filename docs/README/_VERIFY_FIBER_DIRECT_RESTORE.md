# _VERIFY_FIBER_DIRECT_RESTORE

Script: `test/test_fiber_direct_restore.py`

## Purpose

No-SteamVR tests for:

- bounded React fiber walk / cycles / frameID match
- shell direct-restore fiber markers
- broken v2 / contingency v2.1 stage script checks
- deploy readonly trap ordering
- `.gitattributes` LF policy
- git index executable modes (`100755`) for systemd entrypoints

Case A/B diagnostics: `test/test_undocked_render_diag.py` (+ `_VERIFY_UNDOCKED_RENDER_DIAG.md`).

## Run

```bash
python3 test/test_fiber_direct_restore.py
python3 test/test_spatial_persistence.py
python3 test/test_undocked_render_diag.py
```
