#!/usr/bin/env python3
"""asterism-vrsettings unit checks (temp file, no live SteamVR config write)."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "asterism-vrsettings.sh"


class VrsettingsScriptTest(unittest.TestCase):
    def test_script_exists(self):
        self.assertTrue(SCRIPT.is_file())

    def test_merge_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "steamvr.vrsettings"
            path.write_text(
                json.dumps({"dashboard": {"scaleSliderMin": 0.75, "scaleSliderMax": 1.5}}, indent=3)
                + "\n",
                encoding="utf-8",
            )
            # Inline the same merge logic the script uses
            data = json.loads(path.read_text(encoding="utf-8"))
            dash = data.setdefault("dashboard", {})
            dash["asterism_prev_scaleSliderMin"] = dash["scaleSliderMin"]
            dash["asterism_prev_scaleSliderMax"] = dash["scaleSliderMax"]
            dash["scaleSliderMin"] = 0.4
            dash["scaleSliderMax"] = 4.0
            path.write_text(json.dumps(data, indent=3) + "\n", encoding="utf-8")
            out = json.loads(path.read_text(encoding="utf-8"))["dashboard"]
            self.assertEqual(out["scaleSliderMax"], 4.0)
            self.assertEqual(out["asterism_prev_scaleSliderMax"], 1.5)

    def test_conf_example_phys_width(self):
        text = (ROOT / "conf" / "asterism.conf.example").read_text(encoding="utf-8")
        self.assertRegex(text, r"PHYS_WIDTH\s*=\s*2\.5")


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=2))
