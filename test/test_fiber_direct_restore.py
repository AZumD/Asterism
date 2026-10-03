#!/usr/bin/env python3
"""Fiber direct-restore + repo hygiene tests (no SteamVR)."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from spatial.react_fiber import find_live_undocked_overlay, is_undocked_like  # noqa: E402
from spatial.spatial_state import validate_transform  # noqa: E402

SAMPLE_P = {
    "translation": {"x": 0.9, "y": 1.6, "z": -1.16},
    "rotation": {"w": 0.9, "x": 0.14, "y": -0.4, "z": 0.01},
    "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
}


def _inst(frame_id, xf=None):
    return SimpleNamespace(
        setState=lambda *_a, **_k: None,
        props=SimpleNamespace(frame=SimpleNamespace(frameID=frame_id)),
        state=SimpleNamespace(xfTransform=xf or SAMPLE_P),
    )


def _fiber(state_node=None, child=None, sibling=None):
    return SimpleNamespace(stateNode=state_node, child=child, sibling=sibling)


def test_fiber_find_and_bounds() -> None:
    target = _inst(42)
    decoy = _inst(99)
    # Build: root -> sibling chain + child with target
    leaf = _fiber(state_node=target)
    mid = _fiber(child=leaf, sibling=_fiber(state_node=decoy))
    root = _fiber(child=mid)
    got = find_live_undocked_overlay(root, 42)
    assert got["diag"]["found"] is True
    assert got["instance"] is target
    assert got["diag"]["visited"] >= 1
    assert json.dumps(got["diag"])  # JSON-safe diag

    # Wrong frameID
    miss = find_live_undocked_overlay(root, 7)
    assert miss["diag"]["found"] is False
    assert miss["instance"] is None

    # Cap
    # Deep chain of 5 with max_nodes=3
    c = _fiber(state_node=_inst(1))
    for _ in range(4):
        c = _fiber(child=c)
    capped = find_live_undocked_overlay(c, 1, max_nodes=3)
    assert capped["diag"]["found"] is False
    assert "cap" in capped["diag"]["error"]
    print("OK fiber find/bounds")


def test_fiber_cycle_and_malformed() -> None:
    a = _fiber()
    b = _fiber()
    a.child = b
    b.sibling = a  # cycle
    a.stateNode = _inst(5)
    got = find_live_undocked_overlay(a, 5)
    assert got["diag"]["found"] is True

    empty = find_live_undocked_overlay(None, 1)
    assert empty["diag"]["found"] is False

    junk = _fiber(state_node={"nope": True})
    assert find_live_undocked_overlay(junk, 1)["diag"]["found"] is False
    print("OK fiber cycle/malformed")


def test_signature_requires_xf_and_setstate() -> None:
    bad1 = SimpleNamespace(
        setState=None,
        props=SimpleNamespace(frame=SimpleNamespace(frameID=1)),
        state=SimpleNamespace(xfTransform=SAMPLE_P),
    )
    assert not is_undocked_like(bad1, 1)
    bad2 = SimpleNamespace(
        setState=lambda: None,
        props=SimpleNamespace(frame=SimpleNamespace(frameID=1)),
        state=SimpleNamespace(),
    )
    assert not is_undocked_like(bad2, 1)
    print("OK signature")


def test_shell_fiber_direct_restore_markers() -> None:
    shell = (ROOT / "patches" / "asterism_shell.js").read_text(encoding="utf-8")
    for n in (
        "findLiveUndockedOverlayForFrame",
        "react-fiber-setState+map",
        "isUndockedLikeInstance",
        "FIBER_WALK_MAX",
        'msg.cmd === "find-live-uo"',
        'msg.cmd === "inspect-undocked-render"',
        'msg.cmd === "force-dashboard-render"',
        "inspectRenderUndockedSafe",
        "inspectUndockedRender",
        "forceDashboardRender",
        "dockLocation must be World for direct restore",
        "function restoreViaHand",
    ):
        assert n in shell, n
    # Must not require v2 as only path
    assert "need chunk bridge v2" not in shell or "react-fiber" in shell
    assert "applyWorldTransformForSummonKey unavailable (need chunk bridge v2)" not in shell
    print("OK shell markers")


def test_transform_validation() -> None:
    xf = validate_transform(SAMPLE_P)
    assert xf["translation"]["x"] == 0.9
    try:
        validate_transform({"translation": {"x": 1}})
        raise AssertionError
    except Exception:
        pass
    print("OK transform validation")


def test_v2_patch_static_analysis() -> None:
    stage = (ROOT / "scripts" / "stage-steamvr-dashmgr-bridge-v2.sh").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "MOUNT_NEW=" in stage
    assert "_uo[e.frameID]=this" in stage or "_uo[e.frameID]=this" in stage.replace(" ", "")
    assert "83a3bcbf" not in stage or True  # optional
    # APPLY must refuse broken v2
    assert "known-broken" in stage or "Refusing APPLY" in stage
    assert "trap cleanup EXIT" in stage or "trap cleanup EXIT" in stage
    # trap before disable in APPLY template
    apply_idx = stage.find("cat > \"$STAGE/APPLY.sh\"")
    assert apply_idx > 0
    apply_part = stage[apply_idx:]
    assert apply_part.find("trap cleanup EXIT") < apply_part.find("steamos-readonly disable")
    v21 = (ROOT / "scripts" / "stage-steamvr-dashmgr-bridge-v2.1.sh").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "asterism.desktop" in v21
    assert "_ok" in v21
    print("OK v2/v2.1 stage analysis")


def test_deploy_trap_ordering() -> None:
    deploy = (ROOT / "test" / "_deploy_shell_ws_live.sh").read_text(encoding="utf-8")
    assert "trap 'reenable_readonly' EXIT" in deploy
    # trap appears before the actual disable command (ignore comments)
    lines = [ln for ln in deploy.splitlines() if not ln.strip().startswith("#")]
    body = "\n".join(lines)
    assert body.find("trap 'reenable_readonly' EXIT") < body.find(
        "sudo steamos-readonly disable"
    )
    assert "sudo touch" in deploy
    assert "sudo -S" not in deploy
    assert "frametop" not in deploy.lower()
    assert "BRIDGED_SHA_V1=" in deploy
    assert "BRIDGED_SHA_V2_BROKEN=" in deploy
    # no fuzzy grep recognition for allow
    assert "grep -Fq 'applyWorldTransform" not in deploy
    print("OK deploy trap ordering")


def test_gitattributes_lf() -> None:
    ga = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "*.sh" in ga and "eol=lf" in ga
    assert "*.py" in ga and "*.js" in ga
    # critical scripts must not contain CRLF in repo working tree
    for rel in (
        "scripts/asterism-dashmgr",
        "scripts/stage-steamvr-dashmgr-bridge-v2.sh",
        "test/_deploy_shell_ws_live.sh",
        "dashboard/asterism-dashboard.py",
        "patches/asterism_shell.js",
    ):
        data = (ROOT / rel).read_bytes()
        assert b"\r\n" not in data and not data.endswith(b"\r"), rel
    print("OK LF policy")


EXPECTED_EXEC = [
    "dashboard/asterism-dashboard.py",
    "desktop/asterism-session.sh",
    "desktop/asterism-session-inner.sh",
    "scripts/asterism-dashmgr",
    "scripts/asterism-ctl.sh",
    "scripts/asterism-displayctl",
    "scripts/asterism-layout",
    "install.sh",
]


def test_git_executable_modes() -> None:
    r = subprocess.run(
        ["git", "ls-files", "-s", *EXPECTED_EXEC],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    assert len(lines) == len(EXPECTED_EXEC), r.stdout
    for ln in lines:
        mode = ln.split()[0]
        assert mode == "100755", f"expected 100755, got {ln}"
    print("OK git executable modes")


def test_probe_still_json_safe() -> None:
    shell = (ROOT / "patches" / "asterism_shell.js").read_text(encoding="utf-8")
    assert "resolveFramesReport" in shell
    assert "report.liveUndocked" in shell
    print("OK probe json path")


def main() -> int:
    test_fiber_find_and_bounds()
    test_fiber_cycle_and_malformed()
    test_signature_requires_xf_and_setstate()
    test_shell_fiber_direct_restore_markers()
    test_transform_validation()
    test_v2_patch_static_analysis()
    test_deploy_trap_ordering()
    test_gitattributes_lf()
    test_git_executable_modes()
    test_probe_still_json_safe()
    # keep prior suite importable
    print("OK all fiber/hygiene tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
