#!/usr/bin/env python3
"""Layout + multi-display topology tests."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "layout"))
sys.path.insert(0, str(ROOT / "display"))

from displays import DisplayConfigError, add_display, default_config, set_field, validate_config  # noqa: E402
from layout import default_layout, ensure_screen_count, save, validate_layout  # noqa: E402


class MultiDisplayTest(unittest.TestCase):
    def test_multi_requires_same_resolution(self):
        cfg = default_config()
        cfg = set_field(cfg, "display-1", "resolution", "1920x1080")
        cfg = add_display(cfg, resolution=[1920, 1080])
        validate_config(cfg)
        with self.assertRaises(DisplayConfigError):
            set_field(cfg, "display-2", "resolution", "1280x800")


class LayoutTest(unittest.TestCase):
    def test_default_arc_two(self):
        lay = default_layout(2)
        validate_layout(lay)
        self.assertEqual(len(lay["screens"]), 2)
        self.assertEqual(lay["screens"][0]["dock"], "world")

    def test_ensure_count(self):
        lay = ensure_screen_count(default_layout(1), 3)
        self.assertEqual(len(lay["screens"]), 3)

    def test_save_load(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "layout.json"
            save(default_layout(2), path)
            self.assertTrue(path.is_file())


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=2))
