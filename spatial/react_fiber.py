#!/usr/bin/env python3
"""Bounded React fiber walk helpers (mirrors asterism_shell.js; unit-testable)."""
from __future__ import annotations

from typing import Any

FIBER_MAX_DEFAULT = 8000


def _props_frame_id(instance: Any) -> str | None:
    props = getattr(instance, "props", None)
    if props is None and isinstance(instance, dict):
        props = instance.get("props")
    if props is None:
        return None
    frame = getattr(props, "frame", None)
    if frame is None and isinstance(props, dict):
        frame = props.get("frame")
    if frame is None:
        return None
    fid = getattr(frame, "frameID", None)
    if fid is None and isinstance(frame, dict):
        fid = frame.get("frameID")
    return None if fid is None else str(fid)


def _has_set_state(instance: Any) -> bool:
    set_state = getattr(instance, "setState", None)
    if callable(set_state):
        return True
    return isinstance(instance, dict) and callable(instance.get("setState"))


def is_weak_undocked_instance(
    instance: Any, target_frame_id: str | int | None
) -> bool:
    """Mounted class with matching frameID; xfTransform may be null/undefined."""
    if instance is None or target_frame_id is None:
        return False
    if not _has_set_state(instance):
        return False
    fid = _props_frame_id(instance)
    return fid is not None and fid == str(target_frame_id)


def is_undocked_like(instance: Any, target_frame_id: str | int | None) -> bool:
    if instance is None or not isinstance(instance, dict):
        # allow simple namespace objects
        pass
    if not is_weak_undocked_instance(instance, target_frame_id):
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


def weak_instance_candidate_diag(instance: Any, tree: str) -> dict[str, Any]:
    """JSON-safe metadata for a weak fiber match (mirrors asterism_shell.js)."""
    state = getattr(instance, "state", None)
    if state is None and isinstance(instance, dict):
        state = instance.get("state")
    state_present = isinstance(state, dict) or (
        state is not None and not isinstance(state, (str, int, float, bool))
    )
    has_own_xf = False
    xf = None
    xf_nullish = True
    if state is not None:
        if isinstance(state, dict):
            has_own_xf = "xfTransform" in state
            xf = state.get("xfTransform")
        else:
            has_own_xf = hasattr(state, "xfTransform")
            xf = getattr(state, "xfTransform", None)
        xf_nullish = xf is None
    out: dict[str, Any] = {
        "tree": tree,
        "frameID": _props_frame_id(instance),
        "constructorName": type(instance).__name__,
        "hasSetState": _has_set_state(instance),
        "statePresent": bool(state_present),
        "hasOwnXfTransform": has_own_xf,
        "xfTransformNullish": xf_nullish,
        "sParentDevice": getattr(state, "sParentDevice", None)
        if state is not None and not isinstance(state, dict)
        else (state.get("sParentDevice") if isinstance(state, dict) else None),
        "dragSnapLocation": getattr(state, "dragSnapLocation", None)
        if state is not None and not isinstance(state, dict)
        else (state.get("dragSnapLocation") if isinstance(state, dict) else None),
        "hasSetInitialTransformForLocation": callable(
            getattr(instance, "setInitialTransformForLocation", None)
        ),
        "hasComponentDidMount": callable(
            getattr(instance, "componentDidMount", None)
        ),
    }
    if xf is not None and isinstance(xf, dict):
        out["xfTransform"] = xf
    return out


def walk_fiber_tree_weak(
    root_fiber: Any,
    target_frame_id: str | int,
    tree: str,
    *,
    max_nodes: int = FIBER_MAX_DEFAULT,
    seen_state_nodes: set[int] | None = None,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    if root_fiber is None:
        return {"candidates": candidates, "visited": 0}
    stack = [root_fiber]
    visited: set[int] = set()
    count = 0
    while stack and count < max_nodes:
        fiber = stack.pop()
        if fiber is None:
            continue
        fid = id(fiber)
        if fid in visited:
            continue
        visited.add(fid)
        count += 1
        state_node = getattr(fiber, "stateNode", None)
        if state_node is None and isinstance(fiber, dict):
            state_node = fiber.get("stateNode")
        if is_weak_undocked_instance(state_node, target_frame_id):
            sn_id = id(state_node)
            if seen_state_nodes is not None and sn_id in seen_state_nodes:
                pass
            else:
                if seen_state_nodes is not None:
                    seen_state_nodes.add(sn_id)
                candidates.append(weak_instance_candidate_diag(state_node, tree))
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
    return {"candidates": candidates, "visited": count}


def inspect_undocked_instance(
    primary_root: Any,
    target_frame_id: str | int,
    *,
    alternate_root: Any = None,
    max_nodes: int = FIBER_MAX_DEFAULT,
) -> dict[str, Any]:
    """Primary + alternate weak walks with stateNode dedup (unit-test mirror)."""
    seen: set[int] = set()
    primary = walk_fiber_tree_weak(
        primary_root,
        target_frame_id,
        "primary",
        max_nodes=max_nodes,
        seen_state_nodes=seen,
    )
    alternate_present = alternate_root is not None
    alternate = (
        walk_fiber_tree_weak(
            alternate_root,
            target_frame_id,
            "alternate",
            max_nodes=max_nodes,
            seen_state_nodes=seen,
        )
        if alternate_present
        else {"candidates": [], "visited": 0}
    )
    candidates = primary["candidates"] + alternate["candidates"]
    return {
        "ok": True,
        "targetFrameID": str(target_frame_id),
        "candidateCount": len(candidates),
        "primaryVisited": primary["visited"],
        "alternatePresent": alternate_present,
        "alternateVisited": alternate["visited"],
        "candidates": candidates,
    }


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
