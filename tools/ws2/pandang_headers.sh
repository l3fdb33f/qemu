#!/usr/bin/env bash
# WS-2 step 2: generate panda-ng plugin headers via libpanda-ng (gdb-DWARF
# extractor). Native x86_64 host => no -m64/arm64 surgery needed.
set -uo pipefail

LOG=~/pandang_headers.log
SENT=~/pandang_headers.sentinel
rm -f "$SENT"
exec > "$LOG" 2>&1

echo "=== [$(date)] python deps (tree-sitter for header gen) ==="
# cffi + pycparser already present. Need tree-sitter for build.py's C parser.
python3 -m pip install --user --break-system-packages \
    "tree-sitter==0.24.0" "tree-sitter-c==0.23.0" 2>&1 | tail -5

echo "=== [$(date)] clone libpanda-ng ==="
if [ ! -d ~/libpanda-ng/.git ]; then
    git clone https://github.com/panda-re/libpanda-ng ~/libpanda-ng \
        || { echo "CLONE_FAIL"; echo FAIL > "$SENT"; exit 1; }
fi

echo "=== [$(date)] run_all.sh (gdb type extraction) ==="
rm -rf ~/libpanda-ng/build && mkdir -p ~/libpanda-ng/build
cd ~/libpanda-ng/build
bash ~/libpanda-ng/run_all.sh ~/panda-ng || { echo "HEADERGEN_FAIL"; echo FAIL > "$SENT"; exit 1; }

echo "=== [$(date)] DONE ==="
echo "--- generated headers ---"
ls -la ~/libpanda-ng/build/
echo OK > "$SENT"
