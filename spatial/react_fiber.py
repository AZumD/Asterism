#!/usr/bin/env python3
"""Bounded React fiber walk helpers (mirrors asterism_shell.js; unit-testable)."""
from __future__ import annotations

from typing import Any

FIBER_MAX_DEFAULT = 8000


def is_undocked_like(instance: Any, target_frame_id: str | int | None) -> bool:
    if instance is None or not isinstance(instance, dict):
        # allow simple namespace objects
        pass
    if instance is None:
        return False
    set_state = getattr(instance, "setState", None)
    if not callable(set_state) and not (
        isinstance(instance, dict) and callable(instance.get("setState"))
    ):
        return False
    props = getattr(instance, "props", None)
    if props is None and isinstance(instance, dict):
        props = instance.get("props")
    if props is None:
        return False
    frame = getattr(props, "frame", None)
    if frame is None and isinstance(props, dict):
        frame = props.get("frame")
    if frame is None:
        return False
    fid = getattr(frame, "frameID", None)
    if fid is None and isinstance(frame, dict):
        fid = frame.get("frameID")
    if fid is None or target_frame_id is None:
        return False
    if str(fid) != str(target_frame_id):
        return False
    state = getattr(instance, "state", None)
    if state is None and isinstance(instance, dict):
        state = instance.get("state")
    if state is None:
        return False
    xf = getattr(state, "xfTransform", None)
    if xf is None and isinstance(state, dict):
        xf = state.get("xfTransform")
    return xf is not None


def find_live_undocked_overlay(
    root_fiber: Any,
    target_frame_id: str | int,
    *,
    max_nodes: int = FIBER_MAX_DEFAULT,
) -> dict[str, Any]:
    """Walk fiber.child / fiber.sibling only. Never serializes instances."""
    diag: dict[str, Any] = {
        "ok": True,
        "frameID": str(target_frame_id),
        "found": False,
        "visited": 0,
    }
    if root_fiber is None:
        diag["ok"] = False
        diag["error"] = "root fiber missing"
        return {"instance": None, "diag": diag}

    stack = [root_fiber]
    visited: set[int] = set()
    count = 0
    found_instance = None

    def _id(obj: Any) -> int:
        return id(obj)

    while stack and count < max_nodes:
        fiber = stack.pop()
        if fiber is None:
            continue
        fid = _id(fiber)
        if fid in visited:
            continue
        visited.add(fid)
        count += 1

        state_node = getattr(fiber, "stateNode", None)
        if state_node is None and isinstance(fiber, dict):
            state_node = fiber.get("stateNode")
        if is_undocked_like(state_node, target_frame_id):
            found_instance = state_node
            diag["found"] = True
            diag["visited"] = count
            diag["signature"] = {"hasSetState": True, "hasXfTransform": True}
            return {"instance": found_instance, "diag": diag}

        child = getattr(fiber, "child", None)
        if child is None and isinstance(fiber, dict):
            child = fiber.get("child")
        sibling = getattr(fiber, "sibling", None)
        if sibling is None and isinstance(fiber, dict):
            sibling = fiber.get("sibling")
        if child is not None:
            stack.append(child)
        if sibling is not None:
            stack.append(sibling)

    diag["visited"] = count
    diag["ok"] = False
    diag["error"] = "fiber cap reached" if count >= max_nodes else "no matching live instance"
    return {"instance": None, "diag": diag}
