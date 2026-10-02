# ASTERISM_WS

Module: `dashboard/asterism_ws.py`

## Purpose

Minimal RFC6455 WebSocket helpers for the Asterism systemui bridge. No third-party deps.

Used by `asterism-dashboard.py` to listen on `127.0.0.1:47832` (`ws://localhost:47832` from the browser; CSP allows `ws://localhost:*`).
