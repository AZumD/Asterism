#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Antho/Projects/Asterism
# Sync repo content to Frame without wiping local-only junk first; exclude heavy/local.
rsync -av --delete \
  --exclude '.git/' \
  --exclude 'gamescope-asterism/src/' \
  --exclude 'gamescope-asterism/build/' \
  --exclude 'gamescope-asterism/out/' \
  --exclude 'pointer/helper/build/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.cache/' \
  "$SRC/" frame:asterism/
ssh frame 'bash -s' <<'REMOTE'
set -euo pipefail
cd ~/asterism
find scripts desktop pointer/helper test -type f \( -name '*.sh' -o -name 'asterism-layout' -o -name 'asterism-gamescope*' \) -print0 2>/dev/null | xargs -0 -r sed -i 's/\r$//'
sed -i 's/\r$//' pointer/helper/build.sh install.sh 2>/dev/null || true
chmod +x scripts/* pointer/helper/build.sh test/*.sh 2>/dev/null || true
bash pointer/helper/build.sh
ls -la pointer/helper/build/
echo '--- status ---'
./scripts/asterism-status.sh || true
echo '--- keys ---'
./scripts/asterism-layout keys || true
echo '--- gamescope asterism ---'
pgrep -af 'gamescope .*asterism[.]desktop' || echo 'no asterism gamescope'
echo '--- dashboard ---'
systemctl --user is-active asterism-dashboard.service || true
systemctl --user is-active asterism-desktop.service || true
REMOTE
