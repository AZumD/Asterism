#!/usr/bin/env bash
# UI patch safety tests (does not require applying the patch).
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1091
. "$root/scripts/_env.sh"

pass=0; fail=0
check() { local n=$1; shift; if "$@"; then echo "PASS $n"; pass=$((pass+1)); else echo "FAIL $n"; fail=$((fail+1)); fi; }

echo "=== patch tooling ==="
check "patch script exists" test -x "$root/scripts/patch-steamvr-ui.sh"
check "shell inject exists" test -f "$root/patches/asterism_shell.js"
check "patch dry-run" "$root/scripts/patch-steamvr-ui.sh" --dry-run --yes
check "patch status" "$root/scripts/patch-steamvr-ui.sh" --status

# Unknown hash rejection: temporarily point at bad manifest in a copy
tmpdir=$(mktemp -d)
cp "$root/compatibility/manifest.json" "$tmpdir/m.json"
python3 - "$tmpdir/m.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1]))
m["ui_targets"][1]["sha256"]="0"*64
json.dump(m, open(sys.argv[1],"w"))
PY
if ASTERISM_MANIFEST=$tmpdir/m.json "$root/scripts/patch-steamvr-ui.sh" --dry-run --yes >/tmp/ast-patch-bad.out 2>&1; then
  echo "FAIL unknown hash rejected"; fail=$((fail+1))
else
  echo "PASS unknown hash rejected"; pass=$((pass+1))
fi
rm -rf "$tmpdir"

# Idempotence / restore: only if we have a good backup already
if [ -f "$ASTERISM_BACKUP_DIR/.last_backup" ]; then
  latest=$(tr -d '\r\n' < "$ASTERISM_BACKUP_DIR/.last_backup")
  check "restore dry-run checksums" "$root/scripts/restore-steamvr-ui.sh" --dry-run "$latest"
fi

echo "Result: $pass passed, $fail failed"
[ "$fail" = 0 ]
