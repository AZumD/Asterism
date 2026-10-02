#!/usr/bin/env python3
"""Stable Asterism display-N ↔ runtime Gamescope overlay key mapping."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _ensure_paths() -> None:
    for p in (ROOT / "display", ROOT / "layout", ROOT):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)


def enabled_displays() -> list[dict[str, Any]]:
    _ensure_paths()
    from displays import load as load_displays  # noqa: WPS433

    cfg = load_displays()
    return [d for d in cfg.get("displays", []) if d.get("enabled", True)]


def runtime_keys() -> list[str]:
    _ensure_paths()
    from layout import screen_keys  # noqa: WPS433

    return screen_keys()


def map_displays_to_overlays(
    *,
    keys: list[str] | None = None,
    displays: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Positional map: Nth enabled display ↔ Nth PerWindow key.

    Runtime keys like asterism.desktop.app.2 are NOT stable identities.
    Pass keys= explicitly in unit tests (avoids vrcmd).
    """
    disp = displays if displays is not None else enabled_displays()
    runtime = keys if keys is not None else runtime_keys()
    out: list[dict[str, Any]] = []
    for i, d in enumerate(disp):
        did = d.get("id") or f"display-{i + 1}"
        key = runtime[i] if i < len(runtime) else None
        out.append(
            {
                "display_id": did,
                "overlay_key": key,
                "index": i,
                "enabled": True,
                "primary": bool(d.get("primary")),
            }
        )
    for j in range(len(disp), len(runtime)):
        out.append(
            {
                "display_id": None,
                "overlay_key": runtime[j],
                "index": j,
                "enabled": False,
                "orphan_runtime": True,
            }
        )
    return out


def overlay_key_for_display(
    display_id: str,
    *,
    keys: list[str] | None = None,
    displays: list[dict[str, Any]] | None = None,
) -> str | None:
    for row in map_displays_to_overlays(keys=keys, displays=displays):
        if row.get("display_id") == display_id:
            return row.get("overlay_key")
    return None


def display_id_for_overlay(
    overlay_key: str,
    *,
    keys: list[str] | None = None,
    displays: list[dict[str, Any]] | None = None,
) -> str | None:
    for row in map_displays_to_overlays(keys=keys, displays=displays):
        if row.get("overlay_key") == overlay_key:
            return row.get("display_id")
    return None
