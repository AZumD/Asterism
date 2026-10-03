#!/usr/bin/env python3
"""Dashmgr FIFO + WebSocket transport tests (no SteamVR)."""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import socket
import struct
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH_PATH = ROOT / "dashboard" / "asterism-dashboard.py"
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _load_ad():
    spec = importlib.util.spec_from_file_location("asterism_dashboard", DASH_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ad = _load_ad()


def _ws_client_connect(host: str, port: int) -> socket.socket:
    key = base64.b64encode(b"asterism-test-key-12").decode()
    req = (
        f"GET / HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n"
        f"\r\n"
    ).encode()
    sock = socket.create_connection((host, port), timeout=5)
    sock.sendall(req)
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(1024)
        if not chunk:
            raise RuntimeError("no handshake response")
        data += chunk
    assert b"101" in data.split(b"\r\n", 1)[0], data[:200]
    expect = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
    assert expect.encode() in data
    return sock


def _ws_send_text(sock: socket.socket, text: str) -> None:
    payload = text.encode("utf-8")
    n = len(payload)
    header = bytearray([0x81])
    mask = b"\x01\x02\x03\x04"
    if n < 126:
        header.append(0x80 | n)
    elif n <= 0xFFFF:
        header.append(0x80 | 126)
        header.extend(struct.pack("!H", n))
    else:
        header.append(0x80 | 127)
        header.extend(struct.pack("!Q", n))
    header.extend(mask)
    masked = bytes(payload[i] ^ mask[i % 4] for i in range(n))
    sock.sendall(bytes(header) + masked)


def _ws_recv_text(sock: socket.socket, timeout: float = 5.0) -> str:
    sock.settimeout(timeout)
    header = sock.recv(2)
    if len(header) < 2:
        raise RuntimeError("short frame")
    b1 = header[1]
    assert (b1 & 0x80) == 0  # server unmasked
    length = b1 & 0x7F
    if length == 126:
        length = struct.unpack("!H", sock.recv(2))[0]
    elif length == 127:
        length = struct.unpack("!Q", sock.recv(8))[0]
    payload = b""
    while len(payload) < length:
        payload += sock.recv(length - len(payload))
    return payload.decode("utf-8")


def test_queue_fifo_and_reject() -> None:
    ad.dashmgr_reset_for_tests()
    assert ad.dashmgr_poll() == {}
    assert ad.dashmgr_queue_len() == 0

    a = ad.dashmgr_enqueue("list")
    b = ad.dashmgr_enqueue("probe")
    c = ad.dashmgr_enqueue("capture", overlay_key="asterism.desktop.app.2")
    assert a["ok"] and b["ok"] and c["ok"]
    assert ad.dashmgr_queue_len() == 3

    p1 = ad.dashmgr_poll()
    p2 = ad.dashmgr_poll()
    p3 = ad.dashmgr_poll()
    assert p1["id"] == a["id"] and p1["cmd"] == "list"
    assert p2["id"] == b["id"] and p2["cmd"] == "probe"
    assert p3["id"] == c["id"] and p3["cmd"] == "capture"
    assert ad.dashmgr_poll() == {}

    bad = ad.dashmgr_enqueue("nope")
    assert bad["ok"] is False
    for cmd in (
        "capture",
        "seed-world",
        "set-presentation",
        "direct-restore",
        "restore-via-hand",
        "get-live-world",
        "inspect-undocked-render",
    ):
        rej = ad.dashmgr_enqueue(cmd, overlay_key="steam.overlay.other")
        assert rej["ok"] is False
        assert "asterism.desktop" in rej["error"]
    force = ad.dashmgr_enqueue("force-dashboard-render")
    assert force["ok"] is True
    print("OK fifo+reject")


def test_ws_command_result_roundtrip() -> None:
    ad.dashmgr_reset_for_tests()
    # Bind ephemeral WS port for isolation
    ad.WS_PORT = 0
    listen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listen.bind(("127.0.0.1", 0))
    port = listen.getsockname()[1]
    listen.listen(2)
    ad.WS_PORT = port

    # Manually start accept+dispatch using module helpers with our listen socket
    t_accept = threading.Thread(
        target=ad._dashmgr_ws_accept_loop, args=(listen,), daemon=True
    )
    t_disp = threading.Thread(target=ad._dashmgr_ws_dispatcher, daemon=True)
    # Ensure dispatcher sees not-shutdown
    ad._shutdown = False
    t_accept.start()
    t_disp.start()

    sock = _ws_client_connect("127.0.0.1", port)
    _ws_send_text(sock, json.dumps({"type": "hello", "client": "test", "version": 1}))
    time.sleep(0.2)
    assert ad.dashmgr_ws_connected()

    q = ad.dashmgr_enqueue("list")
    assert q["ok"]
    frame = json.loads(_ws_recv_text(sock, timeout=5))
    assert frame["type"] == "command"
    assert frame["cmd"] == "list"
    assert frame["id"] == q["id"]

    _ws_send_text(
        sock,
        json.dumps(
            {
                "type": "result",
                "id": q["id"],
                "result": {"ok": True, "frames": [{"overlay_key": "asterism.desktop.app.2"}]},
            }
        ),
    )
    got = ad.dashmgr_get_result(q["id"], wait=3.0)
    assert got["ok"] is True, got
    assert got["result"]["frames"][0]["overlay_key"] == "asterism.desktop.app.2"

    # FIFO over WS
    ids = []
    for cmd in ("probe", "list", "list"):
        ids.append(ad.dashmgr_enqueue(cmd)["id"])
    for expect_cmd, cid in zip(("probe", "list", "list"), ids):
        fr = json.loads(_ws_recv_text(sock, timeout=5))
        assert fr["cmd"] == expect_cmd and fr["id"] == cid
        _ws_send_text(
            sock, json.dumps({"type": "result", "id": cid, "result": {"ok": True, "cmd": expect_cmd}})
        )
        assert ad.dashmgr_get_result(cid, wait=2)["result"]["cmd"] == expect_cmd

    # reconnect
    sock.close()
    time.sleep(0.3)
    assert not ad.dashmgr_ws_connected()
    sock2 = _ws_client_connect("127.0.0.1", port)
    _ws_send_text(sock2, json.dumps({"type": "hello", "client": "test", "version": 1}))
    time.sleep(0.2)
    assert ad.dashmgr_ws_connected()
    q2 = ad.dashmgr_enqueue("probe")
    fr2 = json.loads(_ws_recv_text(sock2, timeout=5))
    assert fr2["id"] == q2["id"]
    _ws_send_text(
        sock2, json.dumps({"type": "result", "id": q2["id"], "result": {"ok": True, "probe": {}}})
    )
    assert ad.dashmgr_get_result(q2["id"], wait=2)["ok"]

    sock2.close()
    listen.close()
    print("OK websocket")


def test_http_enqueue_still_works() -> None:
    ad.dashmgr_reset_for_tests()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), ad.HttpHandler)
    host, port = srv.server_address
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://{host}:{port}"

    def http_json(method: str, path: str, body: dict | None = None) -> dict:
        data = None if body is None else json.dumps(body).encode()
        headers = {"Content-Type": "application/json"} if body is not None else {}
        req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())

    try:
        enq = http_json("POST", "/dashmgr/enqueue", {"cmd": "list"})
        assert enq["ok"]
        polled = http_json("GET", "/dashmgr/poll")
        assert polled["id"] == enq["id"]
        assert http_json("GET", "/dashmgr/poll") == {}
        print("OK http enqueue")
    finally:
        srv.shutdown()
        srv.server_close()


def main() -> int:
    test_queue_fifo_and_reject()
    test_ws_command_result_roundtrip()
    test_http_enqueue_still_works()
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
