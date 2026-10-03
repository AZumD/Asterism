#!/usr/bin/env python3
"""Asterism dashboard control plane.

Desktop is infrastructure for the SteamVR session:
  - started when SteamVR is healthy
  - kept alive while SteamVR runs (including while hidden)
  - show/hide/toggle change visibility/focus only
  - stop-desktop is administrative/recovery only
"""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

_DASH_DIR = Path(__file__).resolve().parent
if str(_DASH_DIR) not in sys.path:
    sys.path.insert(0, str(_DASH_DIR))
from asterism_ws import (  # noqa: E402
    parse_http_upgrade,
    ws_handshake_response,
    ws_recv_text,
    ws_send_close,
    ws_send_text,
)

ROOT = Path(os.environ.get("ASTERISM_ROOT", Path(__file__).resolve().parents[1]))
STATE = Path(os.environ.get("ASTERISM_STATE_DIR", Path.home() / ".local/state/asterism"))
LOG_DIR = STATE / "logs"
RUNTIME = Path(
    os.environ.get(
        "ASTERISM_RUNTIME_DIR",
        Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "asterism",
    )
)
SOCK = Path(os.environ.get("ASTERISM_IPC_SOCK", RUNTIME / "control.sock"))
HTTP_HOST = os.environ.get("ASTERISM_HTTP_HOST", "127.0.0.1")
HTTP_PORT = int(os.environ.get("ASTERISM_HTTP_PORT", "47831"))
WS_HOST = os.environ.get("ASTERISM_WS_HOST", "127.0.0.1")
WS_PORT = int(os.environ.get("ASTERISM_WS_PORT", "47832"))
STEAMVR = Path(os.environ.get("STEAMVR_ROOT", "/opt/steamvr"))
VRCMD = Path(os.environ.get("VRCMD", STEAMVR / "bin/linuxarm64/vrcmd"))
OVERLAY_KEY = "asterism.desktop"
OVERLAY_KEY_PREFIX = "asterism.desktop"
LOG = LOG_DIR / "dashboard.log"

# Crash recovery rate limit
RESTART_WINDOW_SEC = 120
RESTART_MAX = 3

LOG_DIR.mkdir(parents=True, exist_ok=True)
RUNTIME.mkdir(parents=True, exist_ok=True)

_shutdown = False
_restart_times: list[float] = []
_steamvr_was_alive = False


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def env_for_vr() -> dict:
    e = os.environ.copy()
    lib = str(STEAMVR / "bin/linuxarm64")
    e["LD_LIBRARY_PATH"] = lib + ((":" + e["LD_LIBRARY_PATH"]) if e.get("LD_LIBRARY_PATH") else "")
    e.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    e.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path={e['XDG_RUNTIME_DIR']}/bus")
    return e


def vrcmd(*args: str) -> subprocess.CompletedProcess:
    if not VRCMD.is_file():
        raise FileNotFoundError(str(VRCMD))
    return subprocess.run(
        [str(VRCMD), *args],
        capture_output=True,
        text=True,
        env=env_for_vr(),
        timeout=15,
        check=False,
    )


def systemctl_user(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["systemctl", "--user", *args],
        capture_output=True,
        text=True,
        env=env_for_vr(),
        timeout=60,
        check=False,
    )


def steamvr_alive() -> bool:
    def running(name: str) -> bool:
        return subprocess.run(["pgrep", "-x", name], capture_output=True).returncode == 0

    return running("vrserver") and running("vrcompositor")


def overlays_text() -> str:
    if not steamvr_alive():
        return ""
    try:
        return (vrcmd("--overlays").stdout or "").replace("\r", "")
    except Exception as e:  # noqa: BLE001
        log(f"overlays error: {e}")
        return ""


def overlay_listed() -> bool:
    return OVERLAY_KEY_PREFIX in overlays_text()


def desktop_visible() -> bool:
    """True if an Asterism dashboard overlay line is present and not marked not_visible."""
    for line in overlays_text().splitlines():
        if OVERLAY_KEY_PREFIX not in line:
            continue
        if "VROverlayType_Dashboard_Main" not in line and "Dashboard_Main" not in line:
            continue
        if "not_visible" in line:
            return False
        if " visible " in f" {line} " or line.endswith(" visible") or " visible VROverlay" in line:
            return True
        # vrcmd format: "... visible VROverlayType_..." or "... not_visible ..."
        if " visible " in line:
            return True
    return False


def desktop_running() -> bool:
    r = systemctl_user("is-active", "asterism-desktop.service")
    if r.stdout.strip() == "active":
        return True
    return gamescope_running()


def gamescope_running() -> bool:
    r = subprocess.run(
        ["pgrep", "-f", f"[g]amescope .*--vr-overlay-key {OVERLAY_KEY}"],
        capture_output=True,
    )
    return r.returncode == 0


def _can_restart() -> bool:
    now = time.time()
    global _restart_times
    _restart_times = [t for t in _restart_times if now - t < RESTART_WINDOW_SEC]
    return len(_restart_times) < RESTART_MAX


def ensure_desktop(*, reason: str = "ensure") -> str:
    """Start desktop if missing. Used at session start and crash recovery — not by show()."""
    if not steamvr_alive():
        msg = "error: SteamVR not running; refusing desktop start"
        log(msg)
        return msg
    unit_active = systemctl_user("is-active", "asterism-desktop.service").stdout.strip() == "active"
    gs = gamescope_running()
    if unit_active and gs:
        msg = f"desktop already running ({reason})"
        log(msg)
        return msg
    if unit_active and not gs:
        log(f"desktop unit active without gamescope ({reason}); restarting")
        systemctl_user("reset-failed", "asterism-desktop.service")
        systemctl_user("restart", "asterism-desktop.service")
    else:
        if reason == "crash-recovery" and not _can_restart():
            log("ERROR: desktop crash restart rate limit exceeded; not restarting")
            return "error: desktop restart rate-limited"
        log(f"starting asterism-desktop.service ({reason})")
        if reason == "crash-recovery":
            _restart_times.append(time.time())
        systemctl_user("reset-failed", "asterism-desktop.service")
        r = systemctl_user("start", "asterism-desktop.service")
        if r.returncode != 0:
            msg = f"error: start desktop failed: {r.stderr.strip() or r.stdout.strip()}"
            log(msg)
            return msg
    for _ in range(80):
        if gamescope_running() or overlay_listed():
            break
        time.sleep(0.25)
    if not gamescope_running() and not overlay_listed():
        msg = f"error: desktop start timed out ({reason})"
        log(msg)
        return msg
    msg = f"desktop started ({reason})"
    log(msg)
    return msg


def restart_desktop(*, reason: str = "restart") -> str:
    """Stop then start asterism-desktop on the real user bus (FrameTop desktops restart)."""
    if not steamvr_alive():
        return "error: SteamVR not running; refusing desktop restart"
    log(f"restarting asterism-desktop.service ({reason})")
    stop_desktop(reason=f"restart:{reason}")
    time.sleep(2)
    systemctl_user("reset-failed", "asterism-desktop.service")
    r = systemctl_user("start", "asterism-desktop.service")
    if r.returncode != 0:
        return f"error: restart start failed: {r.stderr.strip() or r.stdout.strip()}"
    for _ in range(80):
        if gamescope_running() or overlay_listed():
            break
        time.sleep(0.25)
    if not gamescope_running() and not overlay_listed():
        return "error: desktop restart timed out"
    focus_desktop_overlay()
    return "desktop restarted"


def stop_desktop(*, reason: str = "admin") -> str:
    log(f"ADMIN stop-desktop ({reason}): terminating asterism-desktop.service")
    r = systemctl_user("stop", "asterism-desktop.service")
    subprocess.run(
        ["pkill", "-TERM", "-f", f"[g]amescope .*--vr-overlay-key {OVERLAY_KEY}"],
        check=False,
    )
    # Wait for graceful exit
    for _ in range(40):
        if not gamescope_running() and not desktop_running():
            break
        time.sleep(0.25)
    return "desktop stopped" if not desktop_running() else f"stop incomplete rc={r.returncode}"


def focus_desktop_overlay(*, force_dashboard: bool = False) -> None:
    """Visibility/focus only — NEVER mutates layout or dock modes.

    Layout restore is owned solely by desktop/asterism-session.sh (one apply
    when a new gamescope process creates PerWindow overlays). Calling apply
    from show/steamvr-up raced with the session apply and re-ran
    theater→dashboard→world.
    """
    try:
        vrcmd("--showdashboard")
        log("vrcmd --showdashboard (visibility only)")
    except Exception as e:  # noqa: BLE001
        log(f"showdashboard failed: {e}")
    if force_dashboard:
        # Administrative path only (explicit force); still no layout apply.
        for key in (OVERLAY_KEY, f"{OVERLAY_KEY}.app.0"):
            try:
                r = vrcmd("--dock-overlay", "dashboard", key)
                if r.returncode == 0:
                    log(f"vrcmd --dock-overlay dashboard {key} (force_dashboard)")
                    break
            except Exception as e:  # noqa: BLE001
                log(f"dock-overlay {key}: {e}")


def restore_layout(*, wait: float = 45.0) -> str:
    """Deprecated: layout apply is session-owned. Kept for diagnostics only."""
    return "skipped: layout apply owned by asterism-session.sh (not dashboard)"


def show() -> dict:
    """Visibility/focus only. Does not start a healthy desktop; recovers if crashed."""
    if not steamvr_alive():
        return {"ok": False, "action": "show", "message": "error: SteamVR not running"}
    msg = "visibility show"
    if not desktop_running():
        msg = ensure_desktop(reason="crash-recovery")
        if msg.startswith("error:"):
            return {"ok": False, "action": "show", "message": msg}
    focus_desktop_overlay()
    return {
        "ok": True,
        "action": "show",
        "message": msg,
        **_status_fields(),
    }


def hide() -> dict:
    """Hide dashboard focus; never terminate Plasma/gamescope."""
    try:
        vrcmd("--hidedashboard")
        log("vrcmd --hidedashboard (desktop session kept alive)")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "action": "hide", "message": str(e), **_status_fields()}
    return {
        "ok": True,
        "action": "hide",
        "message": "dashboard hidden; desktop session still running",
        **_status_fields(),
    }


def toggle() -> dict:
    if desktop_visible():
        return hide()
    return show()


def _status_fields() -> dict[str, Any]:
    return {
        "steamvr_running": steamvr_alive(),
        "desktop_running": desktop_running(),
        "desktop_visible": desktop_visible(),
        "overlay_present": overlay_listed(),
        "overlay_key": OVERLAY_KEY,
        "gamescope_running": gamescope_running(),
        "socket": str(SOCK),
        "http": f"http://{HTTP_HOST}:{HTTP_PORT}",
        "websocket": f"ws://localhost:{WS_PORT}",
        "dashmgr_ws_connected": dashmgr_ws_connected(),
        "dashmgr_queue_len": dashmgr_queue_len(),
    }


def status() -> dict:
    return {"ok": True, "action": "status", **_status_fields()}


def stop_desktop_cmd() -> dict:
    return {
        "ok": True,
        "action": "stop-desktop",
        "message": stop_desktop(reason="asterism-ctl"),
        "warning": "administrative/debug only — not normal shell behavior",
        **_status_fields(),
    }


def restart_desktop_cmd() -> dict:
    msg = restart_desktop(reason="asterism-ctl")
    return {
        "ok": not msg.startswith("error:"),
        "action": "restart-desktop",
        "message": msg,
        **_status_fields(),
    }


HANDLERS: dict[str, Callable[[], dict]] = {
    "show": show,
    "hide": hide,
    "toggle": toggle,
    "status": status,
    "stop-desktop": stop_desktop_cmd,
    "restart-desktop": restart_desktop_cmd,
    "ping": lambda: {"ok": True, "action": "ping", "message": "pong"},
}

# ---- Dashboard Manager shell bridge (loopback only; asterism.desktop* keys) ----
# HTTP :47831 for CLI/debug. WebSocket :47832 for systemui (CSP allows ws://localhost:*)
_DASHMGR_LOCK = threading.Lock()
_DASHMGR_COND = threading.Condition(_DASHMGR_LOCK)
_DASHMGR_QUEUE: deque[dict[str, Any]] = deque()
_DASHMGR_RESULTS: dict[str, Any] = {}
_DASHMGR_SEQ = 0
_DASHMGR_WS_CLIENT: socket.socket | None = None
_DASHMGR_WS_HELLO = False
DASHMGR_DIR = STATE / "dashboard-state"
PROBE_LOG = LOG_DIR / "dashmgr-probe.jsonl"
_SUPPORTED_CMDS = (
    "list",
    "probe",
    "capture",
    "seed-world",
    "seed-presentation-transform",
    "set-presentation",
    "direct-restore",
    "restore-via-hand",
    "get-live-world",
    "find-live-uo",
    "inspect-undocked-render",
    "force-dashboard-render",
)


def _dashmgr_new_id() -> str:
    global _DASHMGR_SEQ
    _DASHMGR_SEQ += 1
    return f"dm-{int(time.time())}-{_DASHMGR_SEQ}"


def _asterism_overlay_key_ok(key: str | None) -> bool:
    return isinstance(key, str) and key.startswith("asterism.desktop")


def dashmgr_reset_for_tests() -> None:
    """Clear queue/results/client state (unit tests only)."""
    global _DASHMGR_WS_CLIENT, _DASHMGR_WS_HELLO
    with _DASHMGR_COND:
        _DASHMGR_QUEUE.clear()
        _DASHMGR_RESULTS.clear()
        _DASHMGR_WS_CLIENT = None
        _DASHMGR_WS_HELLO = False
        _DASHMGR_COND.notify_all()


def dashmgr_enqueue(cmd: str, **fields: Any) -> dict:
    """Enqueue one command for the systemui WebSocket client (FIFO)."""
    if cmd not in _SUPPORTED_CMDS:
        return {"ok": False, "error": f"unsupported cmd: {cmd}"}
    if cmd in (
        "capture",
        "seed-world",
        "seed-presentation-transform",
        "set-presentation",
        "direct-restore",
        "restore-via-hand",
        "get-live-world",
        "find-live-uo",
        "inspect-undocked-render",
    ):
        if not _asterism_overlay_key_ok(fields.get("overlay_key")):
            return {"ok": False, "error": "overlay_key must start with asterism.desktop"}
    if cmd == "seed-presentation-transform":
        pres = str(fields.get("presentation") or "").lower()
        if pres not in (
            "dashboard",
            "world",
            "theater",
            "lefthand",
            "righthand",
            "left",
            "right",
        ):
            return {
                "ok": False,
                "error": "presentation must be dashboard|world|theater|lefthand|righthand",
            }
        if not isinstance(fields.get("transform"), dict):
            return {"ok": False, "error": "transform object required"}
    cid = _dashmgr_new_id()
    msg = {"id": cid, "cmd": cmd, **fields}
    with _DASHMGR_COND:
        _DASHMGR_QUEUE.append(msg)
        _DASHMGR_COND.notify_all()
    log(f"dashmgr enqueue {cmd} id={cid} qlen={len(_DASHMGR_QUEUE)}")
    return {"ok": True, "id": cid, "queued": msg}


def dashmgr_poll() -> dict:
    """Pop one queued command (HTTP debug / tests). Prefer WebSocket in production."""
    with _DASHMGR_COND:
        if not _DASHMGR_QUEUE:
            return {}
        return _DASHMGR_QUEUE.popleft()


def dashmgr_queue_len() -> int:
    with _DASHMGR_LOCK:
        return len(_DASHMGR_QUEUE)


def dashmgr_ws_connected() -> bool:
    with _DASHMGR_LOCK:
        return _DASHMGR_WS_CLIENT is not None and _DASHMGR_WS_HELLO


def dashmgr_store_result(body: dict) -> dict:
    cid = body.get("id")
    result = body.get("result")
    if not cid:
        return {"ok": False, "error": "missing id"}
    with _DASHMGR_COND:
        _DASHMGR_RESULTS[str(cid)] = {
            "ts": time.time(),
            "result": result,
        }
        _DASHMGR_COND.notify_all()
    try:
        DASHMGR_DIR.mkdir(parents=True, exist_ok=True)
        if isinstance(result, dict) and result.get("probe"):
            with PROBE_LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"id": cid, "probe": result["probe"]}) + "\n")
            (DASHMGR_DIR / "last-probe.json").write_text(
                json.dumps(result["probe"], indent=2), encoding="utf-8"
            )
        if isinstance(result, dict) and result.get("capture"):
            name = f"capture-{cid}.json"
            (DASHMGR_DIR / name).write_text(json.dumps(result, indent=2), encoding="utf-8")
            (DASHMGR_DIR / "last-capture.json").write_text(
                json.dumps(result, indent=2), encoding="utf-8"
            )
    except OSError as e:
        log(f"dashmgr persist failed: {e}")
    log(f"dashmgr result id={cid} ok={isinstance(result, dict) and result.get('ok')}")
    return {"ok": True}


def dashmgr_get_result(cid: str, *, wait: float = 0.0) -> dict:
    deadline = time.time() + max(0.0, wait)
    while True:
        with _DASHMGR_COND:
            got = _DASHMGR_RESULTS.get(cid)
            if got is not None:
                return {"ok": True, "id": cid, **got}
            remaining = deadline - time.time()
            if remaining <= 0:
                return {"ok": False, "error": "timeout", "id": cid}
            _DASHMGR_COND.wait(timeout=min(0.5, remaining))


def dashmgr_request(cmd: str, *, wait: float = 8.0, **fields: Any) -> dict:
    q = dashmgr_enqueue(cmd, **fields)
    if not q.get("ok"):
        return q
    return dashmgr_get_result(q["id"], wait=wait)


def _dashmgr_handle_ws_message(raw: str) -> None:
    global _DASHMGR_WS_HELLO
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        log("dashmgr ws: bad json")
        return
    if not isinstance(msg, dict):
        return
    mtype = msg.get("type")
    if mtype == "hello":
        with _DASHMGR_COND:
            _DASHMGR_WS_HELLO = True
            _DASHMGR_COND.notify_all()
        log(
            f"dashmgr ws hello client={msg.get('client')} version={msg.get('version')}"
        )
        return
    if mtype == "ping":
        with _DASHMGR_LOCK:
            sock = _DASHMGR_WS_CLIENT
        if sock:
            try:
                ws_send_text(sock, json.dumps({"type": "pong"}))
            except OSError:
                pass
        return
    if mtype == "result":
        dashmgr_store_result({"id": msg.get("id"), "result": msg.get("result")})
        return
    log(f"dashmgr ws: unknown type {mtype!r}")


def _dashmgr_ws_reader(sock: socket.socket) -> None:
    global _DASHMGR_WS_CLIENT, _DASHMGR_WS_HELLO
    try:
        while True:
            text = ws_recv_text(sock)
            if text is None:
                break
            _dashmgr_handle_ws_message(text)
    except (OSError, ConnectionError, ValueError) as e:
        log(f"dashmgr ws reader end: {e}")
    finally:
        with _DASHMGR_COND:
            if _DASHMGR_WS_CLIENT is sock:
                _DASHMGR_WS_CLIENT = None
                _DASHMGR_WS_HELLO = False
                _DASHMGR_COND.notify_all()
        try:
            sock.close()
        except OSError:
            pass
        log("dashmgr ws client disconnected")


def _dashmgr_ws_dispatcher() -> None:
    """Send queued commands to the connected systemui WebSocket client."""
    global _DASHMGR_WS_CLIENT, _DASHMGR_WS_HELLO
    while not _shutdown:
        with _DASHMGR_COND:
            while (
                not _shutdown
                and (
                    not _DASHMGR_QUEUE
                    or _DASHMGR_WS_CLIENT is None
                    or not _DASHMGR_WS_HELLO
                )
            ):
                _DASHMGR_COND.wait(timeout=0.5)
            if _shutdown:
                return
            if not _DASHMGR_QUEUE or _DASHMGR_WS_CLIENT is None or not _DASHMGR_WS_HELLO:
                continue
            msg = _DASHMGR_QUEUE.popleft()
            sock = _DASHMGR_WS_CLIENT
        frame = {"type": "command", **msg}
        try:
            ws_send_text(sock, json.dumps(frame))
            log(f"dashmgr ws sent cmd={msg.get('cmd')} id={msg.get('id')}")
        except OSError as e:
            log(f"dashmgr ws send failed: {e}; re-queue")
            with _DASHMGR_COND:
                _DASHMGR_QUEUE.appendleft(msg)
                if _DASHMGR_WS_CLIENT is sock:
                    _DASHMGR_WS_CLIENT = None
                    _DASHMGR_WS_HELLO = False
                _DASHMGR_COND.notify_all()
            time.sleep(0.2)


def _dashmgr_ws_accept_loop(listen_sock: socket.socket) -> None:
    global _DASHMGR_WS_CLIENT, _DASHMGR_WS_HELLO
    while not _shutdown:
        try:
            listen_sock.settimeout(1.0)
            conn, addr = listen_sock.accept()
        except socket.timeout:
            continue
        except OSError:
            break
        try:
            conn.settimeout(10.0)
            req = b""
            while b"\r\n\r\n" not in req and len(req) < 8192:
                chunk = conn.recv(1024)
                if not chunk:
                    raise ConnectionError("empty upgrade")
                req += chunk
            key = parse_http_upgrade(req)
            if not key:
                conn.sendall(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
                conn.close()
                continue
            conn.sendall(ws_handshake_response(key))
            conn.settimeout(None)
            with _DASHMGR_COND:
                old = _DASHMGR_WS_CLIENT
                _DASHMGR_WS_CLIENT = conn
                _DASHMGR_WS_HELLO = False
                _DASHMGR_COND.notify_all()
            if old and old is not conn:
                ws_send_close(old)
                try:
                    old.close()
                except OSError:
                    pass
            log(f"dashmgr ws accepted from {addr}")
            threading.Thread(
                target=_dashmgr_ws_reader,
                args=(conn,),
                name="asterism-ws-reader",
                daemon=True,
            ).start()
        except (OSError, ConnectionError, ValueError) as e:
            log(f"dashmgr ws accept error: {e}")
            try:
                conn.close()
            except OSError:
                pass


def start_websocket() -> socket.socket | None:
    try:
        listen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen.bind((WS_HOST, WS_PORT))
        listen.listen(2)
    except OSError as e:
        log(f"WebSocket listen failed on {WS_HOST}:{WS_PORT}: {e}")
        return None
    threading.Thread(
        target=_dashmgr_ws_accept_loop,
        args=(listen,),
        name="asterism-ws-accept",
        daemon=True,
    ).start()
    threading.Thread(
        target=_dashmgr_ws_dispatcher,
        name="asterism-ws-dispatch",
        daemon=True,
    ).start()
    log(f"WebSocket bridge on ws://localhost:{WS_PORT} (bound {WS_HOST})")
    return listen


def on_signal(signum, _frame):
    global _shutdown
    log(f"signal {signum}; shutting down control plane")
    _shutdown = True


def handle_command(name: str) -> dict:
    handler = HANDLERS.get(name)
    if not handler:
        return {"ok": False, "error": f"unknown command: {name}", "commands": sorted(HANDLERS)}
    try:
        return handler()
    except Exception as e:  # noqa: BLE001
        log(f"handler {name} error: {e}")
        return {"ok": False, "action": name, "message": str(e)}


def handle_client(conn: socket.socket) -> None:
    data = b""
    conn.settimeout(5)
    try:
        while not data.endswith(b"\n") and len(data) < 4096:
            chunk = conn.recv(1024)
            if not chunk:
                break
            data += chunk
    except OSError:
        return
    name = (data.decode("utf-8", errors="replace").strip().split() or ["status"])[0]
    conn.sendall((json.dumps(handle_command(name)) + "\n").encode())


class HttpHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        log("http " + (fmt % args))

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 1_000_000:
            return {}
        raw = self.rfile.read(length)
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return obj if isinstance(obj, dict) else {}

    def _send(self, code: int, obj: dict) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        # Chromium Private Network Access (vrwebhelper enables BlockInsecurePrivateNetworkRequests)
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path in ("/status", "/"):
            self._send(200, handle_command("status"))
        elif path == "/ping":
            self._send(200, handle_command("ping"))
        elif path == "/dashmgr/poll":
            self._send(200, dashmgr_poll())
        elif path.startswith("/dashmgr/result/"):
            cid = path.rsplit("/", 1)[-1]
            self._send(200, dashmgr_get_result(cid, wait=0.0))
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        cmd = path.lstrip("/")
        if cmd in HANDLERS and cmd not in ("stop-desktop", "restart-desktop"):
            # Shell UI may POST /show /hide /toggle — never expose stop/restart over HTTP by default
            self._send(200, handle_command(cmd))
            return
        if cmd in ("stop-desktop", "restart-desktop"):
            self._send(403, {"ok": False, "error": f"{cmd} not allowed over HTTP"})
            return
        if cmd == "dashmgr/probe":
            body = self._read_json()
            # Direct probe upload from shell (not poll result)
            DASHMGR_DIR.mkdir(parents=True, exist_ok=True)
            try:
                with PROBE_LOG.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(body) + "\n")
                (DASHMGR_DIR / "last-probe.json").write_text(
                    json.dumps(body, indent=2), encoding="utf-8"
                )
            except OSError as e:
                log(f"probe save failed: {e}")
            log("dashmgr probe received")
            self._send(200, {"ok": True})
            return
        if cmd == "dashmgr/result":
            self._send(200, dashmgr_store_result(self._read_json()))
            return
        if cmd == "dashmgr/enqueue":
            body = self._read_json()
            c = body.get("cmd")
            fields = {k: v for k, v in body.items() if k != "cmd"}
            self._send(200, dashmgr_enqueue(str(c or ""), **fields))
            return
        if cmd == "dashmgr/request":
            body = self._read_json()
            c = body.get("cmd")
            wait = float(body.get("wait") or 8.0)
            fields = {k: v for k, v in body.items() if k not in ("cmd", "wait")}
            self._send(200, dashmgr_request(str(c or ""), wait=wait, **fields))
            return
        self._send(404, {"ok": False, "error": "not found"})


def start_http() -> ThreadingHTTPServer | None:
    try:
        srv = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), HttpHandler)
    except OSError as e:
        log(f"HTTP listen failed on {HTTP_HOST}:{HTTP_PORT}: {e}")
        return None
    t = threading.Thread(target=srv.serve_forever, name="asterism-http", daemon=True)
    t.start()
    log(f"HTTP control on http://{HTTP_HOST}:{HTTP_PORT}")
    return srv


def supervisor_tick() -> None:
    global _steamvr_was_alive
    alive = steamvr_alive()
    if alive and not _steamvr_was_alive:
        log("SteamVR became healthy; ensuring desktop infrastructure")
        msg = ensure_desktop(reason="steamvr-up")
        log(f"ensure after steamvr-up: {msg}")
        if not msg.startswith("error:"):
            # Bring the overlay forward after a SteamVR restart (visibility, not lifecycle).
            focus_desktop_overlay()
    if not alive and _steamvr_was_alive:
        log("SteamVR went away; gracefully stopping desktop")
        stop_desktop(reason="steamvr-down")
    if alive and _steamvr_was_alive and not desktop_running():
        log("desktop missing while SteamVR healthy — crash recovery")
        ensure_desktop(reason="crash-recovery")
    elif alive and _steamvr_was_alive:
        # Unit can report active while gamescope died mid-session.
        if (
            systemctl_user("is-active", "asterism-desktop.service").stdout.strip() == "active"
            and not gamescope_running()
        ):
            log("desktop unit active but gamescope gone — crash recovery")
            ensure_desktop(reason="crash-recovery")
    _steamvr_was_alive = alive


def main() -> int:
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    if SOCK.exists():
        SOCK.unlink()
    log(f"asterism-dashboard starting; socket={SOCK}")
    http = start_http()
    wss = start_websocket()

    if steamvr_alive():
        _steamvr_was_alive = True
        ensure_desktop(reason="dashboard-start")
        # Visibility only — session.sh owns the one-shot layout apply.
        focus_desktop_overlay()
    else:
        log("SteamVR not yet up; waiting (will start desktop when healthy)")

    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(SOCK))
    srv.listen(5)
    srv.settimeout(1.0)
    os.chmod(SOCK, 0o600)

    while not _shutdown:
        supervisor_tick()
        try:
            conn, _ = srv.accept()
        except socket.timeout:
            continue
        except OSError:
            break
        with conn:
            handle_client(conn)

    log("asterism-dashboard exit; stopping desktop if still up")
    if desktop_running():
        stop_desktop(reason="dashboard-exit")
    try:
        srv.close()
    except OSError:
        pass
    if http:
        http.shutdown()
    if wss:
        try:
            wss.close()
        except OSError:
            pass
    if SOCK.exists():
        SOCK.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
