#!/usr/bin/env python3
"""Asterism display topology — persistent Linux outputs (not spatial VR placement)."""
from __future__ import annotations

import json
import os
import re
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(os.environ.get(
    "ASTERISM_DISPLAYS_PATH",
    Path.home() / ".config/asterism/displays.json",
))

SCHEMA_VERSION = 1
ALLOWED_ROTATIONS = ("normal", "left", "right", "inverted")
RES_RE = re.compile(r"^(\d{3,5})x(\d{3,5})$")
MIN_W, MAX_W = 640, 7680
MIN_H, MAX_H = 480, 4320
MIN_SCALE, MAX_SCALE = 0.5, 3.0


class DisplayConfigError(Exception):
    pass


def default_config() -> dict[str, Any]:
    return {
        "version": SCHEMA_VERSION,
        "displays": [
            {
                "id": "display-1",
                "enabled": True,
                "primary": True,
                "resolution": [1280, 800],
                "scale": 1.0,
                "rotation": "normal",
            }
        ],
    }


def _validate_resolution(res: Any) -> list[int]:
    if isinstance(res, str):
        m = RES_RE.match(res.strip())
        if not m:
            raise DisplayConfigError(f"invalid resolution string: {res!r}")
        res = [int(m.group(1)), int(m.group(2))]
    if not isinstance(res, (list, tuple)) or len(res) != 2:
        raise DisplayConfigError(f"resolution must be [w,h], got {res!r}")
    w, h = int(res[0]), int(res[1])
    if not (MIN_W <= w <= MAX_W and MIN_H <= h <= MAX_H):
        raise DisplayConfigError(f"resolution out of range: {w}x{h}")
    return [w, h]


def _validate_scale(scale: Any) -> float:
    s = float(scale)
    if not (MIN_SCALE <= s <= MAX_SCALE):
        raise DisplayConfigError(f"scale out of range: {s}")
    return s


def validate_config(cfg: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(cfg, dict):
        raise DisplayConfigError("config root must be an object")
    ver = int(cfg.get("version", 0))
    if ver != SCHEMA_VERSION:
        raise DisplayConfigError(f"unsupported version {ver}")
    displays = cfg.get("displays")
    if not isinstance(displays, list) or not displays:
        raise DisplayConfigError("displays must be a non-empty list")
    ids: set[str] = set()
    primaries = 0
    out_displays = []
    for i, d in enumerate(displays):
        if not isinstance(d, dict):
            raise DisplayConfigError(f"display[{i}] must be object")
        did = str(d.get("id") or "").strip()
        if not did or not re.match(r"^display-\d+$", did):
            raise DisplayConfigError(f"invalid display id: {did!r}")
        if did in ids:
            raise DisplayConfigError(f"duplicate display id: {did}")
        ids.add(did)
        enabled = bool(d.get("enabled", True))
        primary = bool(d.get("primary", False))
        if primary:
            primaries += 1
        rot = str(d.get("rotation", "normal"))
        if rot not in ALLOWED_ROTATIONS:
            raise DisplayConfigError(f"invalid rotation: {rot}")
        out_displays.append({
            "id": did,
            "enabled": enabled,
            "primary": primary,
            "resolution": _validate_resolution(d.get("resolution", [1280, 800])),
            "scale": _validate_scale(d.get("scale", 1.0)),
            "rotation": rot,
        })
    if primaries != 1:
        raise DisplayConfigError(f"exactly one primary required (got {primaries})")
    # Primary should be enabled
    prim = next(x for x in out_displays if x["primary"])
    if not prim["enabled"]:
        raise DisplayConfigError("primary display must be enabled")
    return {"version": SCHEMA_VERSION, "displays": out_displays}


def load(path: Path | None = None) -> dict[str, Any]:
    path = path or DEFAULT_PATH
    if not path.is_file():
        cfg = default_config()
        save(cfg, path)
        return cfg
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return validate_config(raw)
    except (json.JSONDecodeError, DisplayConfigError, OSError) as e:
        # Preserve last-known-good: do not overwrite; raise for caller
        bak = path.with_suffix(".json.corrupt")
        try:
            if path.is_file():
                bak.write_bytes(path.read_bytes())
        except OSError:
            pass
        raise DisplayConfigError(f"invalid config at {path}: {e} (copied to {bak})") from e


def save(cfg: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    path = path or DEFAULT_PATH
    cfg = validate_config(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(cfg, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".displays.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return cfg


def next_id(cfg: dict[str, Any]) -> str:
    nums = []
    for d in cfg["displays"]:
        m = re.match(r"^display-(\d+)$", d["id"])
        if m:
            nums.append(int(m.group(1)))
    n = max(nums, default=0) + 1
    return f"display-{n}"


def add_display(cfg: dict[str, Any], *, resolution: list[int] | None = None) -> dict[str, Any]:
    cfg = deepcopy(validate_config(cfg))
    cfg["displays"].append({
        "id": next_id(cfg),
        "enabled": True,
        "primary": False,
        "resolution": resolution or list(cfg["displays"][0]["resolution"]),
        "scale": 1.0,
        "rotation": "normal",
    })
    return validate_config(cfg)


def remove_display(cfg: dict[str, Any], display_id: str) -> dict[str, Any]:
    cfg = deepcopy(validate_config(cfg))
    if len(cfg["displays"]) <= 1:
        raise DisplayConfigError("cannot remove the last display")
    kept = [d for d in cfg["displays"] if d["id"] != display_id]
    if len(kept) == len(cfg["displays"]):
        raise DisplayConfigError(f"unknown display id: {display_id}")
    removed = next(d for d in cfg["displays"] if d["id"] == display_id)
    cfg["displays"] = kept
    if removed["primary"]:
        # Promote first enabled, else first
        for d in cfg["displays"]:
            if d["enabled"]:
                d["primary"] = True
                break
        else:
            cfg["displays"][0]["primary"] = True
            cfg["displays"][0]["enabled"] = True
    return validate_config(cfg)


def set_primary(cfg: dict[str, Any], display_id: str) -> dict[str, Any]:
    cfg = deepcopy(validate_config(cfg))
    found = False
    for d in cfg["displays"]:
        if d["id"] == display_id:
            d["primary"] = True
            d["enabled"] = True
            found = True
        else:
            d["primary"] = False
    if not found:
        raise DisplayConfigError(f"unknown display id: {display_id}")
    return validate_config(cfg)


def set_field(cfg: dict[str, Any], display_id: str, field: str, value: Any) -> dict[str, Any]:
    cfg = deepcopy(validate_config(cfg))
    target = next((d for d in cfg["displays"] if d["id"] == display_id), None)
    if not target:
        raise DisplayConfigError(f"unknown display id: {display_id}")
    if field == "resolution":
        target["resolution"] = _validate_resolution(value)
    elif field == "scale":
        target["scale"] = _validate_scale(value)
    elif field == "rotation":
        if value not in ALLOWED_ROTATIONS:
            raise DisplayConfigError(f"invalid rotation: {value}")
        target["rotation"] = value
    elif field == "enabled":
        target["enabled"] = bool(value) if not isinstance(value, str) else value.lower() in ("1", "true", "yes", "on")
        if target["primary"] and not target["enabled"]:
            raise DisplayConfigError("cannot disable the primary display")
    else:
        raise DisplayConfigError(f"unknown field: {field}")
    return validate_config(cfg)


def enabled_count(cfg: dict[str, Any]) -> int:
    return sum(1 for d in cfg["displays"] if d["enabled"])


def primary(cfg: dict[str, Any]) -> dict[str, Any]:
    return next(d for d in cfg["displays"] if d["primary"])


def apply_hint(cfg: dict[str, Any]) -> dict[str, Any]:
    """Return what the session will consume + whether restart is required."""
    cfg = validate_config(cfg)
    p = primary(cfg)
    return {
        "primary_id": p["id"],
        "resolution": p["resolution"],
        "scale": p["scale"],
        "rotation": p["rotation"],
        "enabled_count": enabled_count(cfg),
        "requires_desktop_restart": True,
        "note": "Topology apply stages displays.json; restart asterism-desktop to take effect. "
                "gamescope uses one pixel size for all outputs (primary resolution).",
    }
