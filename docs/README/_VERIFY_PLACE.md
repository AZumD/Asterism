# _VERIFY_PLACE

Script: `test/test_place_wiring.sh`

Checks that `asterism-place` and `driver_asterism_pointer.so` exist after build,
and that `layout.place_world` reports a clean error when the binary is missing.
Live VR place is exercised manually after `pointer/driver/install.sh install`
and a SteamVR restart.
