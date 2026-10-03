#!/usr/bin/env python3
"""No-SteamVR checks for Case A/B undocked-render diagnostics."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_dashboard():
    spec = importlib.util.spec_from_file_location(
        "asterism_dashboard", ROOT / "dashboard" / "asterism-dashboard.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_shell_inspect_and_force_markers() -> None:
    shell = (ROOT / "patches" / "asterism_shell.js").read_text(encoding="utf-8")
    for needle in (
        "function renderUndockedSourceIsKnownSafe",
        "function elementTypeDiag",
        "function elementFrameDiag",
        "function inspectUndockedRender",
        "function forceDashboardRender",
        'msg.cmd === "inspect-undocked-render"',
        'msg.cmd === "force-dashboard-render"',
        "frames_local_undocked",
        "renderUndockedLocalFrameTransforms",
        "dash.forceUpdate()",
        "targetPresent",
        "source shape not recognized; refuse invoke",
        "typeSourcePreview",
        "typeKind",
        "typeName",
        "typeDisplayName",
        "typeSourceLength",
        "propsKeys",
        "mentionsXfTransform",
        "mentionsDockLocation",
        "mentionsWorld",
        "mentionsSetDockLocation",
        "mentionsMapLastRelative",
        "mentionsIsFullyVisible",
        "mentionsShouldShowKeyboardHack",
        "shouldShowKeyboardForUndockedFrame_Hack",
        "m_mapLastRelativeTransformForDockLocation",
        "Function.prototype.toString.call(t)",
        "inspectUndockedRender: inspectUndockedRender",
        "forceDashboardRender: forceDashboardRender",
    ):
        assert needle in shell, needle
    # Must not serialize React elements/fibers or invoke component types
    assert "return elements" not in shell or "elementFrameDiag" in shell
    type_fn = shell[
        shell.index("function elementTypeDiag") : shell.index(
            "function elementFrameDiag"
        )
    ]
    assert "t(" not in type_fn.replace("toString.call(t)", "")
    assert "new t" not in type_fn
    assert "React.createElement" not in type_fn
    print("OK shell Case A/B markers")


def test_cli_commands_present() -> None:
    cli = (ROOT / "scripts" / "asterism-dashmgr").read_text(encoding="utf-8")
    assert "inspect-undocked-render)" in cli
    assert "force-dashboard-render)" in cli
    assert "'cmd':'inspect-undocked-render'" in cli.replace(" ", "")
    assert "'cmd':'force-dashboard-render'" in cli.replace(" ", "")
    print("OK CLI cmds")


def test_dashmgr_enqueue_policy() -> None:
    mod = _load_dashboard()
    mod.dashmgr_reset_for_tests()
    assert "inspect-undocked-render" in mod._SUPPORTED_CMDS
    assert "force-dashboard-render" in mod._SUPPORTED_CMDS

    rej = mod.dashmgr_enqueue(
        "inspect-undocked-render", overlay_key="steam.overlay.other"
    )
    assert rej["ok"] is False
    assert "asterism.desktop" in rej["error"]

    ok = mod.dashmgr_enqueue(
        "inspect-undocked-render", overlay_key="asterism.desktop.app.2"
    )
    assert ok["ok"] is True

    # force-dashboard-render: no overlay_key required
    force = mod.dashmgr_enqueue("force-dashboard-render")
    assert force["ok"] is True
    assert force.get("cmd") == "force-dashboard-render" or "id" in force
    print("OK dashmgr enqueue policy")


def test_known_safe_shape_contract() -> None:
    """Guard the observed live source shape used for the invoke gate."""
    shell = (ROOT / "patches" / "asterism_shell.js").read_text(encoding="utf-8")
    # Gate requires all four tokens
    gate = shell[
        shell.index("function renderUndockedSourceIsKnownSafe") : shell.index(
            "function elementTypeDiag"
        )
    ]
    for tok in ("frames_local_undocked", ".map", "createElement", "frame"):
        assert tok in gate, tok
    print("OK known-safe shape gate")


def test_element_type_diag_contract() -> None:
    """elementTypeDiag reports JSON-safe type metadata; preview capped."""
    shell = (ROOT / "patches" / "asterism_shell.js").read_text(encoding="utf-8")
    body = shell[
        shell.index("function elementTypeDiag") : shell.index(
            "function elementFrameDiag"
        )
    ]
    assert "src.slice(0, 3000)" in body
    assert "Object.keys(props)" in body
    # needle strings for component-source triage
    for s in (
        '"xfTransform"',
        '"dockLocation"',
        '"World"',
        '"SetDockLocation"',
        '"m_mapLastRelativeTransformForDockLocation"',
        '"isFullyVisible"',
        '"shouldShowKeyboardForUndockedFrame_Hack"',
    ):
        assert s in body, s
    # frame fields still merged in elementFrameDiag
    frame_body = shell[
        shell.index("function elementFrameDiag") : shell.index(
            "function inspectUndockedRender"
        )
    ]
    for s in ("frameID", "summonOverlayKey", "associatedSummonOverlayKeys", "typeKind"):
        assert s in frame_body, s
    print("OK element type diag contract")


def main() -> int:
    test_shell_inspect_and_force_markers()
    test_cli_commands_present()
    test_dashmgr_enqueue_policy()
    test_known_safe_shape_contract()
    test_element_type_diag_contract()
    print("ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
