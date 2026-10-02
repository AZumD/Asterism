#!/usr/bin/env python3
"""Asterism Desktop Settings v0.1 — display topology only (no spatial VR placement)."""
from __future__ import annotations

import json
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "display"))
sys.path.insert(0, str(ROOT / "scripts"))

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

DISPLAYCTL = ROOT / "scripts" / "asterism-displayctl"


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Asterism Desktop Settings")
        self.geometry("720x480")
        self.cfg = load()
        self.dirty = False
        self._build()
        self.refresh()

    def _build(self) -> None:
        top = ttk.Frame(self, padding=8)
        top.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            top,
            text="Display topology (persistent). Spatial VR placement is configured elsewhere.",
            wraplength=680,
        ).pack(anchor=tk.W)

        self.listbox = tk.Listbox(top, height=10, exportselection=False)
        self.listbox.pack(fill=tk.BOTH, expand=True, pady=8)
        self.listbox.bind("<<ListboxSelect>>", lambda e: self._on_select())

        form = ttk.Frame(top)
        form.pack(fill=tk.X)
        self.var_res = tk.StringVar(value="1280x800")
        self.var_scale = tk.StringVar(value="1.0")
        self.var_rot = tk.StringVar(value="normal")
        self.var_enabled = tk.BooleanVar(value=True)

        ttk.Label(form, text="Resolution").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(form, textvariable=self.var_res, width=16).grid(row=0, column=1, sticky=tk.W)
        ttk.Label(form, text="Scale").grid(row=0, column=2, sticky=tk.W, padx=(12, 0))
        ttk.Entry(form, textvariable=self.var_scale, width=8).grid(row=0, column=3, sticky=tk.W)
        ttk.Label(form, text="Rotation").grid(row=1, column=0, sticky=tk.W)
        ttk.Combobox(form, textvariable=self.var_rot, values=list(ALLOWED_ROTATIONS), width=14).grid(
            row=1, column=1, sticky=tk.W
        )
        ttk.Checkbutton(form, text="Enabled", variable=self.var_enabled).grid(row=1, column=2, columnspan=2, sticky=tk.W)

        btns = ttk.Frame(top)
        btns.pack(fill=tk.X, pady=8)
        for text, cmd in [
            ("Add display", self.add),
            ("Remove", self.remove),
            ("Set primary", self.make_primary),
            ("Apply fields", self.apply_fields),
            ("Save", self.save_cfg),
            ("Stage apply", self.stage_apply),
            ("Restart desktop session…", self.restart_desktop),
        ]:
            ttk.Button(btns, text=text, command=cmd).pack(side=tk.LEFT, padx=2)

        self.status = ttk.Label(top, text="", wraplength=680)
        self.status.pack(anchor=tk.W, pady=4)
        ttk.Label(
            top,
            text="Apply/Save stages ~/.config/asterism/displays.json. "
            "Resolution/count/scale changes require Restart Desktop Session (apps may close).",
            wraplength=680,
        ).pack(anchor=tk.W)

    def selected_id(self) -> str | None:
        sel = self.listbox.curselection()
        if not sel:
            return None
        line = self.listbox.get(sel[0])
        return line.split(":", 1)[0].strip()

    def refresh(self) -> None:
        self.listbox.delete(0, tk.END)
        for d in self.cfg["displays"]:
            w, h = d["resolution"]
            tags = []
            if d.get("primary"):
                tags.append("primary")
            if not d.get("enabled", True):
                tags.append("disabled")
            tag = f" ({', '.join(tags)})" if tags else ""
            self.listbox.insert(tk.END, f"{d['id']}: {w}x{h} scale={d['scale']} rot={d['rotation']}{tag}")
        self.status.config(text=f"Loaded {len(self.cfg['displays'])} display(s). dirty={self.dirty}")

    def _on_select(self) -> None:
        did = self.selected_id()
        if not did:
            return
        d = next(x for x in self.cfg["displays"] if x["id"] == did)
        w, h = d["resolution"]
        self.var_res.set(f"{w}x{h}")
        self.var_scale.set(str(d["scale"]))
        self.var_rot.set(d["rotation"])
        self.var_enabled.set(bool(d["enabled"]))

    def add(self) -> None:
        try:
            self.cfg = add_display(self.cfg)
            self.dirty = True
            self.refresh()
        except DisplayConfigError as e:
            messagebox.showerror("Asterism", str(e))

    def remove(self) -> None:
        did = self.selected_id()
        if not did:
            return
        try:
            self.cfg = remove_display(self.cfg, did)
            self.dirty = True
            self.refresh()
        except DisplayConfigError as e:
            messagebox.showerror("Asterism", str(e))

    def make_primary(self) -> None:
        did = self.selected_id()
        if not did:
            return
        try:
            self.cfg = set_primary(self.cfg, did)
            self.dirty = True
            self.refresh()
        except DisplayConfigError as e:
            messagebox.showerror("Asterism", str(e))

    def apply_fields(self) -> None:
        did = self.selected_id()
        if not did:
            return
        try:
            self.cfg = set_field(self.cfg, did, "resolution", self.var_res.get())
            self.cfg = set_field(self.cfg, did, "scale", self.var_scale.get())
            self.cfg = set_field(self.cfg, did, "rotation", self.var_rot.get())
            self.cfg = set_field(self.cfg, did, "enabled", self.var_enabled.get())
            self.dirty = True
            self.refresh()
        except DisplayConfigError as e:
            messagebox.showerror("Asterism", str(e))

    def save_cfg(self) -> None:
        try:
            self.cfg = save(self.cfg)
            self.dirty = False
            self.refresh()
            messagebox.showinfo("Asterism", "Saved displays.json")
        except DisplayConfigError as e:
            messagebox.showerror("Asterism", str(e))

    def stage_apply(self) -> None:
        self.save_cfg()
        hint = apply_hint(self.cfg)
        messagebox.showinfo(
            "Asterism",
            "Config staged.\n\n"
            f"Primary: {hint['primary_id']} {hint['resolution']}\n"
            f"Enabled outputs: {hint['enabled_count']}\n\n"
            "Desktop session restart required for compositor to apply.",
        )

    def restart_desktop(self) -> None:
        if not messagebox.askyesno(
            "Restart Desktop Session",
            "This restarts Asterism's Plasma/gamescope session.\n"
            "Unsaved apps in that desktop may be lost.\n\nContinue?",
        ):
            return
        self.save_cfg()
        ctl = ROOT / "scripts" / "asterism-ctl.sh"
        try:
            subprocess.run([str(ctl), "stop-desktop"], check=False, timeout=60)
            # Dashboard supervisor / systemd Restart= will bring it back; nudge start:
            subprocess.run(
                ["systemctl", "--user", "start", "asterism-desktop.service"],
                check=False,
                timeout=30,
            )
            messagebox.showinfo("Asterism", "Desktop session restart requested.")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Asterism", str(e))


def main() -> int:
    try:
        App().mainloop()
    except DisplayConfigError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
