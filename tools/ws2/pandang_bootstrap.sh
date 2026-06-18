#!/usr/bin/env bash
# WS-2 native host build bootstrap. Clones our fork to ~/qemu (NEVER touches
# ~/panda or ~/pandbox) and builds the panda-ng core (x86_64-softmmu).
set -uo pipefail

LOG=~/pandang_build.log
SENT=~/pandang_build.sentinel
rm -f "$SENT"
exec > "$LOG" 2>&1

echo "=== [$(date)] clone ==="
if [ ! -d ~/qemu/.git ]; then
    git clone --branch wip/record-replay \
        https://github.com/l3fdb33f/qemu.git ~/qemu || { echo "CLONE_FAIL"; echo FAIL > "$SENT"; exit 1; }
fi
cd ~/qemu
echo "HEAD: $(git rev-parse --short HEAD) $(git log -1 --format=%s)"

echo "=== [$(date)] configure ==="
mkdir -p build && cd build
../configure \
    --target-list=x86_64-softmmu \
    --enable-plugins \
    --disable-docs \
    --disable-werror \
    --disable-rust || { echo "CONFIGURE_FAIL"; echo FAIL > "$SENT"; exit 1; }

echo "=== [$(date)] ninja ==="
ninja -j "$(nproc)" || { echo "NINJA_FAIL"; echo FAIL > "$SENT"; exit 1; }

echo "=== [$(date)] DONE ==="
ls -la libpanda-x86_64-softmmu.so qemu-system-x86_64 2>/dev/null
echo OK > "$SENT"
