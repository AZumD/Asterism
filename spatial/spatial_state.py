#!/usr/bin/env python3
"""Asterism spatial persistence — presentation + per-dock transforms by display ID."""
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

SCHEMA_VERSION = 2
ALLOWED_PRESENTATIONS = ("dashboard", "world", "theater", "lefthand", "righthand")
TRANSFORM_KEYS = ("dashboard", "world", "theater", "lefthand", "righthand")

# capture/dockLocationName uses Valve-style Title Case
PRES_ALIASES = {
    "dashboard": "dashboard",
    "world": "world",
    "theater": "theater",
    "lefthand": "lefthand",
    "righthand": "righthand",
    "left": "lefthand",
    "right": "righthand",
    # Boot is a transient Valve state — do not persist as dashboard/world/etc.
}

# Explicit unsupported transient presentations (normalize -> None)
PRES_UNSUPPORTED = frozenset({"boot"})


class SpatialStateError(Exception):
    pass


def default_state() -> dict[str, Any]:
    return {"version": SCHEMA_VERSION, "displays": {}}


def normalize_presentation(name: Any) -> str | None:
    if name is None:
        return None
    key = str(name).strip().lower().replace(" ", "").replace("_", "")
    if key in PRES_UNSUPPORTED:
        return None
    # LeftHand -> lefthand
    return PRES_ALIASES.get(key)


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
        raise SpatialStateError("transform must be an object")
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


def migrate_v1_to_v2(state: dict[str, Any]) -> dict[str, Any]:
    """Convert schema v1 {worldTransform} entries to v2 {transforms.world}."""
    displays_in = state.get("displays") or {}
    if not isinstance(displays_in, dict):
        raise SpatialStateError("displays must be an object")
    out_disp: dict[str, Any] = {}
    for did, entry in displays_in.items():
        if not isinstance(did, str) or not did.startswith("display-"):
            raise SpatialStateError(f"invalid display id: {did!r}")
        if not isinstance(entry, dict):
            raise SpatialStateError(f"display entry must be object: {did}")
        cleaned: dict[str, Any] = {}
        pres = normalize_presentation(entry.get("presentation"))
        if entry.get("presentation") is not None and pres is None:
            raise SpatialStateError(f"bad presentation for {did}: {entry.get('presentation')!r}")
        if pres:
            cleaned["presentation"] = pres
        transforms: dict[str, Any] = {}
        if isinstance(entry.get("transforms"), dict):
            for k, v in entry["transforms"].items():
                nk = normalize_presentation(k)
                if nk and v is not None:
                    transforms[nk] = validate_transform(v)
        if entry.get("worldTransform") is not None:
            transforms.setdefault("world", validate_transform(entry["worldTransform"]))
            if "presentation" not in cleaned:
                cleaned["presentation"] = "world"
        if transforms:
            cleaned["transforms"] = transforms
        out_disp[did] = cleaned
    return {"version": SCHEMA_VERSION, "displays": out_disp}


def validate_state(state: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise SpatialStateError("state root must be an object")
    ver = int(state.get("version", 0))
    if ver == 1:
        return migrate_v1_to_v2(state)
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
        pres = normalize_presentation(entry.get("presentation"))
        if entry.get("presentation") is not None and pres is None:
            raise SpatialStateError(f"bad presentation for {did}: {entry.get('presentation')!r}")
        if pres:
            cleaned["presentation"] = pres
        transforms: dict[str, Any] = {}
        raw_xf = entry.get("transforms")
        if raw_xf is None and entry.get("worldTransform") is not None:
            # tolerate mixed files
            transforms["world"] = validate_transform(entry["worldTransform"])
        elif raw_xf is not None:
            if not isinstance(raw_xf, dict):
                raise SpatialStateError(f"transforms must be object for {did}")
            for k, v in raw_xf.items():
                nk = normalize_presentation(k)
                if nk is None:
                    raise SpatialStateError(f"bad transform key {k!r} for {did}")
                if v is not None:
                    transforms[nk] = validate_transform(v)
        if transforms:
            cleaned["transforms"] = transforms
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
    """Atomic write of validated spatial state (always schema v2)."""
    path = path or DEFAULT_PATH
    cleaned = validate_state(state)
    cleaned["version"] = SCHEMA_VERSION
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(cleaned, indent=2, sort_keys=True) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=".spatial-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        # Best-effort directory fsync for reboot durability
        try:
            dir_fd = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def merge_display_entry(
    state: dict[str, Any],
    display_id: str,
    *,
    presentation: str | None = None,
    transforms_update: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge one display into state without dropping other displays' data."""
    if not display_id.startswith("display-"):
        raise SpatialStateError(f"invalid display id: {display_id!r}")
    displays = dict(state.get("displays") or {})
    entry = dict(displays.get(display_id) or {})
    transforms = dict(entry.get("transforms") or {})
    if transforms_update:
        for k, v in transforms_update.items():
            nk = normalize_presentation(k)
            if nk is None:
                raise SpatialStateError(f"bad transform key {k!r}")
            if v is None:
                continue
            transforms[nk] = validate_transform(v)
    if presentation is not None:
        np = normalize_presentation(presentation)
        if np is None:
            raise SpatialStateError(f"bad presentation: {presentation!r}")
        entry["presentation"] = np
    if transforms:
        entry["transforms"] = transforms
    # drop legacy key if present
    entry.pop("worldTransform", None)
    displays[display_id] = entry
    return {"version": SCHEMA_VERSION, "displays": displays}


def set_display_world(
    display_id: str,
    transform: dict[str, Any],
    *,
    presentation: str = "world",
    path: Path | None = None,
) -> dict[str, Any]:
    """Backward-compatible helper: set world transform + presentation."""
    state = load_or_default(path)
    state = merge_display_entry(
        state,
        display_id,
        presentation=presentation,
        transforms_update={"world": transform},
    )
    save(state, path)
    return deepcopy(state)


def get_display(display_id: str, path: Path | None = None) -> dict[str, Any] | None:
    state = load_or_default(path)
    return deepcopy(state["displays"].get(display_id))


def get_transform(entry: dict[str, Any] | None, presentation: str) -> dict[str, Any] | None:
    if not entry:
        return None
    nk = normalize_presentation(presentation)
    if not nk:
        return None
    transforms = entry.get("transforms") or {}
    xf = transforms.get(nk)
    if xf is None and nk == "world" and entry.get("worldTransform"):
        xf = entry["worldTransform"]
    return deepcopy(xf) if xf else None
