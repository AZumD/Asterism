#!/usr/bin/env python3
"""Lifecycle spatial persistence tests (no SteamVR)."""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from spatial.spatial_state import (  # noqa: E402
    SCHEMA_VERSION,
    get_transform,
    load,
    load_or_default,
    migrate_v1_to_v2,
    save,
    set_display_world,
    validate_state,
)
from spatial import restore as restore_mod  # noqa: E402

P = {
    "translation": {"x": 0.9, "y": 1.6, "z": -1.16},
    "rotation": {"w": 0.9, "x": 0.14, "y": -0.4, "z": 0.01},
    "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
}
Q = {
    "translation": {"x": 1.5, "y": 1.2, "z": -2.0},
    "rotation": {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0},
    "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
}


def test_v1_to_v2_migration() -> None:
    v1 = {
        "version": 1,
        "displays": {
            "display-1": {
                "presentation": "world",
                "worldTransform": P,
            }
        },
    }
    v2 = migrate_v1_to_v2(v1)
    assert v2["version"] == 2
    assert "worldTransform" not in v2["displays"]["display-1"]
    assert v2["displays"]["display-1"]["transforms"]["world"]["translation"]["x"] == 0.9
    # load path
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "spatial-state.json"
        path.write_text(json.dumps(v1), encoding="utf-8")
        loaded = load(path)
        assert loaded["version"] == 2
        save(loaded, path)
        again = json.loads(path.read_text(encoding="utf-8"))
        assert again["version"] == 2
        assert "transforms" in again["displays"]["display-1"]
    print("OK v1->v2 migration")


def test_atomic_v2_save() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "spatial-state.json"
        set_display_world("display-1", P, path=path)
        set_display_world("display-2", Q, path=path)
        st = load(path)
        assert st["version"] == SCHEMA_VERSION
        assert get_transform(st["displays"]["display-1"], "world")["translation"]["x"] == 0.9
        assert get_transform(st["displays"]["display-2"], "world")["translation"]["x"] == 1.5
    print("OK atomic v2")


def test_snapshot_prefers_live_world() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "spatial-state.json"
        # Pre-seed stale map value
        set_display_world("display-1", P, path=path)

        def fake_req(cmd, **kw):
            if cmd == "capture":
                return {
                    "ok": True,
                    "result": {
                        "ok": True,
                        "capture": {
                            "frameID": "1",
                            "dockLocationName": "World",
                            "rememberedTransforms": {"World": P},
                        },
                        "world": P,
                    },
                }
            if cmd == "get-live-world":
                return {
                    "ok": True,
                    "result": {"ok": True, "xfTransform": Q},
                }
            raise AssertionError(cmd)

        with mock.patch.object(restore_mod, "dashmgr_request", side_effect=fake_req):
            with mock.patch.object(
                restore_mod, "overlay_key_for_display", return_value="asterism.desktop.app.2"
            ):
                r = restore_mod.snapshot_display("display-1", path=path)
        assert r["ok"] and r["live_world_used"] is True
        st = load(path)
        assert st["displays"]["display-1"]["transforms"]["world"]["translation"]["x"] == 1.5
        assert st["displays"]["display-1"]["presentation"] == "world"
    print("OK snapshot live world")


def test_snapshot_failure_preserves_peers() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "spatial-state.json"
        set_display_world("display-1", P, path=path)
        set_display_world("display-2", Q, path=path)

        def fake_req(cmd, **kw):
            key = kw.get("overlay_key")
            if key == "asterism.desktop.app.2":
                return {"ok": True, "result": {"ok": False, "error": "boom"}}
            if cmd == "capture":
                return {
                    "ok": True,
                    "result": {
                        "ok": True,
                        "capture": {
                            "dockLocationName": "Dashboard",
                            "rememberedTransforms": {},
                        },
                    },
                }
            if cmd == "get-live-world":
                return {"ok": True, "result": {"ok": False}}
            raise AssertionError((cmd, key))

        def fake_map(keys=None, displays=None):
            return [
                {"display_id": "display-1", "overlay_key": "asterism.desktop.app.2"},
                {"display_id": "display-2", "overlay_key": "asterism.desktop.app.3"},
            ]

        with mock.patch.object(restore_mod, "dashmgr_request", side_effect=fake_req):
            with mock.patch.object(restore_mod, "map_displays_to_overlays", side_effect=fake_map):
                with mock.patch.object(
                    restore_mod,
                    "overlay_key_for_display",
                    side_effect=lambda did, keys=None: {
                        "display-1": "asterism.desktop.app.2",
                        "display-2": "asterism.desktop.app.3",
                    }[did],
                ):
                    restore_mod.snapshot_all(path=path, wait_ws=False)
        st = load(path)
        # display-1 must keep prior world P (failed capture must not wipe)
        assert st["displays"]["display-1"]["transforms"]["world"]["translation"]["x"] == 0.9
        assert st["displays"]["display-2"]["presentation"] == "dashboard"
    print("OK snapshot peer preserve")


def _lc_result(
    *,
    just_floated: bool = False,
    panel=None,
    scale: float = 1.0,
    dragged: bool = False,
    xf=None,
):
    if panel is None:
        panel = {"x": 0.0, "y": 0.0, "z": 0.0}
    return {
        "ok": True,
        "result": {
            "ok": True,
            "frameID": "42",
            "dockLocationName": "World",
            "justFloatedFromDashboard": just_floated,
            "isActiveDashboardFrame": False,
            "panelTranslationForResizeOrigin": panel,
            "scaleForActivePage": scale,
            "beingDragged": dragged,
            "mountedWeak": True,
            "xfTransformNullish": xf is None,
            "xfTransform": xf,
        },
    }


def _patch_clock(tmod):
    clock = {"t": 0.0}
    tmod.time = lambda: clock["t"]
    tmod.sleep = lambda d: clock.__setitem__("t", clock["t"] + float(d))
    return clock


def test_world_restore_stale_flag_consume_then_final() -> None:
    """Stale justFloated=true after hide: settle → clear → settle → final P."""
    calls: list[str] = []
    modes: list[str] = []
    http_actions: list[str] = []
    direct_n = {"n": 0}
    cleared = {"n": 0}
    lc_n = {"n": 0}

    def fake_req(cmd, **kw):
        calls.append(cmd)
        if cmd == "set-presentation":
            modes.append(kw.get("mode"))
            return {"ok": True, "result": {"ok": True}}
        if cmd == "seed-presentation-transform":
            return {"ok": True, "result": {"ok": True}}
        if cmd == "capture":
            name = "World" if "world" in modes else "Dashboard"
            return {
                "ok": True,
                "result": {"ok": True, "capture": {"dockLocationName": name}},
            }
        if cmd == "inspect-undocked-instance":
            return {
                "ok": True,
                "result": {
                    "ok": True,
                    "candidateCount": 1,
                    "targetFrameID": "42",
                    "candidates": [{"frameID": "42", "xfTransformNullish": True}],
                },
            }
        if cmd == "direct-restore":
            direct_n["n"] += 1
            return {
                "ok": True,
                "result": {
                    "ok": True,
                    "instanceFound": True,
                    "initializedFromNull": direct_n["n"] == 1,
                    "previousXfTransformNullish": direct_n["n"] == 1,
                },
            }
        if cmd == "get-live-world":
            return {"ok": True, "result": {"ok": True, "xfTransform": P}}
        if cmd == "inspect-world-lifecycle":
            lc_n["n"] += 1
            # Before clear: stale true. After clear: false.
            floated = cleared["n"] == 0
            return _lc_result(just_floated=floated, xf=P)
        if cmd == "clear-just-floated":
            # Must happen after geometry settle started (lifecycle polls exist)
            assert any(c == "inspect-world-lifecycle" for c in calls[:-1])
            cleared["n"] += 1
            return {
                "ok": True,
                "result": {"ok": True, "before": True, "after": False, "frameID": "42"},
            }
        raise AssertionError(cmd)

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "s.json"
        set_display_world("display-1", P, path=path)
        with mock.patch.object(restore_mod, "dashmgr_request", side_effect=fake_req):
            with mock.patch.object(
                restore_mod,
                "_http_action",
                side_effect=lambda _h, a: http_actions.append(a) or {"ok": True},
            ):
                with mock.patch.object(restore_mod, "time") as tmod:
                    _patch_clock(tmod)
                    with mock.patch.object(
                        restore_mod,
                        "overlay_key_for_display",
                        return_value="asterism.desktop.app.2",
                    ):
                        r = restore_mod.restore_display(
                            "display-1", path=path, allow_hand_fallback=False
                        )
        assert r["ok"], r
        assert cleared["n"] == 1
        assert "clear-just-floated" in calls
        assert r["float_consume"]["cleared"] is True
        assert r["float_consume"]["skipped"] is False
        assert r["geometry_settle"]["ok"] is True
        assert r["post_float_settle"]["ok"] is True
        # Order: geometry settle → clear → final restore
        i_clear = calls.index("clear-just-floated")
        i_lc = calls.index("inspect-world-lifecycle")
        directs = [i for i, c in enumerate(calls) if c == "direct-restore"]
        assert i_lc < i_clear < directs[1]
        assert r["pre_hide_restore"]["initializedFromNull"] is True
        assert r["final_restore"]["ok"] is True
        assert r["final_verify"]["ok"] is True
        assert r["final_verify"].get("stable_samples", 0) >= 3
        assert http_actions == ["show", "hide"]
        # No timeout despite stale true flag
        assert "timeout waiting for justFloatedFromDashboard" not in (r.get("error") or "")
    print("OK stale flag consume then final")


def test_world_already_false_skips_clear() -> None:
    calls: list[str] = []
    http_actions: list[str] = []

    def fake_req(cmd, **kw):
        calls.append(cmd)
        if cmd in ("seed-presentation-transform", "set-presentation"):
            return {"ok": True, "result": {"ok": True}}
        if cmd == "capture":
            return {
                "ok": True,
                "result": {"ok": True, "capture": {"dockLocationName": "World"}},
            }
        if cmd == "inspect-undocked-instance":
            return {
                "ok": True,
                "result": {
                    "ok": True,
                    "candidateCount": 1,
                    "targetFrameID": "42",
                    "candidates": [{"frameID": "42"}],
                },
            }
        if cmd == "direct-restore":
            return {"ok": True, "result": {"ok": True, "instanceFound": True}}
        if cmd == "get-live-world":
            return {"ok": True, "result": {"ok": True, "xfTransform": P}}
        if cmd == "inspect-world-lifecycle":
            return _lc_result(just_floated=False, xf=P)
        if cmd == "clear-just-floated":
            raise AssertionError("must skip clear when already false")
        raise AssertionError(cmd)

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "s.json"
        set_display_world("display-1", P, path=path)
        with mock.patch.object(restore_mod, "dashmgr_request", side_effect=fake_req):
            with mock.patch.object(
                restore_mod,
                "_http_action",
                side_effect=lambda _h, a: http_actions.append(a) or {"ok": True},
            ):
                with mock.patch.object(restore_mod, "time") as tmod:
                    _patch_clock(tmod)
                    with mock.patch.object(
                        restore_mod,
                        "overlay_key_for_display",
                        return_value="asterism.desktop.app.2",
                    ):
                        r = restore_mod.restore_display(
                            "display-1", path=path, allow_hand_fallback=False
                        )
        assert r["ok"] is True
        assert "clear-just-floated" not in calls
        assert r["float_consume"]["skipped"] is True
        assert r["final_verify"]["ok"] is True
    print("OK already-false skips clear")


def test_world_final_verify_requires_stable_samples() -> None:
    """Final verify needs consecutive P matches; single match then drift fails."""
    http_actions: list[str] = []
    get_n = {"n": 0}
    bad = {
        "translation": {"x": 0.0, "y": 0.0, "z": 0.0},
        "rotation": {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0},
        "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
    }

    def fake_req(cmd, **kw):
        if cmd in ("seed-presentation-transform", "set-presentation"):
            return {"ok": True, "result": {"ok": True}}
        if cmd == "capture":
            return {
                "ok": True,
                "result": {"ok": True, "capture": {"dockLocationName": "World"}},
            }
        if cmd == "inspect-undocked-instance":
            return {
                "ok": True,
                "result": {
                    "ok": True,
                    "candidateCount": 1,
                    "targetFrameID": "42",
                    "candidates": [{"frameID": "42"}],
                },
            }
        if cmd == "direct-restore":
            return {"ok": True, "result": {"ok": True, "instanceFound": True}}
        if cmd == "get-live-world":
            get_n["n"] += 1
            # pre-hide stable_samples=1 succeeds on first P
            # final needs 3; give P then bad to break streak
            if get_n["n"] == 1:
                xf = P
            elif get_n["n"] in (2, 3):
                xf = P
            else:
                xf = bad
            return {"ok": True, "result": {"ok": True, "xfTransform": xf}}
        if cmd == "inspect-world-lifecycle":
            return _lc_result(just_floated=False, xf=P)
        if cmd == "clear-just-floated":
            raise AssertionError("must skip clear when already false")
        raise AssertionError(cmd)

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "s.json"
        set_display_world("display-1", P, path=path)
        with mock.patch.object(restore_mod, "dashmgr_request", side_effect=fake_req):
            with mock.patch.object(
                restore_mod,
                "_http_action",
                side_effect=lambda _h, a: http_actions.append(a) or {"ok": True},
            ):
                with mock.patch.object(restore_mod, "time") as tmod:
                    _patch_clock(tmod)
                    with mock.patch.object(
                        restore_mod,
                        "overlay_key_for_display",
                        return_value="asterism.desktop.app.2",
                    ):
                        r = restore_mod.restore_display(
                            "display-1", path=path, allow_hand_fallback=False
                        )
        assert r["ok"] is False
        assert r["pre_hide_verify"]["ok"] is True
        assert r["final_verify"]["ok"] is False
        assert "hide" in http_actions
    print("OK final verify requires stable samples")


def test_world_geometry_must_settle_before_clear() -> None:
    """Clear only after geometry ready; dragged samples delay clear."""
    calls: list[str] = []
    http_actions: list[str] = []
    lc_n = {"n": 0}
    cleared = {"n": 0}

    def fake_req(cmd, **kw):
        calls.append(cmd)
        if cmd in ("seed-presentation-transform", "set-presentation"):
            return {"ok": True, "result": {"ok": True}}
        if cmd == "capture":
            return {
                "ok": True,
                "result": {"ok": True, "capture": {"dockLocationName": "World"}},
            }
        if cmd == "inspect-undocked-instance":
            return {
                "ok": True,
                "result": {
                    "ok": True,
                    "candidateCount": 1,
                    "targetFrameID": "42",
                    "candidates": [{"frameID": "42"}],
                },
            }
        if cmd == "direct-restore":
            return {"ok": True, "result": {"ok": True, "instanceFound": True}}
        if cmd == "get-live-world":
            return {"ok": True, "result": {"ok": True, "xfTransform": P}}
        if cmd == "inspect-world-lifecycle":
            lc_n["n"] += 1
            # First two samples still dragging → not ready for settle
            if cleared["n"] == 0 and lc_n["n"] <= 2:
                return _lc_result(just_floated=True, dragged=True, xf=P)
            floated = cleared["n"] == 0
            return _lc_result(just_floated=floated, dragged=False, xf=P)
        if cmd == "clear-just-floated":
            # Must not clear while still in dragged settle phase
            assert lc_n["n"] > 2
            cleared["n"] += 1
            return {
                "ok": True,
                "result": {"ok": True, "before": True, "after": False},
            }
        raise AssertionError(cmd)

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "s.json"
        set_display_world("display-1", P, path=path)
        with mock.patch.object(restore_mod, "dashmgr_request", side_effect=fake_req):
            with mock.patch.object(
                restore_mod,
                "_http_action",
                side_effect=lambda _h, a: http_actions.append(a) or {"ok": True},
            ):
                with mock.patch.object(restore_mod, "time") as tmod:
                    _patch_clock(tmod)
                    with mock.patch.object(
                        restore_mod,
                        "overlay_key_for_display",
                        return_value="asterism.desktop.app.2",
                    ):
                        r = restore_mod.restore_display(
                            "display-1", path=path, allow_hand_fallback=False
                        )
        assert r["ok"] is True
        assert cleared["n"] == 1
        assert r["geometry_settle"]["ok"] is True
        assert calls.index("clear-just-floated") > calls.index("inspect-world-lifecycle")
    print("OK geometry settles before clear")


def test_world_hide_on_failure_and_no_mask() -> None:
    http_actions: list[str] = []

    def fake_req(cmd, **kw):
        if cmd == "seed-presentation-transform":
            return {"ok": True, "result": {"ok": True}}
        if cmd == "set-presentation":
            return {"ok": True, "result": {"ok": True}}
        raise AssertionError(cmd)

    def fake_http(http, action):
        http_actions.append(action)
        if action == "show":
            return {"ok": True}
        return {"ok": False, "error": "hide failed"}

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "s.json"
        set_display_world("display-1", P, path=path)
        with mock.patch.object(restore_mod, "dashmgr_request", side_effect=fake_req):
            with mock.patch.object(restore_mod, "_http_action", side_effect=fake_http):
                with mock.patch.object(restore_mod, "time") as tmod:
                    tmod.sleep = lambda *_a, **_k: None
                    tmod.time = time.time
                    with mock.patch.object(
                        restore_mod,
                        "_wait_presentation",
                        return_value={"ok": True},
                    ):
                        with mock.patch.object(
                            restore_mod,
                            "_wait_world_ready",
                            return_value={"ok": False, "error": "timeout waiting"},
                        ):
                            with mock.patch.object(
                                restore_mod,
                                "overlay_key_for_display",
                                return_value="asterism.desktop.app.2",
                            ):
                                r = restore_mod.restore_display(
                                    "display-1",
                                    path=path,
                                    allow_hand_fallback=False,
                                )
        assert r["ok"] is False
        assert r["error"] == "timeout waiting"
        assert http_actions == ["show", "hide"]
        assert r["materialization"]["hide"]["ok"] is False
        assert "hide failed" not in (r.get("error") or "")
    print("OK hide on failure no mask")


def test_world_no_transform_still_materializes() -> None:
    calls: list[str] = []
    http_actions: list[str] = []

    def fake_req(cmd, **kw):
        calls.append(cmd)
        if cmd == "set-presentation":
            return {"ok": True, "result": {"ok": True}}
        if cmd == "capture":
            return {
                "ok": True,
                "result": {"ok": True, "capture": {"dockLocationName": "World"}},
            }
        if cmd == "inspect-undocked-instance":
            return {
                "ok": True,
                "result": {
                    "ok": True,
                    "candidateCount": 1,
                    "targetFrameID": "42",
                    "candidates": [{"frameID": "42", "xfTransformNullish": True}],
                },
            }
        if cmd == "seed-presentation-transform":
            raise AssertionError("should not seed without transform")
        if cmd == "direct-restore":
            raise AssertionError("should not direct-restore without transform")
        if cmd == "get-live-world":
            raise AssertionError("should not get-live-world without transform")
        if cmd == "clear-just-floated":
            raise AssertionError("should not clear-just-floated without saved World transform")
        if cmd == "inspect-just-floated":
            raise AssertionError("should not wait float lifecycle without saved World transform")
        if cmd == "inspect-world-lifecycle":
            raise AssertionError("should not settle geometry without saved World transform")
        raise AssertionError(cmd)

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "s.json"
        save(
            {
                "version": 2,
                "displays": {"display-1": {"presentation": "world", "transforms": {}}},
            },
            path,
        )
        with mock.patch.object(restore_mod, "dashmgr_request", side_effect=fake_req):
            with mock.patch.object(
                restore_mod,
                "_http_action",
                side_effect=lambda _h, a: http_actions.append(a) or {"ok": True},
            ):
                with mock.patch.object(restore_mod, "time") as tmod:
                    tmod.sleep = lambda *_a, **_k: None
                    tmod.time = time.time
                    with mock.patch.object(
                        restore_mod,
                        "overlay_key_for_display",
                        return_value="asterism.desktop.app.2",
                    ):
                        r = restore_mod.restore_display(
                            "display-1", path=path, allow_hand_fallback=False
                        )
        assert r["ok"] is True
        assert "direct-restore" not in calls
        assert "clear-just-floated" not in calls
        assert "seed-presentation-transform" not in calls
        assert http_actions == ["show", "hide"]
        assert r["materialization"]["live_ready"] is True
    print("OK world no-transform materialize")


def test_dashboard_theater_restore() -> None:
    for mode in ("dashboard", "theater"):
        calls = []
        http_actions: list[str] = []

        def fake_req(cmd, **kw):
            calls.append(cmd)
            if cmd in ("seed-presentation-transform", "set-presentation"):
                return {"ok": True, "result": {"ok": True}}
            if cmd == "capture":
                title = "Dashboard" if mode == "dashboard" else "Theater"
                return {
                    "ok": True,
                    "result": {
                        "ok": True,
                        "capture": {"dockLocationName": title},
                    },
                }
            raise AssertionError(cmd)

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "s.json"
            st = {
                "version": 2,
                "displays": {
                    "display-1": {
                        "presentation": mode,
                        "transforms": {mode: P} if mode != "dashboard" else {},
                    }
                },
            }
            if mode == "dashboard":
                st["displays"]["display-1"]["transforms"] = {"dashboard": P}
            save(st, path)
            with mock.patch.object(restore_mod, "dashmgr_request", side_effect=fake_req):
                with mock.patch.object(
                    restore_mod,
                    "_http_action",
                    side_effect=lambda *_a, **_k: http_actions.append("x") or {"ok": True},
                ):
                    with mock.patch.object(
                        restore_mod,
                        "overlay_key_for_display",
                        return_value="asterism.desktop.app.2",
                    ):
                        r = restore_mod.restore_display(
                            "display-1", path=path, allow_hand_fallback=False
                        )
            assert r["ok"], r
            assert "direct-restore" not in calls
            assert "restore-via-hand" not in calls
            assert http_actions == []  # no World materialization show/hide
            assert "materialization" not in r
    print("OK dashboard/theater restore")


def test_no_hand_on_startup_restore_all() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "s.json"
        set_display_world("display-1", P, path=path)

        def fake_req(cmd, **kw):
            if cmd == "seed-presentation-transform":
                return {"ok": True, "result": {"ok": True}}
            if cmd == "set-presentation":
                return {"ok": True, "result": {"ok": True}}
            if cmd == "restore-via-hand":
                raise AssertionError("hand must not be used")
            if cmd == "direct-restore":
                raise AssertionError("direct should not run if live UO missing")
            return {"ok": True, "result": {"ok": False}}

        with mock.patch.object(restore_mod, "dashmgr_request", side_effect=fake_req):
            with mock.patch.object(
                restore_mod, "_http_action", return_value={"ok": True}
            ):
                with mock.patch.object(restore_mod, "time") as tmod:
                    tmod.sleep = lambda *_a, **_k: None
                    tmod.time = time.time
                    with mock.patch.object(
                        restore_mod, "_wait_presentation", return_value={"ok": True}
                    ):
                        with mock.patch.object(restore_mod, "wait_for_ws", return_value=True):
                            with mock.patch.object(
                                restore_mod,
                                "map_displays_to_overlays",
                                return_value=[
                                    {
                                        "display_id": "display-1",
                                        "overlay_key": "asterism.desktop.app.2",
                                    }
                                ],
                            ):
                                with mock.patch.object(
                                    restore_mod,
                                    "overlay_key_for_display",
                                    return_value="asterism.desktop.app.2",
                                ):
                                    with mock.patch.object(
                                        restore_mod,
                                        "_wait_world_ready",
                                        return_value={"ok": False, "error": "timeout"},
                                    ):
                                        r = restore_mod.restore_all(
                                            path=path,
                                            wait_ws=False,
                                            allow_hand_fallback=False,
                                        )
        assert r["results"][0].get("path") != "restore-via-hand"
        assert r["results"][0].get("ok") is False
    print("OK no hand fallback startup")


def test_missing_corrupt_state() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "missing.json"
        assert load_or_default(path)["displays"] == {}
        path.write_text("{bad", encoding="utf-8")
        assert load_or_default(path)["displays"] == {}
    print("OK missing/corrupt")


def test_session_no_layout_apply_race() -> None:
    session = (ROOT / "desktop" / "asterism-session.sh").read_text(encoding="utf-8")
    # No executable layout apply invocation (comments may mention the old race)
    assert "asterism-layout\" apply" not in session
    assert "asterism-layout' apply" not in session
    assert 'asterism-layout" sync' in session or "asterism-layout\" sync" in session
    assert "asterism-spatial.service" in session
    unit = (ROOT / "systemd" / "asterism-spatial.service").read_text(encoding="utf-8")
    assert "After=steamvr.service asterism-dashboard.service asterism-desktop.service" in unit
    assert "ExecStart=-" in unit and "restore-all" in unit
    assert "ExecStop=" in unit and "snapshot-all" in unit
    assert "TimeoutStopSec=20" in unit
    assert "ASTERISM_SPATIAL_SNAPSHOT_WS_TIMEOUT=3" in unit
    assert "WantedBy=steamvr.service" in unit
    print("OK session/systemd ownership")


def test_execstart_dash_keeps_oneshot_armed() -> None:
    """ExecStart=- ensures failed restore still leaves oneshot active/exited."""
    unit = (ROOT / "systemd" / "asterism-spatial.service").read_text(encoding="utf-8")
    lines = [
        ln.strip()
        for ln in unit.splitlines()
        if ln.strip().startswith("ExecStart=")
    ]
    assert len(lines) == 1
    assert lines[0].startswith("ExecStart=-")
    assert "restore-all" in lines[0]
    assert "Type=oneshot" in unit
    assert "RemainAfterExit=yes" in unit
    print("OK ExecStart=- armed for ExecStop")


def test_snapshot_incremental_durable() -> None:
    """display-1 success must hit disk even if display-2 then fails."""
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "spatial-state.json"
        set_display_world("display-1", P, path=path)
        set_display_world("display-2", Q, path=path)

        def fake_req(cmd, **kw):
            key = kw.get("overlay_key")
            if key == "asterism.desktop.app.2":
                if cmd == "capture":
                    return {
                        "ok": True,
                        "result": {
                            "ok": True,
                            "capture": {
                                "dockLocationName": "World",
                                "rememberedTransforms": {"World": P},
                            },
                            "world": P,
                        },
                    }
                if cmd == "get-live-world":
                    # New live pose for display-1
                    return {
                        "ok": True,
                        "result": {
                            "ok": True,
                            "xfTransform": {
                                "translation": {"x": 3.0, "y": 3.0, "z": -3.0},
                                "rotation": P["rotation"],
                                "scale": P["scale"],
                            },
                        },
                    }
            if key == "asterism.desktop.app.3":
                raise RuntimeError("hang/fail display-2")
            raise AssertionError((cmd, key))

        with mock.patch.object(restore_mod, "dashmgr_request", side_effect=fake_req):
            with mock.patch.object(
                restore_mod,
                "map_displays_to_overlays",
                return_value=[
                    {
                        "display_id": "display-1",
                        "overlay_key": "asterism.desktop.app.2",
                    },
                    {
                        "display_id": "display-2",
                        "overlay_key": "asterism.desktop.app.3",
                    },
                ],
            ):
                with mock.patch.object(
                    restore_mod,
                    "overlay_key_for_display",
                    side_effect=lambda did, keys=None: {
                        "display-1": "asterism.desktop.app.2",
                        "display-2": "asterism.desktop.app.3",
                    }[did],
                ):
                    r = restore_mod.snapshot_all(path=path, wait_ws=False)
        assert r["results"][0].get("ok") is True
        assert r["results"][0].get("saved") is True
        assert r["results"][1].get("ok") is False
        on_disk = load(path)
        assert on_disk["displays"]["display-1"]["transforms"]["world"]["translation"]["x"] == 3.0
        # display-2 prior Q retained
        assert on_disk["displays"]["display-2"]["transforms"]["world"]["translation"]["x"] == 1.5
    print("OK incremental snapshot durable")


def test_boot_presentation_not_persisted() -> None:
    from spatial.spatial_state import normalize_presentation

    assert normalize_presentation("Boot") is None
    assert normalize_presentation("boot") is None
    assert normalize_presentation("World") == "world"
    print("OK boot unsupported")


def test_shell_seed_presentation() -> None:
    shell = (ROOT / "patches" / "asterism_shell.js").read_text(encoding="utf-8")
    assert "seedPresentationTransform" in shell
    assert 'msg.cmd === "seed-presentation-transform"' in shell
    assert "presentation must be dashboard|world|theater|lefthand|righthand" in shell
    # dashmgr rejects non-asterism
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "ad", ROOT / "dashboard" / "asterism-dashboard.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    mod.dashmgr_reset_for_tests()
    bad = mod.dashmgr_enqueue(
        "seed-presentation-transform",
        overlay_key="steam.other",
        presentation="world",
        transform=P,
    )
    assert bad["ok"] is False
    bad2 = mod.dashmgr_enqueue(
        "seed-presentation-transform",
        overlay_key="asterism.desktop.app.2",
        presentation="nope",
        transform=P,
    )
    assert bad2["ok"] is False
    ok = mod.dashmgr_enqueue(
        "seed-presentation-transform",
        overlay_key="asterism.desktop.app.2",
        presentation="theater",
        transform=P,
    )
    assert ok["ok"] is True
    print("OK seed-presentation-transform")


def test_mapping_stable_ids() -> None:
    from spatial.display_map import map_displays_to_overlays

    rows = map_displays_to_overlays(
        keys=["asterism.desktop.app.2", "asterism.desktop.app.9"],
        displays=[
            {"id": "display-1", "enabled": True},
            {"id": "display-2", "enabled": True},
        ],
    )
    assert rows[0]["display_id"] == "display-1"
    assert rows[1]["overlay_key"] == "asterism.desktop.app.9"
    print("OK mapping")


def main() -> int:
    test_v1_to_v2_migration()
    test_atomic_v2_save()
    test_snapshot_prefers_live_world()
    test_snapshot_failure_preserves_peers()
    test_world_restore_stale_flag_consume_then_final()
    test_world_already_false_skips_clear()
    test_world_final_verify_requires_stable_samples()
    test_world_geometry_must_settle_before_clear()
    test_world_hide_on_failure_and_no_mask()
    test_world_no_transform_still_materializes()
    test_dashboard_theater_restore()
    test_no_hand_on_startup_restore_all()
    test_missing_corrupt_state()
    test_session_no_layout_apply_race()
    test_execstart_dash_keeps_oneshot_armed()
    test_snapshot_incremental_durable()
    test_boot_presentation_not_persisted()
    test_shell_seed_presentation()
    test_mapping_stable_ids()
    print("OK all lifecycle tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
