#!/usr/bin/env python3
"""Desktop Settings GUI smoke tests (no display server required for most checks)."""
from __future__ import annotations

import ast
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "desktop-settings" / "asterism_desktop_settings.py"
LAUNCHER = ROOT / "desktop-settings" / "asterism-desktop-settings"


class DesktopSettingsSourceTest(unittest.TestCase):
    def test_no_tkinter_dependency(self):
        src = SETTINGS.read_text(encoding="utf-8")
        tree = ast.parse(src)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    imported.add(a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertNotIn("tkinter", imported)
        self.assertNotIn("_tkinter", imported)

    def test_launcher_exists_and_is_host_wrapper(self):
        self.assertTrue(LAUNCHER.is_file())
        text = LAUNCHER.read_text(encoding="utf-8")
        self.assertIn("asterism_desktop_settings.py", text)
        self.assertIn("asterism-shell-env.sh", text)
        code_lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            code_lines.append(stripped)
        code = "\n".join(code_lines)
        self.assertNotIn("distrobox", code)
        self.assertNotIn("PySide", code)
        self.assertIn("python3", code)
        env_sh = ROOT / "desktop-settings" / "asterism-shell-env.sh"
        self.assertTrue(env_sh.is_file())
        env_text = env_sh.read_text(encoding="utf-8")
        self.assertIn("asterism_nested", env_text)
        self.assertIn("asterism_shell_env_attach", env_text)

    def test_module_loads_helpers_without_gtk_main(self):
        # Import only the constants / path setup by compiling; full App needs Gtk.
        src = SETTINGS.read_text(encoding="utf-8")
        self.assertIn("SCALE_PRESETS", src)
        self.assertIn("RESOLUTION_PRESETS", src)
        self.assertIn("gi.require_version", src)

    def test_gtk_available_or_skip(self):
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # noqa: F401
        except Exception as e:  # noqa: BLE001
            self.skipTest(f"GTK3 not available here: {e}")
        spec = importlib.util.spec_from_file_location("asterism_desktop_settings", SETTINGS)
        self.assertIsNotNone(spec)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        self.assertTrue(callable(mod._require_gtk))
        Gtk = mod._require_gtk()
        self.assertTrue(hasattr(Gtk, "Window"))

    def test_dock_combo_loads_from_layout_not_default(self):
        """Desktop Settings must load saved dock from layout.json per selected display."""
        src = SETTINGS.read_text(encoding="utf-8")
        self.assertIn("def _load_dock_combo", src)
        self.assertIn("screen_dock", src)
        self.assertIn("self._load_dock_combo()", src)
        # Construction may default the ComboBox, but selection must reload saved state.
        select_idx = src.find("def _on_select(")
        self.assertGreater(select_idx, 0)
        chunk = src[select_idx : select_idx + 1200]
        self.assertIn("_load_dock_combo", chunk)


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=2))
