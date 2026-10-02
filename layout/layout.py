#!/usr/bin/env python3
"""Asterism VR layout (gamescope PerWindow path).

Inspired by FrameTop layout/ft_layout.py gamescope backend
(https://github.com/AZumD/frametop) — dock modes via vrcmd, layout file under
~/.config/asterism/layout.json. World poses are applied by pointer/helper/asterism-place
through the asterism_pointer virtual controller (FrameTop ft-pointer place pattern).
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import tempfile
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = Path(
    os.environ.get(
        "ASTERISM_LAYOUT_PATH",
        Path.home() / ".config/asterism/layout.json",
    )
)
STEAMVR = Path(os.environ.get("STEAMVR_ROOT", "/opt/steamvr"))
VRCMD = Path(os.environ.get("VRCMD", STEAMVR / "bin/linuxarm64/vrcmd"))
OVERLAY_PREFIX = os.environ.get("ASTERISM_OVERLAY_KEY", "asterism.desktop")

SCHEMA_VERSION = 1
ALLOWED_DOCK = ("dashboard", "theater", "world")


class LayoutError(Exception):
    pass


def default_layout(screen_count: int = 1) -> dict[str, Any]:
    screens = []
    # Simple arc in front of the head (metres), FrameTop-style coordinates:
    # +x right, +y up, -z forward; face = yaw/pitch degrees relative to heading.
    if screen_count <= 1:
        screens.append(_screen_entry(0.0, 0.0, -1.6, 0.0, 0.0, "world"))
    else:
        gap_yaw = 32.0
        start = -0.5 * (screen_count - 1) * gap_yaw
        for i in range(screen_count):
            yaw = start + i * gap_yaw
            rad = math.radians(yaw)
            dist = 1.6
            screens.append(
                _screen_entry(
                    dist * math.sin(rad),
                    0.0,
                    -dist * math.cos(rad),
                    yaw,
                    0.0,
                    "world",
                )
            )
    return {
        "version": SCHEMA_VERSION,
        "auto": True,
        "mode": "preset",
        "screens": screens,
    }


def _screen_entry(
    x: float, y: float, z: float, yaw: float, pitch: float, dock: str
) -> dict[str, Any]:
    return {
        "dock": dock,
        "pos": [round(x, 4), round(y, 4), round(z, 4)],
        "face": [round(yaw, 2), round(pitch, 2)],
        "roll": 0.0,
    }


def validate_layout(cfg: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(cfg, dict):
        raise LayoutError("layout root must be an object")
    ver = int(cfg.get("version", 0))
    if ver != SCHEMA_VERSION:
        raise LayoutError(f"unsupported layout version {ver}")
    screens = cfg.get("screens")
    if not isinstance(screens, list) or not screens:
        raise LayoutError("screens must be a non-empty list")
    out = []
    for i, s in enumerate(screens):
        if not isinstance(s, dict):
            raise LayoutError(f"screens[{i}] must be object")
        dock = str(s.get("dock", "world"))
        if dock not in ALLOWED_DOCK:
            raise LayoutError(f"invalid dock mode: {dock}")
        pos = s.get("pos", [0.0, 0.0, -1.6])
        face = s.get("face", [0.0, 0.0])
        if not (isinstance(pos, list) and len(pos) == 3):
            raise LayoutError(f"screens[{i}].pos must be [x,y,z]")
        if not (isinstance(face, list) and len(face) == 2):
            raise LayoutError(f"screens[{i}].face must be [yaw,pitch]")
        out.append(
            {
                "dock": dock,
                "pos": [float(pos[0]), float(pos[1]), float(pos[2])],
                "face": [float(face[0]), float(face[1])],
                "roll": float(s.get("roll", 0.0)),
            }
        )
    return {
        "version": SCHEMA_VERSION,
        "auto": bool(cfg.get("auto", True)),
        "mode": str(cfg.get("mode", "preset")),
        "screens": out,
    }


def load(path: Path | None = None) -> dict[str, Any]:
    path = path or DEFAULT_PATH
    if not path.is_file():
        return default_layout(1)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise LayoutError(f"invalid JSON in {path}: {e}") from e
    return validate_layout(raw)


def save(cfg: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    path = path or DEFAULT_PATH
    cfg = validate_layout(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(cfg, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".layout-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return cfg


def env_for_vr() -> dict[str, str]:
    e = os.environ.copy()
    lib = str(STEAMVR / "bin/linuxarm64")
    e["LD_LIBRARY_PATH"] = lib + ((":" + e["LD_LIBRARY_PATH"]) if e.get("LD_LIBRARY_PATH") else "")
    uid = os.getuid()
    e.setdefault("XDG_RUNTIME_DIR", f"/run/user/{uid}")
    e["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={e['XDG_RUNTIME_DIR']}/bus"
    return e


def vrcmd(*args: str, timeout: float = 15) -> str:
    if not VRCMD.is_file():
        raise LayoutError(f"vrcmd missing: {VRCMD}")
    r = subprocess.run(
        [str(VRCMD), *args],
        capture_output=True,
        text=True,
        env=env_for_vr(),
        timeout=timeout,
        check=False,
    )
    return (r.stdout or "") + (r.stderr or "")


def screen_keys() -> list[str]:
    """PerWindow keys in order. Skip .app.0 (gamescope default connector — FrameTop note)."""
    text = vrcmd("--overlays")
    found: list[tuple[int, str]] = []
    for m in re.finditer(
        rf"^'({re.escape(OVERLAY_PREFIX)}\.app\.(\d+))' .*VROverlayType_Dashboard_Main",
        text,
        re.M,
    ):
        idx = int(m.group(2))
        if idx > 0:
            found.append((idx, m.group(1)))
    return [k for _, k in sorted(found)]


def float_then_dock(key: str, dock: str) -> None:
    """FrameTop float_screen dance, then park in the requested dock mode.

    Dashboard must be open when undocking to world so SteamVR assigns an initial
    undocked pose; then hide so a later grab can't snap the panel back in.
    """
    vrcmd("--dock-overlay", "theater", key)
    time.sleep(0.5)
    if dock == "theater":
        return
    vrcmd("--dock-overlay", "dashboard", key)
    time.sleep(0.8)
    if dock == "dashboard":
        return
    vrcmd("--dock-overlay", "world", key)
    time.sleep(0.8)
    vrcmd("--hidedashboard")
    time.sleep(0.8)


def place_bin() -> Path:
    return Path(
        os.environ.get(
            "ASTERISM_PLACE",
            ROOT / "pointer" / "helper" / "build" / "asterism-place",
        )
    )


def place_world(key: str, screen: dict[str, Any], *, timeout: float = 45.0) -> dict[str, Any]:
    """Move a world-docked overlay to layout pos/face/roll (head-relative metres/deg)."""
    bin_path = place_bin()
    if not bin_path.is_file():
        return {
            "ok": False,
            "key": key,
            "error": f"asterism-place missing ({bin_path}); build pointer/helper",
        }
    pos = screen["pos"]
    face = screen["face"]
    roll = float(screen.get("roll", 0.0))
    cmd = [
        str(bin_path),
        "place",
        key,
        f"{pos[0]:.4f}",
        f"{pos[1]:.4f}",
        f"{pos[2]:.4f}",
        f"{face[0]:.3f}",
        f"{face[1]:.3f}",
        f"{roll:.3f}",
    ]
    env = env_for_vr()
    env["LD_LIBRARY_PATH"] = (
        str(STEAMVR / "bin/linuxarm64")
        + ((":" + env["LD_LIBRARY_PATH"]) if env.get("LD_LIBRARY_PATH") else "")
    )
    r = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
        check=False,
    )
    out = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    reply = next((ln for ln in reversed(lines) if ln.startswith(("ok ", "error "))), lines[-1] if lines else out)
    ok = reply.startswith("ok ")
    return {"ok": ok, "key": key, "reply": reply, "rc": r.returncode}


def ensure_screen_count(layout: dict[str, Any], count: int) -> dict[str, Any]:
    layout = deepcopy(validate_layout(layout))
    while len(layout["screens"]) < count:
        layout["screens"].append(_screen_entry(0.0, 0.0, -1.6, 0.0, 0.0, "world"))
    if len(layout["screens"]) > count:
        layout["screens"] = layout["screens"][:count]
    return layout


def place_on_apply_enabled() -> bool:
    """Laser-grab place on apply is opt-in: it steals the dashboard laser and is still unreliable."""
    return os.environ.get("ASTERISM_PLACE_ON_APPLY", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def release_pointer() -> dict[str, Any]:
    """Force-release asterism_pointer (hide + trigger up) so the real laser returns."""
    bin_path = place_bin()
    if not bin_path.is_file():
        return {"ok": False, "error": f"asterism-place missing ({bin_path})"}
    env = env_for_vr()
    env["LD_LIBRARY_PATH"] = (
        str(STEAMVR / "bin/linuxarm64")
        + ((":" + env["LD_LIBRARY_PATH"]) if env.get("LD_LIBRARY_PATH") else "")
    )
    r = subprocess.run(
        [str(bin_path), "release"],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
        check=False,
    )
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    return {"ok": r.returncode == 0, "reply": out, "rc": r.returncode}


def apply_layout(
    *, wait: float = 60.0, path: Path | None = None, place: bool | None = None
) -> dict[str, Any]:
    """Wait for PerWindow overlays, restore dock modes. Optional laser place is opt-in."""
    layout = load(path)
    if not layout.get("auto", True):
        return {"ok": True, "skipped": True, "reason": "auto=false"}
    deadline = time.time() + wait
    keys: list[str] = []
    want = len(layout["screens"])
    while time.time() < deadline:
        keys = screen_keys()
        if len(keys) >= want:
            break
        time.sleep(1.0)
    if not keys:
        raise LayoutError("no Asterism PerWindow overlays yet; is the desktop running?")
    keys = keys[:want]
    layout = ensure_screen_count(layout, len(keys))
    # Quiet any leftover virtual controller from a prior failed place.
    try:
        release_pointer()
    except Exception:
        pass
    vrcmd("--hidedashboard")
    time.sleep(0.5)
    applied = []
    for key, screen in zip(keys, layout["screens"]):
        entry: dict[str, Any] = {"key": key, "dock": screen["dock"]}
        float_then_dock(key, screen["dock"])
        applied.append(entry)
    do_place = place_on_apply_enabled() if place is None else place
    if do_place:
        time.sleep(1.0)
        for entry, screen in zip(applied, layout["screens"]):
            if screen["dock"] != "world":
                continue
            key = entry["key"]
            placed = place_world(key, screen)
            entry["place"] = placed
        try:
            release_pointer()
        except Exception:
            pass
    save(layout, path)
    return {
        "ok": True,
        "applied": applied,
        "place_on_apply": do_place,
        "placed": (
            all(
                a.get("dock") != "world" or (a.get("place") or {}).get("ok")
                for a in applied
            )
            if do_place
            else None
        ),
    }


def apply_places(*, path: Path | None = None) -> dict[str, Any]:
    """Laser-grab each world screen to layout.json poses (explicit; not used on restart)."""
    layout = load(path)
    keys = screen_keys()
    if not keys:
        raise LayoutError("no Asterism PerWindow overlays yet")
    layout = ensure_screen_count(layout, len(keys))
    keys = keys[: len(layout["screens"])]
    results = []
    for key, screen in zip(keys, layout["screens"]):
        if screen["dock"] != "world":
            results.append({"key": key, "dock": screen["dock"], "skipped": True})
            continue
        float_then_dock(key, "world")
        time.sleep(0.5)
        results.append({"key": key, "dock": "world", "place": place_world(key, screen)})
    try:
        release_pointer()
    except Exception:
        pass
    return {"ok": True, "applied": results}


def sync_layout_to_display_count(display_count: int, path: Path | None = None) -> dict[str, Any]:
    path = path or DEFAULT_PATH
    if path.is_file():
        layout = load(path)
        layout = ensure_screen_count(layout, display_count)
    else:
        layout = default_layout(display_count)
    return save(layout, path)


def remember_world_docks(path: Path | None = None) -> dict[str, Any]:
    """Mark every screen as world (user floated panels outside Settings)."""
    layout = load(path)
    for s in layout["screens"]:
        s["dock"] = "world"
    layout["mode"] = "custom"
    return save(layout, path)
