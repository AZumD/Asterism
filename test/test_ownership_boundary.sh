#!/usr/bin/env bash
# Offline + on-device checks: single layout-apply owner, dock ComboBox load, live CLI.
set -euo pipefail
cd "$(dirname "$0")/.."
root=$PWD

fail=0
check() {
  local name=$1
  shift
  if "$@"; then
    echo "PASS $name"
  else
    echo "FAIL $name"
    fail=1
  fi
}

echo "=== Phase 1: single layout restore owner ==="
check session_owns_apply grep -q 'ASTERISM_LAYOUT_OWNER=asterism-session' desktop/asterism-session.sh
check session_runs_apply grep -q 'asterism-layout.*apply' desktop/asterism-session.sh
check dashboard_no_apply_spawn bash -c '! grep -nE "subprocess\\.(run|Popen).*asterism-layout|asterism-layout.*apply" dashboard/asterism-dashboard.py'
# restore_layout must be a no-op stub
check dashboard_restore_stub grep -q 'skipped: layout apply owned by asterism-session' dashboard/asterism-dashboard.py
check focus_visibility_only grep -q 'Visibility/focus only — NEVER mutates layout' dashboard/asterism-dashboard.py
check apply_has_flock grep -q 'fcntl.flock' layout/layout.py
check apply_has_generation grep -q 'APPLY_GEN_PATH' layout/layout.py

echo "=== Phase 1: Desktop Settings dock from layout.json ==="
check settings_load_dock grep -q '_load_dock_combo' desktop-settings/asterism_desktop_settings.py
check settings_uses_screen_dock grep -q 'screen_dock' desktop-settings/asterism_desktop_settings.py

echo "=== Phase 2: live inspect wiring ==="
check layout_cli_live grep -q '"live"' scripts/asterism-layout
check layout_inspect_fn grep -q 'def inspect_live' layout/layout.py
check inspect_helper_src test -f pointer/helper/asterism-overlay-inspect.cpp
check inspect_in_buildsh grep -q 'asterism-overlay-inspect' pointer/helper/build.sh

echo "=== Phase 3: experimental Gamescope scaffolding ==="
check gs_readme test -f gamescope-asterism/README.md
check gs_build test -f scripts/asterism-gamescope-build.sh
check gs_patch test -f scripts/asterism-gamescope-patch.py
check gs_ctrl test -f scripts/asterism-gamescope-ctrl.sh
check session_gs_bin grep -q 'ASTERISM_GAMESCOPE_BIN' desktop/asterism-session.sh
check conf_gs_example grep -q 'ASTERISM_GAMESCOPE_BIN' conf/asterism.conf.example

echo "=== unit: screen_dock + settings source ==="
python3 - <<'PY'
import sys, tempfile, unittest
from pathlib import Path
ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT / "layout"))
from layout import default_layout, save, screen_dock, load

class T(unittest.TestCase):
    def test_screen_dock_reads_saved(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "layout.json"
            lay = default_layout(2)
            lay["screens"][0]["dock"] = "theater"
            lay["screens"][1]["dock"] = "dashboard"
            save(lay, p)
            self.assertEqual(screen_dock(0, p), "theater")
            self.assertEqual(screen_dock(1, p), "dashboard")
            self.assertEqual(screen_dock(99, p), "world")

    def test_settings_calls_load_on_select(self):
        src = (ROOT / "desktop-settings" / "asterism_desktop_settings.py").read_text(encoding="utf-8")
        self.assertIn("self._load_dock_combo()", src)
        # Must not leave ComboBox at construction default without loading.
        self.assertIn("from layout import screen_dock", src)

unittest.main(verbosity=2)
PY

echo "=== unit: layout apply skip-when-locked (fcntl mock via flock file if linux) ==="
python3 test/test_layout.py
python3 test/test_desktop_settings.py

if [ "$fail" -ne 0 ]; then
  echo "SOME CHECKS FAILED"
  exit 1
fi
echo ALL_OK
