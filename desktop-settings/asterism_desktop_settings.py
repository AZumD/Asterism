#!/usr/bin/env python3
"""Asterism Desktop Settings v0.1 — display topology only (no spatial VR placement).

Host-native GTK3 UI (PyGObject). Steam Frame ships Gtk 3 + gi, but not libtk —
tkinter fails with ImportError on libtk8.6.so. FrameTop's Display Settings
(https://github.com/AZumD/frametop display-settings/) uses PySide6+Kirigami inside
distrobox; Asterism deliberately avoids that runtime dependency and keeps v0.1 to
topology only (mirrors FrameTop's Screens tab: count / resolution / scale /
primary / restart desktop).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "display"))

from displays import (  # noqa: E402
    ALLOWED_ROTATIONS,
    DisplayConfigError,
    add_display,
    apply_hint,
    load,
    remove_display,
    save,
    set_field,
    set_primary,
)

# Same common scales FrameTop exposes on its Screens tab.
SCALE_PRESETS = ("0.75", "1.0", "1.25", "1.333", "1.5", "1.75", "2.0")
RESOLUTION_PRESETS = (
    "1280x800",
    "1280x720",
    "1600x900",
    "1920x1080",
    "1920x1200",
    "2560x1440",
    "2560x1080",
    "3440x1440",
    "1080x1920",
)


def _require_gtk():
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk  # noqa: F401
    except Exception as e:  # noqa: BLE001
        print(
            "Asterism Desktop Settings needs GTK3 (PyGObject).\n"
            f"Import failed: {e}\n"
            "On Steam Frame this is normally present; tkinter is not (no libtk).",
            file=sys.stderr,
        )
        raise SystemExit(1) from e
    return Gtk


class App:
    def __init__(self) -> None:
        Gtk = _require_gtk()
        self.Gtk = Gtk
        self.cfg = load()
        self.dirty = False
        self.selected_id: str | None = None

        self.win = Gtk.Window(title="Asterism Desktop Settings")
        self.win.set_default_size(720, 480)
        self.win.connect("destroy", Gtk.main_quit)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        outer.set_border_width(12)
        self.win.add(outer)

        intro = Gtk.Label(
            label=(
                "Display topology + VR dock mode (dashboard / theater / world). "
                "Enabled outputs must share one resolution (gamescope PerWindow). "
                "Absolute world poses are saved in layout.json; dock restore runs on desktop start "
                "(FrameTop layout pattern)."
            ),
            xalign=0,
            wrap=True,
        )
        outer.pack_start(intro, False, False, 0)

        self.store = Gtk.ListStore(str, str)  # id, label
        self.tree = Gtk.TreeView(model=self.store)
        col = Gtk.TreeViewColumn("Displays", Gtk.CellRendererText(), text=1)
        self.tree.append_column(col)
        self.tree.get_selection().connect("changed", self._on_select)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(160)
        scroll.add(self.tree)
        outer.pack_start(scroll, True, True, 0)

        form = Gtk.Grid(column_spacing=8, row_spacing=6)
        outer.pack_start(form, False, False, 0)

        self.res_combo = Gtk.ComboBoxText.new_with_entry()
        for r in RESOLUTION_PRESETS:
            self.res_combo.append_text(r)
        self.scale_combo = Gtk.ComboBoxText.new_with_entry()
        for s in SCALE_PRESETS:
            self.scale_combo.append_text(s)
        self.rot_combo = Gtk.ComboBoxText()
        for r in ALLOWED_ROTATIONS:
            self.rot_combo.append_text(r)
        self.enabled = Gtk.CheckButton(label="Enabled")
        self.dock_combo = Gtk.ComboBoxText()
        for d in ("world", "theater", "dashboard"):
            self.dock_combo.append_text(d)
        self.dock_combo.set_active(0)

        form.attach(Gtk.Label(label="Resolution", xalign=0), 0, 0, 1, 1)
        form.attach(self.res_combo, 1, 0, 1, 1)
        form.attach(Gtk.Label(label="Scale", xalign=0), 2, 0, 1, 1)
        form.attach(self.scale_combo, 3, 0, 1, 1)
        form.attach(Gtk.Label(label="Rotation", xalign=0), 0, 1, 1, 1)
        form.attach(self.rot_combo, 1, 1, 1, 1)
        form.attach(self.enabled, 2, 1, 2, 1)
        form.attach(Gtk.Label(label="VR dock", xalign=0), 0, 2, 1, 1)
        form.attach(self.dock_combo, 1, 2, 1, 1)

        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        outer.pack_start(btns, False, False, 0)
        for label, cb in (
            ("Add display", self.add),
            ("Remove", self.remove),
            ("Set primary", self.make_primary),
            ("Apply fields", self.apply_fields),
            ("Save", self.save_cfg),
            ("Stage apply", self.stage_apply),
            ("Apply VR layout", self.apply_vr_layout),
            ("Restart desktop…", self.restart_desktop),
        ):
            b = Gtk.Button(label=label)
            b.connect("clicked", lambda _w, fn=cb: fn())
            btns.pack_start(b, False, False, 0)

        self.status = Gtk.Label(label="", xalign=0, wrap=True)
        outer.pack_start(self.status, False, False, 0)
        note = Gtk.Label(
            label=(
                "Save writes displays.json + layout dock modes. "
                "Resolution/count need Restart desktop. "
                "KWin outputs are auto-placed edge-to-edge (no overlap) after Plasma starts."
            ),
            xalign=0,
            wrap=True,
        )
        outer.pack_start(note, False, False, 0)
        self.refresh()
        self.win.show_all()

    def _error(self, msg: str) -> None:
        d = self.Gtk.MessageDialog(
            transient_for=self.win,
            flags=0,
            message_type=self.Gtk.MessageType.ERROR,
            buttons=self.Gtk.ButtonsType.OK,
            text=str(msg),
        )
        d.run()
        d.destroy()

    def _info(self, msg: str) -> None:
        d = self.Gtk.MessageDialog(
            transient_for=self.win,
            flags=0,
            message_type=self.Gtk.MessageType.INFO,
            buttons=self.Gtk.ButtonsType.OK,
            text=str(msg),
        )
        d.run()
        d.destroy()

    def _confirm(self, title: str, body: str) -> bool:
        d = self.Gtk.MessageDialog(
            transient_for=self.win,
            flags=0,
            message_type=self.Gtk.MessageType.QUESTION,
            buttons=self.Gtk.ButtonsType.YES_NO,
            text=title,
        )
        d.format_secondary_text(body)
        resp = d.run()
        d.destroy()
        return resp == self.Gtk.ResponseType.YES

    def refresh(self) -> None:
        self.store.clear()
        for d in self.cfg["displays"]:
            w, h = d["resolution"]
            tags = []
            if d.get("primary"):
                tags.append("primary")
            if not d.get("enabled", True):
                tags.append("disabled")
            tag = f" ({', '.join(tags)})" if tags else ""
            label = f"{d['id']}: {w}x{h} scale={d['scale']} rot={d['rotation']}{tag}"
            self.store.append([d["id"], label])
        self.status.set_text(f"Loaded {len(self.cfg['displays'])} display(s). dirty={self.dirty}")

    def _on_select(self, selection) -> None:
        model, it = selection.get_selected()
        if not it:
            self.selected_id = None
            return
        self.selected_id = model[it][0]
        d = next(x for x in self.cfg["displays"] if x["id"] == self.selected_id)
        w, h = d["resolution"]
        self.res_combo.get_child().set_text(f"{w}x{h}")
        self.scale_combo.get_child().set_text(str(d["scale"]))
        # ComboBoxText active by string
        try:
            idx = list(ALLOWED_ROTATIONS).index(d["rotation"])
        except ValueError:
            idx = 0
        self.rot_combo.set_active(idx)
        self.enabled.set_active(bool(d["enabled"]))

    def add(self) -> None:
        try:
            self.cfg = add_display(self.cfg)
            self.dirty = True
            self.refresh()
        except DisplayConfigError as e:
            self._error(str(e))

    def remove(self) -> None:
        if not self.selected_id:
            return
        try:
            self.cfg = remove_display(self.cfg, self.selected_id)
            self.dirty = True
            self.selected_id = None
            self.refresh()
        except DisplayConfigError as e:
            self._error(str(e))

    def make_primary(self) -> None:
        if not self.selected_id:
            return
        try:
            self.cfg = set_primary(self.cfg, self.selected_id)
            self.dirty = True
            self.refresh()
        except DisplayConfigError as e:
            self._error(str(e))

    def apply_fields(self) -> None:
        if not self.selected_id:
            return
        try:
            res = self.res_combo.get_active_text() or self.res_combo.get_child().get_text()
            scale = self.scale_combo.get_active_text() or self.scale_combo.get_child().get_text()
            rot = self.rot_combo.get_active_text() or "normal"
            self.cfg = set_field(self.cfg, self.selected_id, "resolution", res)
            self.cfg = set_field(self.cfg, self.selected_id, "scale", scale)
            self.cfg = set_field(self.cfg, self.selected_id, "rotation", rot)
            self.cfg = set_field(self.cfg, self.selected_id, "enabled", self.enabled.get_active())
            self.dirty = True
            self.refresh()
        except DisplayConfigError as e:
            self._error(str(e))

    def save_cfg(self) -> None:
        try:
            self.cfg = save(self.cfg)
            self._sync_layout_docks()
            self.dirty = False
            self.refresh()
            self._info("Saved displays.json + layout dock modes")
        except DisplayConfigError as e:
            self._error(str(e))

    def _display_index(self) -> int | None:
        if not self.selected_id:
            return None
        enabled = [d for d in self.cfg["displays"] if d.get("enabled", True)]
        # layout screens follow enabled order: primary first then id
        enabled.sort(key=lambda d: (not d.get("primary", False), d["id"]))
        for i, d in enumerate(enabled):
            if d["id"] == self.selected_id:
                return i
        return None

    def _sync_layout_docks(self) -> None:
        layout_bin = ROOT / "scripts" / "asterism-layout"
        idx = self._display_index()
        dock = self.dock_combo.get_active_text() or "world"
        subprocess.run([str(layout_bin), "sync"], check=False, timeout=30)
        if idx is not None:
            subprocess.run([str(layout_bin), "set-dock", str(idx), dock], check=False, timeout=30)

    def apply_vr_layout(self) -> None:
        self.save_cfg()
        layout_bin = ROOT / "scripts" / "asterism-layout"
        uid = os.getuid()
        host_env = os.environ.copy()
        host_env["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"
        host_env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{uid}/bus"
        try:
            r = subprocess.run(
                [str(layout_bin), "apply", "--wait", "30"],
                capture_output=True,
                text=True,
                env=host_env,
                timeout=90,
                check=False,
            )
            if r.returncode != 0:
                self._error(r.stderr.strip() or r.stdout.strip() or "layout apply failed")
                return
            self._info("VR layout apply requested (dock modes).")
        except Exception as e:  # noqa: BLE001
            self._error(str(e))

    def stage_apply(self) -> None:
        self.save_cfg()
        hint = apply_hint(self.cfg)
        self._info(
            "Config staged.\n\n"
            f"Primary: {hint['primary_id']} {hint['resolution']}\n"
            f"Enabled outputs: {hint['enabled_count']}\n\n"
            "Desktop session restart required for compositor to apply."
        )

    def restart_desktop(self) -> None:
        # Wording aligned with FrameTop PromptDialog: windows close with the session.
        if not self._confirm(
            "Restart the desktop?",
            "Every window on the Asterism desktop closes, this app too. "
            "It starts again with the current settings.",
        ):
            return
        try:
            self.cfg = save(self.cfg)
        except DisplayConfigError as e:
            self._error(str(e))
            return
        ctl = ROOT / "scripts" / "asterism-ctl.sh"
        uid = os.getuid()
        # Nested Plasma uses dbus-run-session's private bus; systemd --user only
        # works on the real user bus (FrameTop host_command / ft-display-settings).
        host_env = os.environ.copy()
        host_env["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"
        host_env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{uid}/bus"
        try:
            # Detach on the real user bus so restart outlives this settings process.
            subprocess.Popen(
                [
                    "systemd-run",
                    "--user",
                    "--collect",
                    "--quiet",
                    "/bin/bash",
                    "-lc",
                    f'"{ctl}" restart-desktop',
                ],
                env=host_env,
                start_new_session=True,
            )
            # Quit without a blocking dialog — the session (and this window) is going away.
            self.Gtk.main_quit()
        except Exception as e:  # noqa: BLE001
            self._error(str(e))


def main() -> int:
    Gtk = _require_gtk()
    if not Gtk.init_check()[0]:
        print(
            "Gtk could not initialize a display.\n"
            "Run via desktop-settings/asterism-desktop-settings so it can attach "
            "to the nested Plasma session (…/asterism_nested), or open the app "
            "from the VR desktop Applications menu.",
            file=sys.stderr,
        )
        return 1
    try:
        App()
        Gtk.main()
    except DisplayConfigError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
