#!/usr/bin/env python3
"""Spatial snapshot / restore orchestration (presentation-first, fiber World pose)."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from copy import deepcopy
from pathlib import Path
from typing import Any

from spatial.display_map import map_displays_to_overlays, overlay_key_for_display
from spatial.spatial_state import (
    DEFAULT_PATH,
    SpatialStateError,
    get_display,
    get_transform,
    load_or_default,
    merge_display_entry,
    normalize_presentation,
    save,
    validate_transform,
)

HTTP_DEFAULT = "http://127.0.0.1:47831"
STATE_DIR = Path(
    os.environ.get(
        "ASTERISM_STATE_DIR",
        Path.home() / ".local/state/asterism",
    )
)
LAST_RESTORE_PATH = STATE_DIR / "spatial-last-restore.json"
LAST_SNAPSHOT_PATH = STATE_DIR / "spatial-last-snapshot.json"

# Valve Title Case rememberedTransforms keys -> schema keys
REMEMBERED_KEY_MAP = {
    "Dashboard": "dashboard",
    "World": "world",
    "Theater": "theater",
    "LeftHand": "lefthand",
    "RightHand": "righthand",
}


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


def _write_diag(path: Path, payload: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def wait_for_ws(
    http: str = HTTP_DEFAULT,
    *,
    timeout: float = 90.0,
    poll: float = 0.5,
) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{http}/status", timeout=3) as resp:
                st = json.loads(resp.read().decode("utf-8"))
            if st.get("dashmgr_ws_connected") or st.get("dashmgr", {}).get("ws_connected"):
                return True
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


def _result(resp: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(resp, dict):
        return {"ok": False, "error": "bad response"}
    if "result" in resp and isinstance(resp["result"], dict):
        return resp["result"]
    return resp


def load_transform_file(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        xf = json.load(f)
    if isinstance(xf, dict) and xf.get("world"):
        xf = xf["world"]
    elif isinstance(xf, dict) and xf.get("transform"):
        xf = xf["transform"]
    elif isinstance(xf, dict) and xf.get("xfTransform"):
        xf = xf["xfTransform"]
    elif isinstance(xf, dict) and xf.get("capture"):
        rem = (xf.get("capture") or {}).get("rememberedTransforms") or {}
        xf = rem.get("World") or xf
    return validate_transform(xf)


def _remembered_to_schema(rem: dict[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not isinstance(rem, dict):
        return out
    for k, v in rem.items():
        nk = REMEMBERED_KEY_MAP.get(k) or normalize_presentation(k)
        if not nk or v is None:
            continue
        try:
            out[nk] = validate_transform(v)
        except SpatialStateError:
            continue
    return out


def snapshot_display(
    display_id: str,
    *,
    http: str = HTTP_DEFAULT,
    keys: list[str] | None = None,
    path: Path | None = None,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Snapshot one display into spatial-state. Does not wipe peers on failure."""
    key = overlay_key_for_display(display_id, keys=keys)
    if not key:
        return {
            "ok": False,
            "skipped": True,
            "display_id": display_id,
            "error": "no runtime overlay",
        }
    try:
        cap_resp = dashmgr_request("capture", http=http, overlay_key=key, wait=10.0)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return {
            "ok": False,
            "display_id": display_id,
            "overlay_key": key,
            "error": f"capture request failed: {e}",
        }
    cap = _result(cap_resp)
    if not cap.get("ok"):
        return {
            "ok": False,
            "display_id": display_id,
            "overlay_key": key,
            "error": cap.get("error") or "capture failed",
            "capture": cap,
        }

    snap = cap.get("capture") or {}
    pres = normalize_presentation(snap.get("dockLocationName"))
    transforms_update = _remembered_to_schema(snap.get("rememberedTransforms"))

    live_used = False
    if pres == "world":
        try:
            live_resp = dashmgr_request(
                "get-live-world", http=http, overlay_key=key, wait=10.0
            )
            live = _result(live_resp)
            if live.get("ok") and live.get("xfTransform"):
                transforms_update["world"] = validate_transform(live["xfTransform"])
                live_used = True
        except (urllib.error.URLError, TimeoutError, OSError, SpatialStateError):
            pass

    if not transforms_update and not pres:
        return {
            "ok": False,
            "display_id": display_id,
            "overlay_key": key,
            "error": "nothing to save",
            "capture": snap,
        }

    try:
        cur = state if state is not None else load_or_default(path)
        merged = merge_display_entry(
            cur,
            display_id,
            presentation=pres,
            transforms_update=transforms_update or None,
        )
        if state is not None:
            # caller owns atomic multi-display save
            state.clear()
            state.update(merged)
        else:
            save(merged, path)
    except SpatialStateError as e:
        return {
            "ok": False,
            "display_id": display_id,
            "overlay_key": key,
            "error": f"state merge failed: {e}",
        }

    return {
        "ok": True,
        "display_id": display_id,
        "overlay_key": key,
        "presentation": pres,
        "transforms_saved": sorted(transforms_update.keys()),
        "live_world_used": live_used,
        "frameID": snap.get("frameID"),
    }


def snapshot_all(
    *,
    http: str = HTTP_DEFAULT,
    keys: list[str] | None = None,
    path: Path | None = None,
    wait_ws: bool = True,
    ws_timeout: float = 15.0,
) -> dict[str, Any]:
    """Best-effort snapshot of all mapped displays. Partial failures keep prior state."""
    t0 = time.time()
    if wait_ws and not wait_for_ws(http, timeout=ws_timeout):
        out = {"ok": False, "error": "WebSocket shell bridge not connected", "results": []}
        _write_diag(LAST_SNAPSHOT_PATH, out)
        return out

    # Start from existing valid state so one failure cannot wipe peers
    base = load_or_default(path)
    working = deepcopy(base)
    mapping = map_displays_to_overlays(keys=keys)
    results = []
    any_ok = False
    for row in mapping:
        did = row.get("display_id")
        if not did:
            continue
        try:
            r = snapshot_display(
                did, http=http, keys=keys, path=path, state=working
            )
        except Exception as e:  # noqa: BLE001
            r = {"ok": False, "display_id": did, "error": str(e)}
        results.append(r)
        if r.get("ok"):
            any_ok = True

    if any_ok:
        try:
            save(working, path)
        except Exception as e:  # noqa: BLE001
            out = {
                "ok": False,
                "error": f"atomic save failed: {e}",
                "results": results,
                "elapsed_s": time.time() - t0,
            }
            _write_diag(LAST_SNAPSHOT_PATH, out)
            return out

    ok = any_ok or all(r.get("skipped") for r in results)
    out = {
        "ok": ok,
        "results": results,
        "mapping": mapping,
        "elapsed_s": round(time.time() - t0, 3),
        "path": str(path or DEFAULT_PATH),
    }
    _write_diag(LAST_SNAPSHOT_PATH, out)
    return out


def _wait_world_ready(
    overlay_key: str,
    *,
    http: str,
    timeout: float = 25.0,
) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: dict[str, Any] = {}
    while time.time() < deadline:
        try:
            cap = _result(
                dashmgr_request("capture", http=http, overlay_key=overlay_key, wait=8.0)
            )
            last["capture"] = {
                "ok": cap.get("ok"),
                "dockLocationName": (cap.get("capture") or {}).get("dockLocationName"),
            }
            pres = normalize_presentation(
                (cap.get("capture") or {}).get("dockLocationName")
            )
            if pres == "world":
                find = _result(
                    dashmgr_request(
                        "find-live-uo", http=http, overlay_key=overlay_key, wait=8.0
                    )
                )
                last["find"] = {
                    "ok": find.get("ok"),
                    "live": find.get("live"),
                }
                if find.get("ok") or (find.get("live") or {}).get("found"):
                    return {"ok": True, "ready": True, "last": last}
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last["error"] = str(e)
        time.sleep(0.4)
    return {"ok": False, "ready": False, "last": last, "error": "timeout waiting for World+UO"}


def restore_display(
    display_id: str,
    *,
    http: str = HTTP_DEFAULT,
    keys: list[str] | None = None,
    allow_hand_fallback: bool = False,
    path: Path | None = None,
) -> dict[str, Any]:
    """Restore saved presentation (+ World pose when applicable). No hand fallback by default."""
    key = overlay_key_for_display(display_id, keys=keys)
    if not key:
        return {
            "ok": False,
            "skipped": True,
            "display_id": display_id,
            "error": "no runtime overlay",
        }
    entry = get_display(display_id, path)
    if not entry or not entry.get("presentation"):
        return {
            "ok": True,
            "skipped": True,
            "display_id": display_id,
            "overlay_key": key,
            "reason": "no saved presentation",
        }

    presentation = normalize_presentation(entry.get("presentation"))
    out: dict[str, Any] = {
        "display_id": display_id,
        "overlay_key": key,
        "saved_presentation": presentation,
    }
    if presentation is None:
        out["ok"] = True
        out["skipped"] = True
        out["reason"] = "unsupported presentation"
        return out

    # Seed remembered map for this presentation when we have a transform
    xf = get_transform(entry, presentation)
    if xf:
        try:
            seed = _result(
                dashmgr_request(
                    "seed-presentation-transform",
                    http=http,
                    overlay_key=key,
                    presentation=presentation,
                    transform=xf,
                    wait=10.0,
                )
            )
            out["seed"] = {"ok": seed.get("ok"), "error": seed.get("error")}
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            out["seed"] = {"ok": False, "error": str(e)}

    # Set presentation (no theater->dashboard->world dance)
    try:
        setp = _result(
            dashmgr_request(
                "set-presentation",
                http=http,
                overlay_key=key,
                mode=presentation,
                wait=12.0,
            )
        )
        out["set_presentation"] = {
            "ok": setp.get("ok"),
            "path": setp.get("path"),
            "error": setp.get("error"),
        }
        if not setp.get("ok"):
            out["ok"] = False
            out["error"] = setp.get("error") or "set-presentation failed"
            return out
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        out["ok"] = False
        out["error"] = str(e)
        return out

    if presentation != "world":
        # Validate capture reports expected presentation
        try:
            cap = _result(
                dashmgr_request("capture", http=http, overlay_key=key, wait=8.0)
            )
            got = normalize_presentation(
                (cap.get("capture") or {}).get("dockLocationName")
            )
            out["capture_presentation"] = got
            out["ok"] = got == presentation
            if not out["ok"]:
                out["error"] = f"expected {presentation}, got {got}"
            out["path"] = f"set-presentation:{presentation}"
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            out["ok"] = False
            out["error"] = str(e)
        return out

    # World: wait for live UO then direct-restore
    world_xf = get_transform(entry, "world")
    if not world_xf:
        out["ok"] = True
        out["path"] = "set-presentation:world"
        out["note"] = "no saved world transform; presentation only"
        return out

    ready = _wait_world_ready(key, http=http)
    out["wait_world"] = {
        "ok": ready.get("ok"),
        "error": ready.get("error"),
        "last": ready.get("last"),
    }
    if not ready.get("ok"):
        if allow_hand_fallback:
            try:
                hand = _result(
                    dashmgr_request(
                        "restore-via-hand",
                        http=http,
                        overlay_key=key,
                        transform=world_xf,
                        wait=20.0,
                    )
                )
                out["hand"] = hand
                out["ok"] = bool(hand.get("ok"))
                out["path"] = "restore-via-hand"
                if not out["ok"]:
                    out["error"] = hand.get("error") or "hand fallback failed"
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                out["ok"] = False
                out["error"] = str(e)
                out["path"] = "restore-via-hand"
            return out
        out["ok"] = False
        out["error"] = ready.get("error") or "World live instance not ready"
        out["path"] = "set-presentation:world"
        return out

    try:
        direct = _result(
            dashmgr_request(
                "direct-restore",
                http=http,
                overlay_key=key,
                transform=world_xf,
                wait=15.0,
            )
        )
        out["direct"] = {
            "ok": direct.get("ok"),
            "path": direct.get("path"),
            "error": direct.get("error"),
            "liveInstanceFound": direct.get("liveInstanceFound"),
        }
        out["ok"] = bool(direct.get("ok"))
        out["path"] = direct.get("path") or "react-fiber-setState+map"
        if not out["ok"]:
            out["error"] = direct.get("error") or "direct-restore failed"
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        out["ok"] = False
        out["error"] = str(e)
        out["path"] = "direct-restore"
    return out


def restore_all(
    *,
    http: str = HTTP_DEFAULT,
    keys: list[str] | None = None,
    allow_hand_fallback: bool = False,
    wait_ws: bool = True,
    ws_timeout: float = 90.0,
    wait_overlays: float = 45.0,
    path: Path | None = None,
) -> dict[str, Any]:
    """Idempotent multi-display restore. Normal startup: allow_hand_fallback=False."""
    t0 = time.time()
    if wait_ws and not wait_for_ws(http, timeout=ws_timeout):
        out = {"ok": False, "error": "WebSocket shell bridge not connected", "results": []}
        _write_diag(LAST_RESTORE_PATH, out)
        return out

    # Wait until at least one runtime overlay key exists (Frames may lag WS)
    deadline = time.time() + wait_overlays
    mapping = map_displays_to_overlays(keys=keys)
    while time.time() < deadline:
        mapping = map_displays_to_overlays(keys=keys)
        if any(r.get("display_id") and r.get("overlay_key") for r in mapping):
            break
        time.sleep(0.5)

    state = load_or_default(path)
    results = []
    for row in mapping:
        did = row.get("display_id")
        if not did:
            continue
        if did not in state.get("displays", {}):
            results.append(
                {
                    "ok": True,
                    "skipped": True,
                    "display_id": did,
                    "overlay_key": row.get("overlay_key"),
                    "reason": "no saved state",
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
                    allow_hand_fallback=allow_hand_fallback,
                    path=path,
                )
            )
        except Exception as e:  # noqa: BLE001
            results.append(
                {
                    "ok": False,
                    "skipped": True,
                    "display_id": did,
                    "error": str(e),
                }
            )

    ok = all(r.get("ok") or r.get("skipped") for r in results)
    out = {
        "ok": ok,
        "results": results,
        "mapping": mapping,
        "elapsed_s": round(time.time() - t0, 3),
        "allow_hand_fallback": allow_hand_fallback,
    }
    _write_diag(LAST_RESTORE_PATH, out)
    return out


# Legacy alias used by older CLI
def save_display_from_capture(
    display_id: str,
    *,
    http: str = HTTP_DEFAULT,
    keys: list[str] | None = None,
) -> dict[str, Any]:
    return snapshot_display(display_id, http=http, keys=keys)


def mapping_debug(*, keys: list[str] | None = None) -> list[dict[str, Any]]:
    return map_displays_to_overlays(keys=keys)


def status_report(
    *,
    http: str = HTTP_DEFAULT,
    keys: list[str] | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    path = path or DEFAULT_PATH
    state = load_or_default(path)
    ws = False
    try:
        with urllib.request.urlopen(f"{http}/status", timeout=3) as resp:
            st = json.loads(resp.read().decode("utf-8"))
        ws = bool(st.get("dashmgr_ws_connected"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        pass
    mapping = []
    try:
        mapping = map_displays_to_overlays(keys=keys)
    except Exception as e:  # noqa: BLE001
        mapping = [{"error": str(e)}]
    last_restore = None
    last_snap = None
    try:
        if LAST_RESTORE_PATH.is_file():
            last_restore = json.loads(LAST_RESTORE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    try:
        if LAST_SNAPSHOT_PATH.is_file():
            last_snap = json.loads(LAST_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    return {
        "ok": True,
        "path": str(path),
        "schema_version": state.get("version"),
        "saved_displays": sorted(state.get("displays", {}).keys()),
        "displays": state.get("displays"),
        "mapping": mapping,
        "ws_connected": ws,
        "last_restore": last_restore,
        "last_snapshot": last_snap,
    }
