#!/usr/bin/env python3
"""Startup / explicit restore orchestration for Asterism spatial state.

Does not race Frame creation: callers must wait for WS + overlays first.
Direct restore is preferred; restore-via-hand is diagnostic fallback only.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from spatial.display_map import map_displays_to_overlays, overlay_key_for_display
from spatial.spatial_state import (
    SpatialStateError,
    get_display,
    load_or_default,
    set_display_world,
    validate_transform,
)

HTTP_DEFAULT = "http://127.0.0.1:47831"


def _post_json(url: str, body: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def wait_for_ws(
    http: str = HTTP_DEFAULT,
    *,
    timeout: float = 60.0,
    poll: float = 0.5,
) -> bool:
    """Wait until asterism-dashboard reports a connected shell WebSocket."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{http}/status", timeout=3) as resp:
                st = json.loads(resp.read().decode("utf-8"))
            if st.get("dashmgr_ws_connected") or st.get("dashmgr", {}).get("ws_connected"):
                return True
            # tolerate flat / nested status shapes
            if st.get("ok") and st.get("ws_connected"):
                return True
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            pass
        time.sleep(poll)
    return False


def dashmgr_request(
    cmd: str,
    *,
    http: str = HTTP_DEFAULT,
    wait: float = 12.0,
    **fields: Any,
) -> dict[str, Any]:
    body = {"cmd": cmd, "wait": wait, **fields}
    return _post_json(f"{http}/dashmgr/request", body, timeout=wait + 5)


def load_transform_file(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        xf = json.load(f)
    if isinstance(xf, dict) and xf.get("world"):
        xf = xf["world"]
    elif isinstance(xf, dict) and xf.get("transform"):
        xf = xf["transform"]
    elif isinstance(xf, dict) and xf.get("capture"):
        rem = (xf.get("capture") or {}).get("rememberedTransforms") or {}
        xf = rem.get("World") or xf
    return validate_transform(xf)


def save_display_from_capture(
    display_id: str,
    *,
    http: str = HTTP_DEFAULT,
    keys: list[str] | None = None,
) -> dict[str, Any]:
    key = overlay_key_for_display(display_id, keys=keys)
    if not key:
        return {"ok": False, "error": f"no runtime overlay for {display_id}"}
    cap = dashmgr_request("capture", http=http, overlay_key=key)
    result = cap.get("result") or cap
    if not result.get("ok"):
        return {"ok": False, "error": "capture failed", "capture": result, "overlay_key": key}
    world = result.get("world")
    if not world:
        return {
            "ok": False,
            "error": "no remembered World transform",
            "overlay_key": key,
            "capture": result,
        }
    state = set_display_world(display_id, world, presentation="world")
    return {
        "ok": True,
        "display_id": display_id,
        "overlay_key": key,
        "worldTransform": world,
        "state": state,
    }


def restore_display(
    display_id: str,
    *,
    http: str = HTTP_DEFAULT,
    keys: list[str] | None = None,
    prefer_direct: bool = True,
    allow_hand_fallback: bool = False,
    transform: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Restore one stable display. Missing Frame must not raise."""
    key = overlay_key_for_display(display_id, keys=keys)
    if not key:
        return {
            "ok": False,
            "skipped": True,
            "error": f"no runtime overlay for {display_id}",
            "display_id": display_id,
        }
    if transform is None:
        entry = get_display(display_id)
        if not entry or not entry.get("worldTransform"):
            return {
                "ok": False,
                "skipped": True,
                "error": f"no saved worldTransform for {display_id}",
                "display_id": display_id,
                "overlay_key": key,
            }
        transform = entry["worldTransform"]
    else:
        transform = validate_transform(transform)

    out: dict[str, Any] = {
        "display_id": display_id,
        "overlay_key": key,
        "transform": transform,
    }

    if prefer_direct:
        try:
            direct = dashmgr_request(
                "direct-restore",
                http=http,
                overlay_key=key,
                transform=transform,
            )
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            direct = {"ok": False, "error": str(e)}
        result = direct.get("result") or direct
        out["direct"] = result
        if result.get("ok"):
            out["ok"] = True
            out["path"] = result.get("path") or "direct-restore"
            return out
        if not allow_hand_fallback:
            out["ok"] = False
            out["error"] = result.get("error") or "direct-restore failed"
            return out

    try:
        hand = dashmgr_request(
            "restore-via-hand",
            http=http,
            overlay_key=key,
            transform=transform,
            wait=20.0,
        )
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        hand = {"ok": False, "error": str(e)}
    result = hand.get("result") or hand
    out["hand"] = result
    out["ok"] = bool(result.get("ok"))
    out["path"] = "restore-via-hand"
    if not out["ok"]:
        out["error"] = result.get("error") or "restore-via-hand failed"
    return out


def restore_all(
    *,
    http: str = HTTP_DEFAULT,
    keys: list[str] | None = None,
    prefer_direct: bool = True,
    allow_hand_fallback: bool = False,
    wait_ws: bool = True,
) -> dict[str, Any]:
    """Idempotent multi-display restore. One missing Frame does not abort others."""
    if wait_ws and not wait_for_ws(http):
        return {"ok": False, "error": "WebSocket shell bridge not connected"}
    state = load_or_default()
    mapping = map_displays_to_overlays(keys=keys)
    results = []
    for row in mapping:
        did = row.get("display_id")
        if not did:
            continue
        entry = state["displays"].get(did)
        if not entry or not entry.get("worldTransform"):
            results.append(
                {
                    "ok": True,
                    "skipped": True,
                    "display_id": did,
                    "reason": "no saved pose",
                    "overlay_key": row.get("overlay_key"),
                }
            )
            continue
        if not row.get("overlay_key"):
            results.append(
                {
                    "ok": False,
                    "skipped": True,
                    "display_id": did,
                    "error": "runtime overlay missing",
                }
            )
            continue
        try:
            results.append(
                restore_display(
                    did,
                    http=http,
                    keys=keys,
                    prefer_direct=prefer_direct,
                    allow_hand_fallback=allow_hand_fallback,
                    transform=entry["worldTransform"],
                )
            )
        except SpatialStateError as e:
            results.append(
                {
                    "ok": False,
                    "skipped": True,
                    "display_id": did,
                    "error": f"corrupt pose: {e}",
                }
            )
        except Exception as e:  # noqa: BLE001 — isolate per display
            results.append(
                {
                    "ok": False,
                    "skipped": True,
                    "display_id": did,
                    "error": str(e),
                }
            )
    ok = all(r.get("ok") or r.get("skipped") for r in results)
    return {"ok": ok, "mapping": mapping, "results": results}


def mapping_debug(*, keys: list[str] | None = None) -> list[dict[str, Any]]:
    return map_displays_to_overlays(keys=keys)
