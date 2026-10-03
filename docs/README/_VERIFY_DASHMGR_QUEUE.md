# _VERIFY_DASHMGR_QUEUE

Script: `test/test_dashmgr_queue.py`

## Purpose

Exercise dashmgr FIFO queue + minimal WebSocket transport (no SteamVR):

- empty poll / FIFO A→B→C
- reject unsupported cmds and non-`asterism.desktop*` keys
  (including `direct-restore` / `restore-via-hand` / `get-live-world` /
  `inspect-undocked-render`; `force-dashboard-render` needs no overlay key)
- simulated WS client: hello → command → result → waiter
- reconnect after disconnect
- HTTP enqueue/poll still works for CLI/debug
- no silent queue overwrite (FIFO)

## Run

```bash
python3 test/test_dashmgr_queue.py
```
