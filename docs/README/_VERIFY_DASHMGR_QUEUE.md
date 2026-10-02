# _VERIFY_DASHMGR_QUEUE

Script: `test/test_dashmgr_queue.py`

## Purpose

Exercise the real dashmgr queue API in `dashboard/asterism-dashboard.py` (no SteamVR):

- empty poll
- enqueue → poll → empty poll
- second enqueue after drain
- store_result / get_result round-trip
- unsupported cmd rejected
- non-`asterism.desktop*` overlay keys rejected
- localhost HTTP: POST enqueue, GET poll, POST result, GET result/:id

## Run

```bash
python3 test/test_dashmgr_queue.py
```
