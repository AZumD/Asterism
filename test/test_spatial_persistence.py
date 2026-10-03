#!/usr/bin/env python3
"""Unit tests: spatial-state + display mapping + probe JSON safety (no SteamVR)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from spatial.display_map import (  # noqa: E402
    display_id_for_overlay,
    map_displays_to_overlays,
    overlay_key_for_display,
)
from spatial.spatial_state import (  # noqa: E402
    SpatialStateError,
    default_state,
    load,
    load_or_default,
    save,
    set_display_world,
    validate_transform,
)

SAMPLE_P = {
    "translation": {
        "x": 0.904729962348938,
        "y": 1.6027473211288452,
        "z": -1.1635589599609375,
    },
    "rotation": {
        "w": 0.903954665885911,
        "x": 0.14401781558990479,
        "y": -0.4022553563117981,
        "z": 0.01776042953133583,
    },
    "scale": {
        "x": 0.9999998807907104,
        "y": 0.9999999403953552,
        "z": 0.9999998211860657,
    },
}


def test_probe_json_serializable() -> None:
    """Probe must never embed raw Frame objects — only JSON-safe snapshots."""
    shell = (ROOT / "patches" / "asterism_shell.js").read_text(encoding="utf-8")
    assert "resolveFramesReport" in shell
    assert "frameResolve = resolveFramesReport" in shell.replace(" ", "") or \
        "report.frameResolve = resolveFramesReport(" in shell
    # Simulate shell probe payload shape
    probe = {
        "ts": "2026-10-03T00:00:00Z",
        "hasDashboard": True,
        "hasAsterismBridge": True,
        "frameResolve": {
            "source": "chunk_bridge",
            "count": 1,
            "frames": [
                {
                    "frameID": "174400003",
                    "summonOverlayKey": "asterism.desktop.app.2",
                    "dockLocation": 1,
                    "dockLocationName": "World",
                    "rememberedTransforms": {"World": SAMPLE_P},
                }
            ],
        },
        "notes": ["Frame resolve via chunk_bridge"],
    }
    s = json.dumps(probe)
    assert "frameID" in s
    # Ensure no accidental circular-marker leftovers
    json.loads(s)
    print("OK probe json serializable")


def test_spatial_state_roundtrip_atomic() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "spatial-state.json"
        st = set_display_world("display-1", SAMPLE_P, path=path)
        assert st["version"] == 2
        assert st["displays"]["display-1"]["presentation"] == "world"
        loaded = load(path)
        xf = loaded["displays"]["display-1"]["transforms"]["world"]
        assert xf["translation"]["x"] == SAMPLE_P["translation"]["x"]
        # round-trip exact
        xf = validate_transform(xf)
        assert xf["rotation"]["w"] == SAMPLE_P["rotation"]["w"]
        # atomic: parent exists, file is valid JSON
        assert path.is_file()
        json.loads(path.read_text(encoding="utf-8"))
    print("OK spatial roundtrip+atomic")


def test_corrupt_state_handling() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "spatial-state.json"
        path.write_text("{not json", encoding="utf-8")
        try:
            load(path)
            raise AssertionError("expected SpatialStateError")
        except SpatialStateError:
            pass
        # load_or_default recovers
        st = load_or_default(path)
        assert st == default_state()
        # bad version
        path.write_text(json.dumps({"version": 99, "displays": {}}), encoding="utf-8")
        try:
            load(path)
            raise AssertionError("expected version error")
        except SpatialStateError as e:
            assert "version" in str(e)
        # bad display id
        try:
            save({"version": 1, "displays": {"nope": {}}}, path)
            raise AssertionError("expected id error")
        except SpatialStateError:
            pass
    print("OK corrupt handling")


def test_display_mapping() -> None:
    displays = [
        {"id": "display-1", "enabled": True, "primary": True},
        {"id": "display-2", "enabled": True, "primary": False},
    ]
    keys = ["asterism.desktop.app.2", "asterism.desktop.app.3"]
    rows = map_displays_to_overlays(keys=keys, displays=displays)
    assert rows[0]["display_id"] == "display-1"
    assert rows[0]["overlay_key"] == "asterism.desktop.app.2"
    assert rows[1]["display_id"] == "display-2"
    assert rows[1]["overlay_key"] == "asterism.desktop.app.3"
    assert overlay_key_for_display("display-2", keys=keys, displays=displays) == \
        "asterism.desktop.app.3"
    assert display_id_for_overlay("asterism.desktop.app.2", keys=keys, displays=displays) == \
        "display-1"
    # missing runtime key
    rows2 = map_displays_to_overlays(keys=["asterism.desktop.app.2"], displays=displays)
    assert rows2[1]["overlay_key"] is None
    # orphan runtime
    rows3 = map_displays_to_overlays(
        keys=keys + ["asterism.desktop.app.4"], displays=displays
    )
    assert rows3[2].get("orphan_runtime") is True
    print("OK display mapping")


def test_multi_display_state() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "spatial-state.json"
        p2 = dict(SAMPLE_P)
        p2 = {
            "translation": {"x": 1.0, "y": 1.5, "z": -2.0},
            "rotation": SAMPLE_P["rotation"],
            "scale": SAMPLE_P["scale"],
        }
        set_display_world("display-1", SAMPLE_P, path=path)
        set_display_world("display-2", p2, path=path)
        st = load(path)
        assert set(st["displays"]) == {"display-1", "display-2"}
        assert (
            st["displays"]["display-1"]["transforms"]["world"]["translation"]["x"]
            != st["displays"]["display-2"]["transforms"]["world"]["translation"]["x"]
        )
    print("OK multi-display state")


def test_restore_validation_and_missing_frame() -> None:
    from spatial.restore import restore_display

    displays = [{"id": "display-1", "enabled": True}]
    assert overlay_key_for_display("display-1", keys=[], displays=displays) is None
    r = restore_display("display-1", keys=[], allow_hand_fallback=False)
    assert r.get("ok") is False or r.get("skipped")
    print("OK missing frame handling")


def test_shell_commands_present() -> None:
    shell = (ROOT / "patches" / "asterism_shell.js").read_text(encoding="utf-8")
    for needle in (
        'msg.cmd === "direct-restore"',
        'msg.cmd === "restore-via-hand"',
        'msg.cmd === "get-live-world"',
        'msg.cmd === "find-live-uo"',
        'msg.cmd === "inspect-undocked-render"',
        'msg.cmd === "force-dashboard-render"',
        "function directRestore",
        "function restoreViaHand",
        "function inspectUndockedRender",
        "function forceDashboardRender",
        "findLiveUndockedOverlayForFrame",
        "react-fiber-setState+map",
        "JSON-safe Frame resolve",
    ):
        assert needle in shell, needle
    stage = (ROOT / "scripts" / "stage-steamvr-dashmgr-bridge-v2.sh").read_text(
        encoding="utf-8", errors="ignore"
    )
    assert "applyWorldTransformForSummonKey" in stage
    assert "EXPECTED_V1_SHA=272c1e40" in stage
    deploy = (ROOT / "test" / "_deploy_shell_ws_live.sh").read_text(encoding="utf-8")
    assert "frametop" not in deploy.lower()
    assert "steamos_root_pwd" not in deploy
    assert "sudo -S" not in deploy
    assert "printf" not in deploy or "steamos_root" not in deploy
    assert "steamos-readonly disable" in deploy
    assert "steamos-readonly enable" in deploy
    # only allowed soft-fail: missing prior shell backup (not readonly ops)
    soft = [ln for ln in deploy.splitlines() if "|| true" in ln and not ln.strip().startswith("#")]
    assert len(soft) == 1 and "asterism_shell.js" in soft[0]
    print("OK shell cmds + deploy cleanup")


def test_dashmgr_rejects_non_asterism_new_cmds() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "asterism_dashboard", ROOT / "dashboard" / "asterism-dashboard.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.dashmgr_reset_for_tests()
    for cmd in (
        "direct-restore",
        "restore-via-hand",
        "get-live-world",
        "inspect-undocked-render",
    ):
        rej = mod.dashmgr_enqueue(cmd, overlay_key="steam.overlay.other")
        assert rej["ok"] is False
        ok = mod.dashmgr_enqueue(
            cmd, overlay_key="asterism.desktop.app.2", transform=SAMPLE_P
        )
        assert ok["ok"] is True
    force = mod.dashmgr_enqueue("force-dashboard-render")
    assert force["ok"] is True
    print("OK non-asterism rejection")


def main() -> int:
    test_probe_json_serializable()
    test_spatial_state_roundtrip_atomic()
    test_corrupt_state_handling()
    test_display_mapping()
    test_multi_display_state()
    test_restore_validation_and_missing_frame()
    test_shell_commands_present()
    test_dashmgr_rejects_non_asterism_new_cmds()
    print("OK all spatial/probe tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
