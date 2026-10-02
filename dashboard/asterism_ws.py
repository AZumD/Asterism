"""Minimal RFC6455 WebSocket server helpers for Asterism loopback bridge.

Only what we need: localhost text frames, one client. No third-party deps.
"""
from __future__ import annotations

import base64
import hashlib
import socket
import struct
from typing import Optional

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def ws_accept_key(sec_key: str) -> str:
    digest = hashlib.sha1((sec_key + WS_GUID).encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii")


def ws_handshake_response(sec_key: str) -> bytes:
    accept = ws_accept_key(sec_key)
    return (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept}\r\n"
        "\r\n"
    ).encode("ascii")


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("websocket closed")
        buf += chunk
    return buf


def ws_recv_text(sock: socket.socket) -> Optional[str]:
    """Receive one text frame. Returns None on close. Raises on protocol errors."""
    while True:
        header = _recv_exact(sock, 2)
        b0, b1 = header[0], header[1]
        opcode = b0 & 0x0F
        masked = (b1 & 0x80) != 0
        length = b1 & 0x7F
        if length == 126:
            length = struct.unpack("!H", _recv_exact(sock, 2))[0]
        elif length == 127:
            length = struct.unpack("!Q", _recv_exact(sock, 8))[0]
        mask = _recv_exact(sock, 4) if masked else b""
        payload = _recv_exact(sock, length) if length else b""
        if masked:
            payload = bytes(payload[i] ^ mask[i % 4] for i in range(len(payload)))
        if opcode == 0x8:  # close
            return None
        if opcode == 0x9:  # ping -> pong
            ws_send_frame(sock, payload, opcode=0xA)
            continue
        if opcode == 0xA:  # pong
            continue
        if opcode == 0x1:  # text
            return payload.decode("utf-8")
        if opcode == 0x2:  # binary — ignore
            continue
        # continuation / unknown: ignore
        continue


def ws_send_frame(sock: socket.socket, payload: bytes, *, opcode: int = 0x1) -> None:
    """Send an unmasked server frame."""
    header = bytearray()
    header.append(0x80 | (opcode & 0x0F))
    n = len(payload)
    if n < 126:
        header.append(n)
    elif n <= 0xFFFF:
        header.append(126)
        header.extend(struct.pack("!H", n))
    else:
        header.append(127)
        header.extend(struct.pack("!Q", n))
    sock.sendall(bytes(header) + payload)


def ws_send_text(sock: socket.socket, text: str) -> None:
    ws_send_frame(sock, text.encode("utf-8"), opcode=0x1)


def ws_send_close(sock: socket.socket) -> None:
    try:
        ws_send_frame(sock, b"", opcode=0x8)
    except OSError:
        pass


def parse_http_upgrade(request: bytes) -> Optional[str]:
    """Return Sec-WebSocket-Key if this is a valid Upgrade request."""
    try:
        text = request.decode("iso-8859-1")
    except UnicodeDecodeError:
        return None
    if "\r\n\r\n" not in text:
        return None
    lines = text.split("\r\n")
    headers = {}
    for line in lines[1:]:
        if not line or ":" not in line:
            continue
        k, v = line.split(":", 1)
        headers[k.strip().lower()] = v.strip()
    if headers.get("upgrade", "").lower() != "websocket":
        return None
    if "upgrade" not in headers.get("connection", "").lower():
        return None
    key = headers.get("sec-websocket-key")
    return key or None
