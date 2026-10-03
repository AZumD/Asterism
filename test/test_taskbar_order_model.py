#!/usr/bin/env python3
"""Offline model of Valve dashboard-bar tab publish sort + GamepadUI surfaces.

Mirrors:
  SteamVR chunk~8012d0c89.js  Dt[] / Pt() in updateVRGamepadUIPathProperties
  Steam steamui chunk~2dcc5aaf7.js  Nt() left bookend vs main tabs

PoC: Asterism-specific bucket between Steam(14) and appid(33).
"""
from __future__ import annotations

ASTERISM_APP_PREFIX = "asterism.desktop.app."


def is_asterism_app_overlay(overlay: str | None) -> bool:
    return isinstance(overlay, str) and overlay.startswith(ASTERISM_APP_PREFIX)


def sort_bucket_stock(icon: dict | None) -> int:
    """Pre-PoC Valve Dt buckets."""
    if not icon:
        return 5
    if icon.get("enum") == 14:
        return 0
    if icon.get("enum") == 33:
        return 1
    if icon.get("overlay"):
        return 2
    if icon.get("enum") == 15:
        return 3
    if icon.get("hwnd") is not None:
        return 4
    return 5


def sort_bucket_poc(icon: dict | None) -> int:
    """PoC Dt: Steam, Asterism app.N, appid 33, other overlay, Display 15, hwnd."""
    if not icon:
        return 6
    if icon.get("enum") == 14:
        return 0
    ov = icon.get("overlay")
    if is_asterism_app_overlay(ov):
        return 1
    if icon.get("enum") == 33:
        return 2
    if ov:  # other overlays; Asterism already excluded above
        return 3
    if icon.get("enum") == 15:
        return 4
    if icon.get("hwnd") is not None:
        return 5
    return 6


def publish_sort(tabs: list[dict], *, poc: bool = True) -> list[dict]:
    bucket = sort_bucket_poc if poc else sort_bucket_stock
    return sorted(
        tabs,
        key=lambda t: (bucket(t.get("icon")), t.get("tab_id") or 0),
    )


def gamepadui_surfaces(tabs: list[dict]) -> dict:
    """Nt(): Steam enum 14 -> left bookend; everything else -> main (order preserved)."""
    left = [t for t in tabs if (t.get("icon") or {}).get("enum") == 14]
    main = [t for t in tabs if (t.get("icon") or {}).get("enum") != 14]
    return {"left_bookend": left, "main_tabs": main}


def kind_for(tab: dict) -> str:
    icon = tab.get("icon") or {}
    if icon.get("enum") == 14:
        return "steam"
    if is_asterism_app_overlay(icon.get("overlay")):
        return "asterism-display"
    if icon.get("enum") == 33:
        return "appid"
    if icon.get("overlay"):
        return "overlay"
    if icon.get("enum") == 15:
        return "display-enum"
    if icon.get("hwnd") is not None:
        return "hwnd"
    return "other"


def mixed_fixture() -> list[dict]:
    """Deliberately mixed input order for PoC expectations."""
    return [
        {"tab_id": 50, "title": "Steam", "icon": {"enum": 14}},
        {"tab_id": 20, "title": "AppA", "icon": {"enum": 33, "appid": 10}},
        {
            "tab_id": 40,
            "title": "Ast3",
            "icon": {"overlay": "asterism.desktop.app.3"},
        },
        {
            "tab_id": 15,
            "title": "UnrelatedOverlay",
            "icon": {"overlay": "system.example.overlay"},
        },
        {"tab_id": 30, "title": "AppB", "icon": {"enum": 33, "appid": 20}},
        {
            "tab_id": 10,
            "title": "Ast2",
            "icon": {"overlay": "asterism.desktop.app.2"},
        },
        {"tab_id": 60, "title": "HwndTab", "icon": {"hwnd": "99"}},
    ]


def test_stock_order_puts_apps_before_asterism():
    ordered = publish_sort(mixed_fixture(), poc=False)
    titles = [t["title"] for t in ordered]
    kinds = [kind_for(t) for t in ordered]
    # Stock: Steam, appid(33), then ALL overlays by tab_id (Asterism mixed
    # with unrelated), then hwnd.
    assert titles == [
        "Steam",
        "AppA",
        "AppB",
        "Ast2",
        "UnrelatedOverlay",
        "Ast3",
        "HwndTab",
    ]
    assert kinds == [
        "steam",
        "appid",
        "appid",
        "asterism-display",
        "overlay",
        "asterism-display",
        "hwnd",
    ]
    apps = [t for t in ordered if kind_for(t) == "appid"]
    assert [t["title"] for t in apps] == ["AppA", "AppB"]


def test_poc_order_asterism_after_steam_before_apps():
    ordered = publish_sort(mixed_fixture(), poc=True)
    titles = [t["title"] for t in ordered]
    kinds = [kind_for(t) for t in ordered]
    # Asterism sorted by tab_id within bucket: .2 (10) before .3 (40)
    assert titles == [
        "Steam",
        "Ast2",
        "Ast3",
        "AppA",
        "AppB",
        "UnrelatedOverlay",
        "HwndTab",
    ]
    assert kinds == [
        "steam",
        "asterism-display",
        "asterism-display",
        "appid",
        "appid",
        "overlay",
        "hwnd",
    ]
    surfaces = gamepadui_surfaces(ordered)
    assert [t["title"] for t in surfaces["left_bookend"]] == ["Steam"]
    assert [t["title"] for t in surfaces["main_tabs"]] == [
        "Ast2",
        "Ast3",
        "AppA",
        "AppB",
        "UnrelatedOverlay",
        "HwndTab",
    ]


def test_asterism_app_999_and_prefix_not_bare_desktop():
    tabs = [
        {"tab_id": 1, "title": "Steam", "icon": {"enum": 14}},
        {
            "tab_id": 2,
            "title": "BareDesktop",
            "icon": {"overlay": "asterism.desktop"},
        },
        {
            "tab_id": 3,
            "title": "Ast999",
            "icon": {"overlay": "asterism.desktop.app.999"},
        },
        {"tab_id": 4, "title": "App", "icon": {"enum": 33, "appid": 1}},
    ]
    ordered = publish_sort(tabs, poc=True)
    assert [t["title"] for t in ordered] == [
        "Steam",
        "Ast999",
        "App",
        "BareDesktop",
    ]
    assert kind_for(ordered[1]) == "asterism-display"
    assert kind_for(ordered[3]) == "overlay"
    assert not is_asterism_app_overlay("asterism.desktop")
    assert is_asterism_app_overlay("asterism.desktop.app.999")


def test_unrelated_overlay_and_app_bucket_stable():
    tabs = [
        {"tab_id": 5, "title": "Steam", "icon": {"enum": 14}},
        {"tab_id": 3, "title": "AppHi", "icon": {"enum": 33, "appid": 2}},
        {"tab_id": 1, "title": "AppLo", "icon": {"enum": 33, "appid": 1}},
        {
            "tab_id": 9,
            "title": "OtherOv",
            "icon": {"overlay": "valve.steam.something"},
        },
        {
            "tab_id": 2,
            "title": "Ast",
            "icon": {"overlay": "asterism.desktop.app.1"},
        },
    ]
    ordered = publish_sort(tabs, poc=True)
    assert [t["title"] for t in ordered] == [
        "Steam",
        "Ast",
        "AppLo",
        "AppHi",
        "OtherOv",
    ]
    # Same object identities
    by_id = {t["tab_id"]: t for t in tabs}
    for t in ordered:
        assert t is by_id[t["tab_id"]]


def test_poc_excludes_asterism_from_other_overlay_bucket():
    # Conceptual: Asterism must not also classify as generic overlay.
    icon = {"overlay": "asterism.desktop.app.2"}
    assert sort_bucket_poc(icon) == 1
    assert sort_bucket_poc({"overlay": "system.foo"}) == 3


if __name__ == "__main__":
    test_stock_order_puts_apps_before_asterism()
    test_poc_order_asterism_after_steam_before_apps()
    test_asterism_app_999_and_prefix_not_bare_desktop()
    test_unrelated_overlay_and_app_bucket_stable()
    test_poc_excludes_asterism_from_other_overlay_bucket()
    print("ok")
