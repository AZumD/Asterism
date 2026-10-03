# _VERIFY_SPATIAL_LIFECYCLE

Script: `test/test_spatial_lifecycle.py`

## Purpose

No-SteamVR tests for automatic spatial persistence:

- v1→v2 migration
- snapshot prefers get-live-world
- World readiness uses inspect-undocked-instance (weak); direct-restore may init null xf; verify get-live-world
- clear-just-floated after pre-hide verify, before hide; post-hide verify must match P
- peer-safe snapshot failure
- World restore presentation-first
- Dashboard/Theater restore
- no hand fallback on startup
- session/layout-apply race removed
- systemd unit ordering / ExecStop timeout
- seed-presentation-transform validation

## Run

```bash
python3 test/test_spatial_lifecycle.py
python3 test/test_spatial_persistence.py
python3 test/test_fiber_direct_restore.py
```
