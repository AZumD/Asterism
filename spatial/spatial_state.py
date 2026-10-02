#!/usr/bin/env python3
"""Asterism spatial persistence — Valve World transforms keyed by stable display IDs."""
from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(
    os.environ.get(
        "ASTERISM_SPATIAL_PATH",
        Path.home() / ".local/state/asterism/spatial-state.json",
    )
)

SCHEMA_VERSION = 1


class SpatialStateError(Exception):
    pass


def default_state() -> dict[str, Any]:
    return {"version": SCHEMA_VERSION, "displays": {}}


def _validate_vec3(obj: Any, name: str) -> dict[str, float]:
    if not isinstance(obj, dict):
        raise SpatialStateError(f"{name} must be an object")
    try:
        return {"x": float(obj["x"]), "y": float(obj["y"]), "z": float(obj["z"])}
    except (KeyError, TypeError, ValueError) as e:
        raise SpatialStateError(f"invalid {name}: {e}") from e


def _validate_quat(obj: Any) -> dict[str, float]:
    if not isinstance(obj, dict):
        raise SpatialStateError("rotation must be an object")
    try:
        return {
            "w": float(obj["w"]),
            "x": float(obj["x"]),
            "y": float(obj["y"]),
            "z": float(obj["z"]),
        }
    except (KeyError, TypeError, ValueError) as e:
        raise SpatialStateError(f"invalid rotation: {e}") from e


def validate_transform(xf: Any) -> dict[str, Any]:
    if not isinstance(xf, dict):
        raise SpatialStateError("worldTransform must be an object")
    out: dict[str, Any] = {
        "translation": _validate_vec3(xf.get("translation"), "translation"),
        "rotation": _validate_quat(xf.get("rotation")),
    }
    scale = xf.get("scale")
    if scale is None:
        pass
    elif isinstance(scale, (int, float)):
        out["scale"] = float(scale)
    elif isinstance(scale, dict):
        out["scale"] = _validate_vec3(scale, "scale")
    else:
        raise SpatialStateError(f"invalid scale: {scale!r}")
    return out


def validate_state(state: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise SpatialStateError("state root must be an object")
    ver = int(state.get("version", 0))
    if ver != SCHEMA_VERSION:
        raise SpatialStateError(f"unsupported spatial-state version {ver}")
    displays = state.get("displays")
    if displays is None:
        displays = {}
    if not isinstance(displays, dict):
        raise SpatialStateError("displays must be an object")
    out_disp: dict[str, Any] = {}
    for did, entry in displays.items():
        if not isinstance(did, str) or not did.startswith("display-"):
            raise SpatialStateError(f"invalid display id: {did!r}")
        if not isinstance(entry, dict):
            raise SpatialStateError(f"display entry must be object: {did}")
        cleaned: dict[str, Any] = {}
        pres = entry.get("presentation")
        if pres is not None:
            if pres not in ("dashboard", "world", "theater", "lefthand", "righthand"):
                raise SpatialStateError(f"bad presentation for {did}: {pres!r}")
            cleaned["presentation"] = pres
        if "worldTransform" in entry and entry["worldTransform"] is not None:
            cleaned["worldTransform"] = validate_transform(entry["worldTransform"])
        out_disp[did] = cleaned
    return {"version": SCHEMA_VERSION, "displays": out_disp}


def load(path: Path | None = None) -> dict[str, Any]:
    path = path or DEFAULT_PATH
    if not path.is_file():
        return default_state()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise SpatialStateError(f"corrupt spatial state at {path}: {e}") from e
    return validate_state(raw)


def load_or_default(path: Path | None = None) -> dict[str, Any]:
    try:
        return load(path)
    except SpatialStateError:
        return default_state()


def save(state: dict[str, Any], path: Path | None = None) -> Path:
    """Atomic write of validated spatial state."""
    path = path or DEFAULT_PATH
    cleaned = validate_state(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(cleaned, indent=2, sort_keys=True) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=".spatial-", suffix=".json", dir=str(path.parent))
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
    return path


def set_display_world(
    display_id: str,
    transform: dict[str, Any],
    *,
    presentation: str = "world",
    path: Path | None = None,
) -> dict[str, Any]:
    state = load_or_default(path)
    entry = dict(state["displays"].get(display_id) or {})
    entry["presentation"] = presentation
    entry["worldTransform"] = validate_transform(transform)
    state["displays"][display_id] = entry
    save(state, path)
    return deepcopy(state)


def get_display(display_id: str, path: Path | None = None) -> dict[str, Any] | None:
    state = load_or_default(path)
    return deepcopy(state["displays"].get(display_id))
