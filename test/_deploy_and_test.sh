#!/usr/bin/env bash
# Sync local Asterism tree to Frame ~/asterism and run install + tests + optional patch.
set -euo pipefail
ssh -o BatchMode=yes frame 'mkdir -p ~/asterism'
# Prefer rsync if available
if command -v rsync >/dev/null; then
  rsync -az --delete --exclude .git --exclude '__pycache__' \
    "C:/Users/Antho/Projects/Asterism/" frame:~/asterism/
else
  scp -o BatchMode=yes -r "C:/Users/Antho/Projects/Asterism/"* frame:~/asterism/
fi
ssh -o BatchMode=yes frame 'bash -s' <<'REMOTE'
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
cd ~/asterism
find . -type f \( -name '*.sh' -o -name '*.py' -o -name 'asterism-displayctl' -o -name '*.js' -o -name '*.example' -o -name '*.desktop' -o -name '*.json' -o -name '*.md' -o -name 'VERSION' \) -print0 | xargs -0 sed -i 's/\r$//'
chmod +x install.sh scripts/*.sh scripts/asterism-displayctl desktop/*.sh dashboard/*.py desktop-settings/*.py test/*.sh test/*.py patches/*.js 2>/dev/null || true

echo "===== display unit tests ====="
python3 test/test_display_config.py

echo "===== lifecycle tests ====="
bash test/test_lifecycle.sh

echo "===== ui patch dry tests ====="
bash test/test_ui_patch.sh

echo "===== reinstall ====="
./install.sh --yes --skip-backup

echo "===== ctl status ====="
./scripts/asterism-ctl.sh status || true

echo "===== patch dry-run ====="
./scripts/patch-steamvr-ui.sh --dry-run --yes
REMOTE
