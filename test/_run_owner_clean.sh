#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Antho/Projects/Asterism
sed -i 's/\r$//' \
  "$SRC/pointer/helper/asterism-openvr-owner.cpp" \
  "$SRC/test/_owner_proof_clean.sh"
scp "$SRC/pointer/helper/asterism-openvr-owner.cpp" frame:asterism/pointer/helper/
scp "$SRC/test/_owner_proof_clean.sh" frame:asterism/test/
ssh frame bash -s <<'REMOTE'
set -euo pipefail
cd ~/asterism
sed -i 's/\r$//' pointer/helper/asterism-openvr-owner.cpp pointer/helper/build.sh test/_owner_proof_clean.sh
bash pointer/helper/build.sh
bash test/_owner_proof_clean.sh
REMOTE
