#!/usr/bin/env python3
"""Real dashmgr queue transport tests (no SteamVR required)."""
from __future__ import annotations

import importlib.util
import json
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH_PATH = ROOT / "dashboard" / "asterism-dashboard.py"


def _load_ad():
    spec = importlib.util.spec_from_file_location("asterism_dashboard", DASH_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ad = _load_ad()


def _reset_queue() -> None:
    with ad._DASHMGR_LOCK:
        ad._DASHMGR_PENDING = None
        ad._DASHMGR_RESULTS.clear()


def test_queue_functions() -> None:
    _reset_queue()
    assert ad.dashmgr_poll() == {}

    q = ad.dashmgr_enqueue("list")
    assert q.get("ok") is True, q
    assert q.get("id"), q
    cid = q["id"]
    assert q["queued"]["cmd"] == "list"
    assert q["queued"]["id"] == cid

    polled = ad.dashmgr_poll()
    assert polled.get("id") == cid, polled
    assert polled.get("cmd") == "list", polled

    assert ad.dashmgr_poll() == {}

    q2 = ad.dashmgr_enqueue("probe")
    assert q2.get("ok") is True, q2
    p2 = ad.dashmgr_poll()
    assert p2.get("id") == q2["id"]
    assert p2.get("cmd") == "probe"
    assert ad.dashmgr_poll() == {}

    stored = ad.dashmgr_store_result({"id": cid, "result": {"ok": True, "frames": []}})
    assert stored.get("ok") is True, stored
    got = ad.dashmgr_get_result(cid, wait=0.0)
    assert got.get("ok") is True, got
    assert got.get("id") == cid
    assert got.get("result") == {"ok": True, "frames": []}

    bad = ad.dashmgr_enqueue("not-a-cmd")
    assert bad.get("ok") is False
    assert "unsupported" in str(bad.get("error", "")).lower()

    for cmd in ("capture", "seed-world", "set-presentation"):
        rej = ad.dashmgr_enqueue(cmd, overlay_key="steam.overlay.other")
        assert rej.get("ok") is False, (cmd, rej)
        assert "asterism.desktop" in str(rej.get("error", ""))

    ok_cap = ad.dashmgr_enqueue("capture", overlay_key="asterism.desktop.app.2")
    assert ok_cap.get("ok") is True, ok_cap
    assert ad.dashmgr_poll()["overlay_key"] == "asterism.desktop.app.2"
    print("OK functions")


def test_http_roundtrip() -> None:
    _reset_queue()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), ad.HttpHandler)
    host, port = srv.server_address
    t = threading.Thread(target=srv.serve_forever, name="dashmgr-test-http", daemon=True)
    t.start()
    base = f"http://{host}:{port}"

    def http_json(method: str, path: str, body: dict | None = None) -> dict:
        data = None if body is None else json.dumps(body).encode()
        headers = {"Content-Type": "application/json"} if body is not None else {}
        req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())

    try:
        enq = http_json("POST", "/dashmgr/enqueue", {"cmd": "list"})
        assert enq.get("ok") is True, enq
        cid = enq["id"]
        polled = http_json("GET", "/dashmgr/poll")
        assert polled.get("id") == cid, polled
        assert polled.get("cmd") == "list"
        empty = http_json("GET", "/dashmgr/poll")
        assert empty == {}, empty
        stored = http_json(
            "POST",
            "/dashmgr/result",
            {"id": cid, "result": {"ok": True, "via": "http-test"}},
        )
        assert stored.get("ok") is True, stored
        got = http_json("GET", f"/dashmgr/result/{cid}")
        assert got.get("ok") is True, got
        assert got.get("result", {}).get("via") == "http-test"
        print("OK http")
    finally:
        srv.shutdown()
        srv.server_close()


def main() -> int:
    test_queue_functions()
    test_http_roundtrip()
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
