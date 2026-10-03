# TEST_TASKBAR_ORDER_MODEL

Script: `test/test_taskbar_order_model.py`

## Purpose

Offline unit model of SteamVR dashboard-bar tab **publish sort** (`Dt`/`Pt` in
`chunk~8012d0c89.js`) and GamepadUI **left bookend vs main tabs** split
(`Nt()` in `steamui/chunk~2dcc5aaf7.js`).

Covers stock Valve order vs Asterism **taskbar-order PoC** buckets
(`asterism.desktop.app.*` after Steam, before appid 33). See
[PATCH-STEAMVR-TASKBAR-ORDER.md](PATCH-STEAMVR-TASKBAR-ORDER.md).

## Usage

```bash
python3 test/test_taskbar_order_model.py
```
