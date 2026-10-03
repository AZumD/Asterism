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
            # Durable immediately — do not wait for the full loop (TimeoutStopSec).
            try:
                save(working, path)
                r["saved"] = True
            except Exception as e:  # noqa: BLE001
                r["saved"] = False
                r["save_error"] = str(e)
                out = {
                    "ok": False,
                    "error": f"atomic save failed after {did}: {e}",
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


def _http_action(http: str, action: str) -> dict[str, Any]:
    """POST /show or /hide on asterism-dashboard (visibility/materialization)."""
    try:
        return _post_json(f"{http.rstrip('/')}/{action}", {}, timeout=5.0)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
        return {"ok": False, "error": str(e)}


def _wait_presentation(
    overlay_key: str,
    want: str,
    *,
    http: str,
    timeout: float = 8.0,
) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: dict[str, Any] = {}
    while time.time() < deadline:
        try:
            cap = _result(
                dashmgr_request("capture", http=http, overlay_key=overlay_key, wait=6.0)
            )
            got = normalize_presentation(
                (cap.get("capture") or {}).get("dockLocationName")
            )
            last = {"ok": cap.get("ok"), "dockLocationName": got}
            if got == want:
                return {"ok": True, "presentation": got, "last": last}
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = {"error": str(e)}
        time.sleep(0.25)
    return {"ok": False, "error": f"timeout waiting for {want}", "last": last}


def _transforms_match(a: Any, b: Any, *, eps: float = 1e-3) -> bool:
    """Compare validated World transforms (translation + rotation)."""
    try:
        va = validate_transform(a)
        vb = validate_transform(b)
    except Exception:
        return False
    ta, tb = va["translation"], vb["translation"]
    for k in ("x", "y", "z"):
        if abs(float(ta[k]) - float(tb[k])) > eps:
            return False
    ra, rb = va["rotation"], vb["rotation"]
    for k in ("w", "x", "y", "z"):
        if abs(float(ra[k]) - float(rb[k])) > eps:
            return False
    return True


def _wait_world_ready(
    overlay_key: str,
    *,
    http: str,
    timeout: float = 25.0,
) -> dict[str, Any]:
    """Wait until dockLocation==World AND a weak-mounted UndockedOverlay exists.

    Nullish xfTransform is OK — cold World mount often has state.xfTransform
    undefined until initialized. Strict find-live-uo is not used for readiness.
    """
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
                weak = _result(
                    dashmgr_request(
                        "inspect-undocked-instance",
                        http=http,
                        overlay_key=overlay_key,
                        wait=8.0,
                    )
                )
                count = int(weak.get("candidateCount") or 0)
                target = weak.get("targetFrameID")
                cands = weak.get("candidates") or []
                unique_ok = count == 1 or (
                    count >= 1
                    and target is not None
                    and all(str(c.get("frameID")) == str(target) for c in cands)
                )
                last["mounted"] = {
                    "ok": weak.get("ok"),
                    "candidateCount": count,
                    "targetFrameID": target,
                    "unique_ok": unique_ok,
                    "xfTransformNullish": (cands[0].get("xfTransformNullish") if cands else None),
                }
                if weak.get("ok") and count >= 1 and unique_ok:
                    return {"ok": True, "ready": True, "last": last}
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last["error"] = str(e)
        time.sleep(0.4)
    return {
        "ok": False,
        "ready": False,
        "last": last,
        "error": "timeout waiting for World+mounted UndockedOverlay",
    }


def _restore_world(
    overlay_key: str,
    entry: dict[str, Any],
    *,
    http: str,
    allow_hand_fallback: bool = False,
) -> dict[str, Any]:
    """World restore via Dashboard materialization then fiber direct-restore.

    Valve mounts UndockedOverlay only after a real Dashboard→World transition
    while the dashboard is shown. map[World] alone is not enough.
    """
    out: dict[str, Any] = {
        "overlay_key": overlay_key,
        "saved_presentation": "world",
        "path": "world-materialization",
        "materialization": {},
    }
    mat: dict[str, Any] = out["materialization"]
    showed = False
    world_xf = get_transform(entry, "world")

    def _cleanup_hide() -> None:
        if not showed:
            return
        hide = _http_action(http, "hide")
        mat["hide"] = {"ok": hide.get("ok"), "error": hide.get("error")}

    # 1) Seed remembered World map when we have a transform
    if world_xf:
        try:
            seed = _result(
                dashmgr_request(
                    "seed-presentation-transform",
                    http=http,
                    overlay_key=overlay_key,
                    presentation="world",
                    transform=world_xf,
                    wait=10.0,
                )
            )
            out["seed"] = {"ok": seed.get("ok"), "error": seed.get("error")}
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            out["seed"] = {"ok": False, "error": str(e)}

    # 2–3) WORLD MATERIALIZATION: Dashboard + show
    try:
        dash = _result(
            dashmgr_request(
                "set-presentation",
                http=http,
                overlay_key=overlay_key,
                mode="dashboard",
                wait=12.0,
            )
        )
        mat["dashboard"] = {
            "ok": dash.get("ok"),
            "path": dash.get("path"),
            "error": dash.get("error"),
        }
        if not dash.get("ok"):
            out["ok"] = False
            out["error"] = dash.get("error") or "materialization set-dashboard failed"
            return out
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        out["ok"] = False
        out["error"] = str(e)
        mat["dashboard"] = {"ok": False, "error": str(e)}
        return out

    show = _http_action(http, "show")
    mat["show"] = {"ok": show.get("ok"), "error": show.get("error")}
    showed = True
    # Brief wait so dashboard scene is active (optional observability)
    mat["dashboard_ready"] = _wait_presentation(
        overlay_key, "dashboard", http=http, timeout=5.0
    )
    time.sleep(0.5)

    # 4) Transition to World (mounts UndockedOverlay)
    try:
        world_set = _result(
            dashmgr_request(
                "set-presentation",
                http=http,
                overlay_key=overlay_key,
                mode="world",
                wait=12.0,
            )
        )
        mat["world"] = {
            "ok": world_set.get("ok"),
            "path": world_set.get("path"),
            "error": world_set.get("error"),
        }
        if not world_set.get("ok"):
            out["ok"] = False
            out["error"] = world_set.get("error") or "materialization set-world failed"
            _cleanup_hide()
            return out
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        out["ok"] = False
        out["error"] = str(e)
        mat["world"] = {"ok": False, "error": str(e)}
        _cleanup_hide()
        return out

    # 5) Wait for World + weak-mounted UndockedOverlay (xf may still be null)
    ready = _wait_world_ready(overlay_key, http=http)
    mat["live_ready"] = bool(ready.get("ok"))
    mat["live_wait"] = {
        "ok": ready.get("ok"),
        "error": ready.get("error"),
        "last": ready.get("last"),
    }
    if not ready.get("ok"):
        if allow_hand_fallback and world_xf:
            try:
                hand = _result(
                    dashmgr_request(
                        "restore-via-hand",
                        http=http,
                        overlay_key=overlay_key,
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
            _cleanup_hide()
            return out
        out["ok"] = False
        out["error"] = ready.get("error") or "World mounted instance not ready"
        _cleanup_hide()
        return out

    # 6) Direct restore only when Asterism has a saved World transform P.
    #    Without P: do not invent a pose; materialization alone is enough.
    if not world_xf:
        out["ok"] = True
        out["note"] = (
            "no saved world transform; materialization only "
            "(weak mount may still have nullish xfTransform)"
        )
        _cleanup_hide()
        return out

    try:
        direct = _result(
            dashmgr_request(
                "direct-restore",
                http=http,
                overlay_key=overlay_key,
                transform=world_xf,
                wait=15.0,
            )
        )
        out["direct"] = {
            "ok": direct.get("ok"),
            "path": direct.get("path"),
            "error": direct.get("error"),
            "instanceFound": direct.get("instanceFound"),
            "liveInstanceFound": direct.get("liveInstanceFound"),
            "previousXfTransformNullish": direct.get("previousXfTransformNullish"),
            "initializedFromNull": direct.get("initializedFromNull"),
        }
        if not direct.get("ok"):
            out["ok"] = False
            out["error"] = direct.get("error") or "direct-restore failed"
            _cleanup_hide()
            return out
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        out["ok"] = False
        out["error"] = str(e)
        _cleanup_hide()
        return out

    # 7) Strict verify live P before hide
    verify = _wait_live_world_match(overlay_key, world_xf, http=http)
    out["verify"] = {
        "ok": verify.get("ok"),
        "error": verify.get("error"),
        "last": verify.get("last"),
        "expected": verify.get("expected"),
        "actual": verify.get("actual"),
    }
    if not verify.get("ok"):
        out["ok"] = False
        out["error"] = verify.get("error") or "live xf mismatch after direct-restore"
        _cleanup_hide()
        return out

    # 8) Suppress Valve post-float nudge before hide (exact World restore only)
    try:
        cleared = _result(
            dashmgr_request(
                "clear-just-floated",
                http=http,
                overlay_key=overlay_key,
                wait=10.0,
            )
        )
        out["clear_just_floated"] = {
            "ok": cleared.get("ok"),
            "before": cleared.get("before"),
            "after": cleared.get("after"),
            "frameID": cleared.get("frameID"),
            "error": cleared.get("error"),
        }
        if not cleared.get("ok"):
            out["ok"] = False
            out["error"] = cleared.get("error") or "clear-just-floated failed"
            _cleanup_hide()
            return out
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        out["ok"] = False
        out["error"] = str(e)
        out["clear_just_floated"] = {"ok": False, "error": str(e)}
        _cleanup_hide()
        return out

    # 9) Hide, then strict-verify P again (nudge would show up here if flag uncleared)
    _cleanup_hide()
    verify_after = _wait_live_world_match(overlay_key, world_xf, http=http)
    out["verify_after_hide"] = {
        "ok": verify_after.get("ok"),
        "error": verify_after.get("error"),
        "last": verify_after.get("last"),
        "expected": verify_after.get("expected"),
        "actual": verify_after.get("actual"),
    }
    out["ok"] = bool(verify_after.get("ok"))
    if out["ok"]:
        out["path"] = "world-materialization+direct-restore"
    else:
        out["error"] = (
            verify_after.get("error")
            or "live xf mismatch after hide (Valve float nudge?)"
        )
    return out


def _wait_live_world_match(
    overlay_key: str,
    expected: dict[str, Any],
    *,
    http: str,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Bounded poll of strict get-live-world until xf matches expected P."""
    deadline = time.time() + timeout
    last: dict[str, Any] = {}
    last_xf: Any = None
    while time.time() < deadline:
        try:
            live = _result(
                dashmgr_request(
                    "get-live-world",
                    http=http,
                    overlay_key=overlay_key,
                    wait=8.0,
                )
            )
            live_xf = live.get("xfTransform")
            last_xf = live_xf
            last = {
                "ok": live.get("ok"),
                "path": live.get("path"),
                "error": live.get("error"),
                "has_xf": live_xf is not None,
            }
            if live.get("ok") and live_xf and _transforms_match(live_xf, expected):
                return {
                    "ok": True,
                    "last": last,
                    "xfTransform": live_xf,
                    "expected": expected,
                    "actual": live_xf,
                }
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = {"error": str(e)}
        time.sleep(0.25)
    return {
        "ok": False,
        "last": last,
        "expected": expected,
        "actual": last_xf,
        "error": last.get("error") or "timeout waiting for get-live-world match",
    }


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

    # World needs Dashboard materialization — separate path.
    if presentation == "world":
        world_out = _restore_world(
            key, entry, http=http, allow_hand_fallback=allow_hand_fallback
        )
        world_out["display_id"] = display_id
        return world_out

    # Dashboard / Theater: seed (if any) + direct set-presentation. No materialization.
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
