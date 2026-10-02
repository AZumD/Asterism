#!/usr/bin/env python3
"""Display topology unit tests."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "display"))

from displays import (  # noqa: E402
    DisplayConfigError,
    add_display,
    default_config,
    load,
    remove_display,
    save,
    set_field,
    set_primary,
    validate_config,
)


class DisplaysTest(unittest.TestCase):
    def test_default_valid(self):
        validate_config(default_config())

    def test_add_remove(self):
        cfg = default_config()
        cfg = add_display(cfg)
        self.assertEqual(len(cfg["displays"]), 2)
        cfg = remove_display(cfg, "display-2")
        self.assertEqual(len(cfg["displays"]), 1)

    def test_one_primary(self):
        cfg = add_display(default_config())
        cfg = set_primary(cfg, "display-2")
        prim = [d for d in cfg["displays"] if d["primary"]]
        self.assertEqual(len(prim), 1)
        self.assertEqual(prim[0]["id"], "display-2")

    def test_invalid_resolution(self):
        cfg = default_config()
        with self.assertRaises(DisplayConfigError):
            set_field(cfg, "display-1", "resolution", "nope")

    def test_scale_bounds(self):
        cfg = default_config()
        with self.assertRaises(DisplayConfigError):
            set_field(cfg, "display-1", "scale", 99)

    def test_atomic_save_and_load(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "displays.json"
            cfg = default_config()
            save(cfg, path)
            loaded = load(path)
            self.assertEqual(loaded["displays"][0]["id"], "display-1")

    def test_malformed_preserves(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "displays.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(DisplayConfigError):
                load(path)
            self.assertTrue(path.with_suffix(".json.corrupt").is_file())
            # original corrupt file still present (not destroyed blindly)
            self.assertTrue(path.is_file())

    def test_cannot_remove_last(self):
        with self.assertRaises(DisplayConfigError):
            remove_display(default_config(), "display-1")

    def test_persistence_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "displays.json"
            cfg = add_display(default_config(), resolution=[1920, 1080])
            cfg = set_field(cfg, "display-2", "scale", 1.25)
            save(cfg, path)
            again = load(path)
            self.assertEqual(again["displays"][1]["resolution"], [1920, 1080])
            self.assertEqual(again["displays"][1]["scale"], 1.25)


if __name__ == "__main__":
    unittest.main()
